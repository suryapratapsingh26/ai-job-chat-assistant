from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backend.app.models.application import ApplicationWithJob
from backend.app.models.job import Job
from backend.app.models.matching import JobRecommendation
from backend.app.models.resume import ResumeProfile


class ChatIntent(StrEnum):
    SEARCH_JOBS = "search_jobs"
    REFINE_JOBS = "refine_jobs"
    EXPLAIN_JOB = "explain_job"
    SHOW_JOBS = "show_jobs"
    APPLY_JOB = "apply_job"
    LIST_APPLICATIONS = "list_applications"
    GENERAL = "general"
    ERROR = "error"


class IntentAction(StrEnum):
    SEARCH_JOBS = "search_jobs"
    REFINE_JOBS = "refine_jobs"
    EXPLAIN_JOB = "explain_job"
    SHOW_JOBS = "show_jobs"
    APPLY_JOB = "apply_job"
    LIST_APPLICATIONS = "list_applications"
    GENERAL = "general"


class ExperienceLevel(StrEnum):
    INTERN = "intern"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class ChatFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    skills: list[Annotated[str, StringConstraints(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=10)
    location: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    remote: bool | None = None
    role: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    experience_level: ExperienceLevel | None = None


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=1000)
    profile: ResumeProfile | None = None
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    active_filters: ChatFilters = Field(default_factory=ChatFilters)
    current_job_ids: list[str] = Field(default_factory=list, max_length=1800)
    selected_job_id: str | None = None


class IntentPlan(BaseModel):
    """Closed schema returned by the LLM; it only selects allowed search actions."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intent: IntentAction
    skills: list[Annotated[str, StringConstraints(min_length=1, max_length=50)]] = Field(max_length=10)
    location: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    remote: bool | None
    role: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    experience_level: ExperienceLevel | None
    replace_skills: bool
    clear_filters: bool
    explanation_index: int | None = Field(ge=0, le=23)
    job_reference: int | None = Field(default=None, ge=1, le=1800)


class ChatResponse(BaseModel):
    assistant_message: str
    intent: ChatIntent
    jobs: list[Job] = Field(default_factory=list)
    recommendations: list[JobRecommendation] = Field(default_factory=list)
    applications: list[ApplicationWithJob] = Field(default_factory=list)
    active_filters: ChatFilters = Field(default_factory=ChatFilters)
    personalized: bool = False
    error: str | None = None
