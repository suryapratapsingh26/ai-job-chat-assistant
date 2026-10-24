"""Plan and coordinate safe, deterministic job-search capabilities."""

import json
import logging
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from backend.app.models.chat import (
    ChatFilters,
    ChatIntent,
    ChatRequest,
    ChatResponse,
    ExperienceLevel,
    IntentAction,
    IntentPlan,
)
from backend.app.models.job import Job
from backend.app.models.matching import JobRecommendation
from backend.app.services.application_service import (
    ApplicationService,
    DuplicateApplicationError,
    JobNotFoundError,
)
from backend.app.services.job_matcher import match_jobs
from backend.app.services.job_search import filter_jobs, filter_recommendations

MAX_CHAT_RESULTS = 24
logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """You are the intent parser for a job-search assistant. Return only the supplied structured schema.
Choose one allowed intent: search_jobs for a fresh job search, refine_jobs for changing the current search,
explain_job for asking why a current result is relevant, show_jobs for repeating the current result list,
apply_job for applying to a job in the current result list, list_applications for showing saved applications,
or general for greetings/help/off-topic messages. For apply_job, set job_reference to the one-based position
only when the user specifies a job number; leave it null for "this job". The application service resolves
the reference against backend-provided current result IDs. Never provide a job ID, date, or status. For
list_applications, leave job_reference null. Extract only constraints explicitly requested by the user.
Do not invent job facts, job IDs, actions, or filters. Skills must be short skill names. Location is a place name.
Remote is true for remote-only and false for onsite-only; leave it null when not specified. Experience level
must be one of intern, entry, junior, mid, senior, lead. For refinement, return only newly requested constraints;
the application combines them with the current filters. Set replace_skills true when the user explicitly replaces
the previous skill constraint (for example, "only React"), otherwise false. Set clear_filters true only when the
user starts an unrelated fresh search or asks to clear/reset filters. For show_jobs, apply_job, list_applications,
and general, leave search constraints empty. For explain_job, use explanation_index 0 for the first current result
unless the user specifies another.
When prior context clearly establishes a current search, interpret ordinary search follow-ups as refinements and
preserve other filters. Explicit apply and application-status requests keep their application intent."""


class IntentParser(Protocol):
    def parse(self, request: ChatRequest) -> IntentPlan: ...


class ChatConfigurationError(RuntimeError):
    """Raised when an API key or provider configuration is missing."""


class ChatProviderError(RuntimeError):
    """Raised when the model cannot return a usable structured plan."""


class InvalidIntentPlanError(ChatProviderError):
    """Raised when model output does not validate against the allowed schema."""


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"

# Groq's strict JSON Schema mode expects every field to be required and does not
# need Pydantic's $defs/$ref output. Pydantic remains the authority for validation.
INTENT_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [action.value for action in IntentAction],
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "location": {"type": ["string", "null"]},
        "remote": {"type": ["boolean", "null"]},
        "role": {"type": ["string", "null"]},
        "experience_level": {
            "type": ["string", "null"],
            "enum": [level.value for level in ExperienceLevel] + [None],
        },
        "replace_skills": {"type": "boolean"},
        "clear_filters": {"type": "boolean"},
        "explanation_index": {"type": ["integer", "null"]},
        "job_reference": {"type": ["integer", "null"], "minimum": 1, "maximum": 1800},
    },
    "required": [
        "intent", "skills", "location", "remote", "role", "experience_level",
        "replace_skills", "clear_filters", "explanation_index", "job_reference",
    ],
    "additionalProperties": False,
}


class _SafeProviderException(Exception):
    """Sanitized exception text used with the original provider traceback."""


def _safe_provider_error_message(exc: Exception, api_key: str, context: dict) -> str:
    message = str(exc)
    sensitive_values = [api_key, json.dumps(context, ensure_ascii=False)]
    sensitive_values.extend(turn["content"] for turn in context["history"])
    sensitive_values.append(context["message"])
    sensitive_values.extend(str(value) for value in context["current_filters"].values() if value is not None)
    for value in sorted((value for value in sensitive_values if value), key=len, reverse=True):
        message = message.replace(value, "[REDACTED]")
    message = re.sub(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+", r"\1[REDACTED]", message)
    message = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    return message[:1000]


def _provider_response_metadata(exc: Exception) -> tuple[object, ...]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    body = getattr(exc, "body", None)
    body_size = len(body) if isinstance(body, (str, bytes, bytearray)) else None
    return (
        getattr(exc, "status_code", None) or getattr(response, "status_code", None),
        getattr(exc, "request_id", None) or headers.get("x-request-id") or headers.get("X-Request-ID"),
        headers.get("content-type") or headers.get("Content-Type"),
        type(body).__name__ if body is not None else None,
        body_size,
    )


def _load_groq_environment() -> None:
    """Load Groq settings from backend/.env without overriding the host environment."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        key = key.strip()
        if not separator or key not in {"GROQ_API_KEY", "GROQ_MODEL"} or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


class GroqIntentParser:
    def parse(self, request: ChatRequest) -> IntentPlan:
        # Environment variables supplied by the hosting environment take precedence.
        _load_groq_environment()
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ChatConfigurationError(
                "Conversational search requires GROQ_API_KEY. Configure the key and restart the backend."
            )

        context = {
            "message": request.message,
            "history": [turn.model_dump() for turn in request.history[-12:]],
            "current_filters": request.active_filters.model_dump(mode="json"),
            "current_result_count": len(request.current_job_ids),
        }
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "job_search_intent",
                        "strict": True,
                        "schema": INTENT_PLAN_JSON_SCHEMA,
                    },
                },
            )
            choice = response.choices[0]
            if getattr(choice.message, "refusal", None):
                raise InvalidIntentPlanError("The assistant did not return a structured search plan.")
            content = choice.message.content
            if not content:
                raise InvalidIntentPlanError("The assistant did not return a structured search plan.")
            return IntentPlan.model_validate_json(content)
        except InvalidIntentPlanError:
            raise
        except ValidationError as exc:
            raise InvalidIntentPlanError("The assistant returned an invalid search plan.") from exc
        except Exception as exc:
            safe_message = _safe_provider_error_message(exc, api_key, context)
            status_code, request_id, content_type, body_type, body_size = _provider_response_metadata(exc)
            safe_exc = _SafeProviderException(safe_message)
            logger.exception(
                "Groq provider request failed (exception_type=%s, message=%s, status_code=%s, "
                "request_id=%s, response_content_type=%s, response_body_type=%s, response_body_size=%s)",
                type(exc).__name__, safe_message, status_code, request_id, content_type, body_type, body_size,
                exc_info=(type(safe_exc), safe_exc, exc.__traceback__),
            )
            raise ChatProviderError("The conversational search service could not be reached. Please try again.") from exc


def _merge_filters(current: ChatFilters, plan: IntentPlan) -> ChatFilters:
    if plan.clear_filters:
        current = ChatFilters()
    skills = [] if plan.replace_skills else list(current.skills)
    seen = {skill.casefold() for skill in skills}
    for skill in plan.skills:
        if skill.casefold() not in seen:
            skills.append(skill)
            seen.add(skill.casefold())
    values = current.model_dump()
    values["skills"] = skills
    for key in ("location", "remote", "role", "experience_level"):
        update = getattr(plan, key)
        if update is not None:
            values[key] = update
    return ChatFilters.model_validate(values)


def _active_filter_summary(filters: ChatFilters) -> str:
    parts = []
    if filters.remote is True:
        parts.append("remote")
    elif filters.remote is False:
        parts.append("onsite")
    if filters.skills:
        parts.append("skills: " + ", ".join(filters.skills))
    if filters.location:
        parts.append("location: " + filters.location)
    if filters.role:
        parts.append("role: " + filters.role)
    if filters.experience_level:
        parts.append(filters.experience_level.value + " level")
    return "; ".join(parts)


def _search_message(intent: IntentAction, filters: ChatFilters, count: int, personalized: bool) -> str:
    scope = "resume matches" if personalized else "job listings"
    constraints = _active_filter_summary(filters)
    if not count:
        if constraints:
            return f"I couldn’t find {scope} for {constraints}. Try relaxing one of those filters."
        return "I couldn’t find jobs in the current dataset. Try again later."
    if intent is IntentAction.SHOW_JOBS:
        return f"Here are the {count} current {scope}{' for ' + constraints if constraints else ''}."
    if intent is IntentAction.REFINE_JOBS:
        return f"I narrowed the search to {count} {scope}{' for ' + constraints if constraints else ''}."
    return f"I found {count} {scope}{' for ' + constraints if constraints else ''}."


def _explain_recommendation(recommendation: JobRecommendation) -> str:
    job = recommendation.job
    details = [f"{job.title} at {job.company} has a {recommendation.match_score}/100 match score."]
    if recommendation.matched_skills:
        details.append("Your matching skills are " + ", ".join(recommendation.matched_skills) + ".")
    details.extend(recommendation.match_reasons[:2])
    return " ".join(details)


class JobChatOrchestrator:
    def __init__(self, intent_parser: IntentParser, application_service: ApplicationService | None = None):
        self.intent_parser = intent_parser
        self.application_service = application_service or ApplicationService()

    def handle(self, request: ChatRequest, jobs: Sequence[Job]) -> ChatResponse:
        plan = self.intent_parser.parse(request)
        if not isinstance(plan, IntentPlan):
            try:
                plan = IntentPlan.model_validate(plan)
            except ValidationError as exc:
                raise InvalidIntentPlanError("The assistant returned an invalid search plan.") from exc

        if plan.intent is IntentAction.APPLY_JOB:
            if request.selected_job_id is not None:
                job_id = request.selected_job_id
                if job_id not in request.current_job_ids:
                    return ChatResponse(
                        assistant_message="I couldn't identify that job in the current results. Ask to apply to a numbered job in the displayed list.",
                        intent=ChatIntent.APPLY_JOB,
                        active_filters=request.active_filters,
                    )
            else:
                reference = plan.job_reference
                if reference is None and len(request.current_job_ids) == 1:
                    reference = 1
                if reference is None or reference > len(request.current_job_ids):
                    return ChatResponse(
                        assistant_message="I couldn't identify that job in the current results. Ask to apply to a numbered job in the displayed list.",
                        intent=ChatIntent.APPLY_JOB,
                        active_filters=request.active_filters,
                    )
                job_id = request.current_job_ids[reference - 1]
            job = next((item for item in jobs if item.job_id == job_id), None)
            if job is None:
                return ChatResponse(
                    assistant_message="That job is no longer available in the current dataset. Please choose another displayed job.",
                    intent=ChatIntent.APPLY_JOB,
                    active_filters=request.active_filters,
                )
            try:
                application = self.application_service.apply(job_id, jobs)
                message = f"Application recorded for {job.title} at {job.company}. Status: {application.status.value}."
            except DuplicateApplicationError:
                application = next(
                    item for item in self.application_service.list_applications(jobs)
                    if item.job_id == job_id
                )
                message = f"You've already applied to {job.title} at {job.company}. Status: {application.status.value}."
            except JobNotFoundError:
                return ChatResponse(
                    assistant_message="That job is no longer available in the current dataset. Please choose another displayed job.",
                    intent=ChatIntent.APPLY_JOB,
                    active_filters=request.active_filters,
                )
            return ChatResponse(
                assistant_message=message,
                intent=ChatIntent.APPLY_JOB,
                jobs=[job],
                applications=[application],
                active_filters=request.active_filters,
            )

        if plan.intent is IntentAction.LIST_APPLICATIONS:
            applications = self.application_service.list_applications(jobs)
            application_jobs = [item.job for item in applications if item.job is not None]
            message = (
                f"You have {len(applications)} recorded application{'s' if len(applications) != 1 else ''}."
                if applications else "You don't have any recorded applications yet."
            )
            return ChatResponse(
                assistant_message=message,
                intent=ChatIntent.LIST_APPLICATIONS,
                jobs=application_jobs,
                applications=applications,
                active_filters=request.active_filters,
            )

        if plan.intent is IntentAction.GENERAL:
            return ChatResponse(
                assistant_message="I can search the job dataset, refine results by skills, role, location, work mode, or experience level, and explain resume matches.",
                intent=ChatIntent.GENERAL,
                active_filters=request.active_filters,
                personalized=request.profile is not None,
            )

        filters = request.active_filters
        if plan.intent in {IntentAction.SEARCH_JOBS, IntentAction.REFINE_JOBS}:
            filters = _merge_filters(filters, plan)

        recommendations: list[JobRecommendation] = []
        if request.profile is not None:
            all_recommendations, _ = match_jobs(request.profile, jobs, limit=len(jobs))
            recommendations = filter_recommendations(all_recommendations, filters, limit=MAX_CHAT_RESULTS)
            results = recommendations
        else:
            general_jobs = filter_jobs(jobs, filters, limit=MAX_CHAT_RESULTS)
            results = general_jobs

        assistant_message = _search_message(plan.intent, filters, len(results), request.profile is not None)
        if plan.intent is IntentAction.EXPLAIN_JOB:
            index = plan.explanation_index or 0
            if request.current_job_ids:
                order = {job_id: position for position, job_id in enumerate(request.current_job_ids)}
                results = sorted(results, key=lambda item: order.get(
                    item.job.job_id if isinstance(item, JobRecommendation) else item.job_id,
                    len(order),
                ))
            if results:
                selected = results[index] if index < len(results) else results[0]
                if isinstance(selected, JobRecommendation):
                    assistant_message = _explain_recommendation(selected)
                else:
                    constraints = _active_filter_summary(filters)
                    assistant_message = (
                        f"{selected.title} at {selected.company} appears in the results"
                        f"{' because it matches ' + constraints if constraints else ' from the job dataset'}. "
                        "Without a parsed resume, there is no personalized match score."
                    )

        return ChatResponse(
            assistant_message=assistant_message,
            intent=ChatIntent(plan.intent.value),
            jobs=[item.job for item in results] if request.profile is not None else results,
            recommendations=recommendations,
            active_filters=filters,
            personalized=request.profile is not None,
        )
