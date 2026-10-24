from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from backend.app.models.job import Job


class ApplicationStatus(StrEnum):
    APPLIED = "applied"


class JobApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    applied_at: datetime
    status: ApplicationStatus = ApplicationStatus.APPLIED


class ApplicationWithJob(JobApplication):
    job: Job | None


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationWithJob]


class ApplyToJobRequest(BaseModel):
    job_id: str
