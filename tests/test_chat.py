import asyncio
import json
import sys
from types import SimpleNamespace

from backend.app import main
from backend.app.agents.orchestrator import (
    ChatConfigurationError,
    JobChatOrchestrator,
    ChatProviderError,
    GroqIntentParser,
)
from backend.app.api import chat as chat_api
from backend.app.api import jobs as jobs_api
from backend.app.models.chat import ChatFilters, ChatRequest, ChatTurn, IntentAction, IntentPlan
from backend.app.models.job import Job
from backend.app.models.resume import ResumeProfile


def make_job(job_id: str, title: str, location: str, skills: list[str], experience: str = "", description: str = "") -> Job:
    return Job(
        job_id=job_id, title=title, company="Example Co", location=location, experience=experience,
        skills=skills, description=description, source_link=f"https://example.com/{job_id}",
    )


def make_plan(
    intent: IntentAction = IntentAction.SEARCH_JOBS,
    *,
    skills: list[str] | None = None,
    location: str | None = None,
    remote: bool | None = None,
    role: str | None = None,
    experience_level: str | None = None,
    replace_skills: bool = False,
    clear_filters: bool = False,
    explanation_index: int | None = None,
) -> IntentPlan:
    return IntentPlan(
        intent=intent, skills=skills or [], location=location, remote=remote, role=role,
        experience_level=experience_level, replace_skills=replace_skills,
        clear_filters=clear_filters, explanation_index=explanation_index,
    )


class FakeParser:
    def __init__(self, *plans):
        self.plans = list(plans)
        self.calls = []

    def parse(self, request: ChatRequest):
        self.calls.append(request)
        return self.plans.pop(0)


def call_asgi(method: str, path: str, payload: dict | None = None):
    async def call():
        body = json.dumps(payload).encode() if payload is not None else b""
        delivered = False
        messages = []

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        route, _, query = path.partition("?")
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": method, "scheme": "http", "path": route,
            "raw_path": route.encode(), "query_string": query.encode(), "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode())],
            "client": ("testclient", 50000), "server": ("testserver", 80),
        }
        await main.app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return start["status"], json.loads(response_body)

    return asyncio.run(call())


def test_groq_structured_intent_parser_uses_mocked_response(monkeypatch):
    expected = make_plan(
        IntentAction.REFINE_JOBS, skills=["React"], replace_skills=True,
    )
    observed = {}

    class FakeCompletions:
        def create(self, **kwargs):
            observed.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=expected.model_dump_json(), refusal=None,
            ))])

    class FakeChat:
        completions = FakeCompletions()

    class FakeCompatibleClient:
        def __init__(self, api_key, base_url):
            assert api_key == "test-key"
            assert base_url == "https://api.groq.com/openai/v1"
            self.chat = FakeChat()

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeCompatibleClient))
    request = ChatRequest(
        message="Only React",
        history=[ChatTurn(role="user", content="Show me remote Python jobs")],
        active_filters=ChatFilters(remote=True, skills=["Python"]),
    )
    parsed = GroqIntentParser().parse(request)
    assert parsed.intent is IntentAction.REFINE_JOBS
    assert parsed.skills == ["React"]
    assert parsed.replace_skills is True
    assert observed["model"] == "openai/gpt-oss-20b"
    assert observed["response_format"]["type"] == "json_schema"
    assert observed["response_format"]["json_schema"]["strict"] is True
    assert "job_id" not in json.dumps(observed["messages"])


def test_missing_groq_api_key_returns_clear_configuration_error(monkeypatch):
    # An empty environment value takes precedence over any developer-local .env file.
    monkeypatch.setenv("GROQ_API_KEY", "")
    try:
        GroqIntentParser().parse(ChatRequest(message="Show me remote jobs"))
    except ChatConfigurationError as exc:
        assert "GROQ_API_KEY" in str(exc)
    else:
        raise AssertionError("missing API key was not reported")


def test_groq_provider_failure_is_logged_safely_and_keeps_public_error(monkeypatch, caplog):
    class FakeProviderError(RuntimeError):
        status_code = 401
        request_id = "req_test_123"
        response = SimpleNamespace(
            status_code=401,
            headers={"content-type": "application/json", "x-request-id": "req_test_123"},
        )
        body = {"error": "unauthorized"}

    class FailingCompletions:
        def create(self, **kwargs):
            raise FakeProviderError(
                "provider rejected request; Authorization: Bearer hidden-token; "
                "message=Find private jobs; key=test-key"
            )

    class FakeCompatibleClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FailingCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeCompatibleClient))
    with caplog.at_level("ERROR"):
        try:
            GroqIntentParser().parse(ChatRequest(message="Find private jobs"))
        except ChatProviderError as exc:
            assert str(exc) == "The conversational search service could not be reached. Please try again."
        else:
            raise AssertionError("provider failure was not reported")

    assert "FakeProviderError" in caplog.text
    assert "status_code=401" in caplog.text
    assert "request_id=req_test_123" in caplog.text
    assert "provider rejected request" in caplog.text
    assert "hidden-token" not in caplog.text
    assert "test-key" not in caplog.text
    assert "Find private jobs" not in caplog.text


def test_groq_invalid_structured_output_is_rejected(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"intent":"execute_shell"}', refusal=None,
            ))])

    class FakeCompatibleClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeCompatibleClient))
    try:
        GroqIntentParser().parse(ChatRequest(message="Show me jobs"))
    except Exception as exc:
        assert "invalid search plan" in str(exc)
    else:
        raise AssertionError("invalid plan was accepted")


def test_remote_filter_matches_known_remote_signals():
    jobs = [
        make_job("remote-location", "Engineer", "Remote job", []),
        make_job("remote-skill", "Developer", "Berlin", ["Remote"]),
        make_job("onsite", "Developer", "Berlin", ["Python"]),
    ]
    response = JobChatOrchestrator(FakeParser(make_plan(remote=True))).handle(
        ChatRequest(message="Show me remote jobs"), jobs,
    )
    assert [job.job_id for job in response.jobs] == ["remote-location", "remote-skill"]
    assert response.active_filters.remote is True


def test_skill_filter_uses_whole_phrases_not_substrings():
    jobs = [
        make_job("js", "Developer", "Berlin", ["JavaScript"]),
        make_job("java", "Developer", "Berlin", ["Java"]),
        make_job("nosql", "Developer", "Berlin", ["NoSQL"]),
    ]
    parser = FakeParser(make_plan(skills=["Java"]))
    java = JobChatOrchestrator(parser).handle(ChatRequest(message="Java only"), jobs)
    sql = JobChatOrchestrator(FakeParser(make_plan(skills=["SQL"]))).handle(ChatRequest(message="SQL only"), jobs)
    assert [job.job_id for job in java.jobs] == ["java"]
    assert sql.jobs == []


def test_location_filter_uses_normalized_location_field():
    jobs = [make_job("india", "Engineer", "Bengaluru, India", []), make_job("berlin", "Engineer", "Berlin", [])]
    response = JobChatOrchestrator(FakeParser(make_plan(location="India"))).handle(
        ChatRequest(message="Show jobs in India"), jobs,
    )
    assert [job.job_id for job in response.jobs] == ["india"]


def test_multiple_constraints_are_combined():
    jobs = [
        make_job("good", "Senior Backend Engineer", "Remote", ["Python", "React"]),
        make_job("wrong-location", "Senior Backend Engineer", "Berlin", ["Python", "React"]),
        make_job("wrong-skill", "Senior Backend Engineer", "Remote", ["Python"]),
        make_job("wrong-role", "Senior Frontend Developer", "Remote", ["Python", "React"]),
    ]
    plan = make_plan(
        skills=["Python", "React"], remote=True, role="Backend", experience_level="senior",
    )
    response = JobChatOrchestrator(FakeParser(plan)).handle(ChatRequest(message="Python backend remote senior"), jobs)
    assert [job.job_id for job in response.jobs] == ["good"]


def test_followup_refinement_keeps_existing_constraints_and_replaces_skill():
    jobs = [
        make_job("remote-backend", "Backend Engineer", "Remote", ["Python", "React"]),
        make_job("berlin-backend", "Backend Engineer", "Berlin", ["Python", "React"]),
        make_job("remote-frontend", "Frontend Developer", "Remote", ["React"]),
    ]
    orchestrator = JobChatOrchestrator(FakeParser(
        make_plan(skills=["Python"], remote=True, role="Backend"),
        make_plan(IntentAction.REFINE_JOBS, skills=["React"], replace_skills=True),
    ))
    first = orchestrator.handle(ChatRequest(message="Show me remote Python backend jobs"), jobs)
    second = orchestrator.handle(ChatRequest(
        message="Only React",
        history=[ChatTurn(role="user", content="Show me remote Python backend jobs")],
        active_filters=first.active_filters,
        current_job_ids=[job.job_id for job in first.jobs],
    ), jobs)
    assert second.active_filters.remote is True
    assert second.active_filters.role == "Backend"
    assert second.active_filters.skills == ["React"]
    assert [job.job_id for job in second.jobs] == ["remote-backend"]


def test_no_result_search_suggests_relaxing_filters():
    response = JobChatOrchestrator(FakeParser(make_plan(skills=["Rust"], location="India"))).handle(
        ChatRequest(message="Show remote Rust roles in India"),
        [make_job("one", "Engineer", "Berlin", ["Python"])],
    )
    assert response.jobs == []
    assert "couldn’t find" in response.assistant_message
    assert "relaxing" in response.assistant_message


def test_explanation_uses_existing_deterministic_match_reasons():
    jobs = [make_job("python", "Backend Engineer", "Remote", ["Python", "FastAPI"])]
    response = JobChatOrchestrator(FakeParser(make_plan(IntentAction.EXPLAIN_JOB))).handle(
        ChatRequest(message="Why is the first one a good match?", profile=ResumeProfile(
            designation="Backend Engineer", skills=["Python", "FastAPI"],
        ), current_job_ids=["python"]),
        jobs,
    )
    assert "Backend Engineer at Example Co" in response.assistant_message
    assert "100/100" in response.assistant_message
    assert "Python, FastAPI" in response.assistant_message
    assert response.recommendations[0].match_reasons


def test_invalid_unsafe_model_output_is_rejected_before_search():
    class UnsafeParser:
        def parse(self, request):
            return {"intent": "execute_shell", "command": "format c:", "skills": []}

    try:
        JobChatOrchestrator(UnsafeParser()).handle(
            ChatRequest(message="do something"), [make_job("one", "Engineer", "Remote", [])],
        )
    except Exception as exc:
        assert "invalid search plan" in str(exc)
    else:
        raise AssertionError("unsafe plan was accepted")


def test_chat_endpoint_accepts_search_and_returns_typed_results(monkeypatch):
    monkeypatch.setattr(chat_api.dataset, "load", lambda: [
        make_job("remote", "Developer", "Remote", ["Python"]),
        make_job("onsite", "Developer", "Berlin", ["Python"]),
    ])
    monkeypatch.setattr(GroqIntentParser, "parse", lambda self, request: make_plan(remote=True))
    status, payload = call_asgi("POST", "/api/chat", {"message": "Show me remote jobs"})
    assert status == 200
    assert payload["intent"] == "search_jobs"
    assert payload["jobs"][0]["job_id"] == "remote"
    assert payload["personalized"] is False
    assert payload["assistant_message"]


def test_chat_endpoint_reports_missing_key_and_invalid_schema(monkeypatch):
    monkeypatch.setattr(chat_api.dataset, "load", lambda: [])
    monkeypatch.setenv("GROQ_API_KEY", "")
    status, payload = call_asgi("POST", "/api/chat", {"message": "Show jobs"})
    assert status == 503
    assert "GROQ_API_KEY" in payload["error"]

    monkeypatch.setattr(GroqIntentParser, "parse", lambda self, request: {"intent": "read_secret", "skills": []})
    status, payload = call_asgi("POST", "/api/chat", {"message": "Search"})
    assert status == 502
    assert "No job action was executed" in payload["error"]


def test_chat_endpoint_validates_request_and_existing_endpoints_work(monkeypatch):
    status, _ = call_asgi("POST", "/api/chat", {"history": []})
    assert status == 422
    status, health = call_asgi("GET", "/health")
    assert status == 200
    assert health == {"status": "ok"}

    listing = make_job("existing", "Engineer", "Remote", ["Python"])
    monkeypatch.setattr(main.dataset, "load", lambda: [listing])
    status, jobs = call_asgi("GET", "/api/jobs?offset=0&limit=1")
    assert status == 200 and jobs["jobs"][0]["job_id"] == "existing"

    monkeypatch.setattr(jobs_api.dataset, "load", lambda: [listing])
    status, matches = call_asgi("POST", "/api/jobs/match", {"profile": {"skills": ["Python"]}})
    assert status == 200 and matches["recommendations"][0]["job"]["job_id"] == "existing"
