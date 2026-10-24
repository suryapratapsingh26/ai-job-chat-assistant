"""Persistent local application records stored separately from job data."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from collections.abc import Sequence

from pydantic import ValidationError

from backend.app.models.application import ApplicationWithJob, JobApplication
from backend.app.models.job import Job

_storage_lock = RLock()


class ApplicationError(RuntimeError):
    pass


class JobNotFoundError(ApplicationError):
    pass


class DuplicateApplicationError(ApplicationError):
    def __init__(self, application: JobApplication):
        super().__init__(f"An application for job {application.job_id} already exists.")
        self.application = application


class ApplicationStorageError(ApplicationError):
    pass


class ApplicationService:
    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else (
            Path(__file__).resolve().parents[3] / "data" / "applications.json"
        )

    def _read(self) -> list[JobApplication]:
        try:
            if not self.storage_path.exists():
                return []
            content = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(content, list):
                raise ValueError("Application store must contain a JSON array.")
            return [JobApplication.model_validate(item) for item in content]
        except (OSError, ValueError, ValidationError) as exc:
            raise ApplicationStorageError("Application records could not be read.") from exc

    def _write(self, applications: list[JobApplication]) -> None:
        temp_path = None
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.storage_path.parent,
                prefix=f".{self.storage_path.name}.", suffix=".tmp", delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(
                    [application.model_dump(mode="json") for application in applications],
                    temp_file, ensure_ascii=False, indent=2,
                )
                temp_file.write("\n")
            os.replace(temp_path, self.storage_path)
        except OSError as exc:
            if temp_path:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ApplicationStorageError("Application records could not be saved.") from exc

    def list_applications(self, jobs: Sequence[Job]) -> list[ApplicationWithJob]:
        with _storage_lock:
            applications = self._read()
        jobs_by_id = {job.job_id: job for job in jobs}
        return [
            ApplicationWithJob(**application.model_dump(), job=jobs_by_id.get(application.job_id))
            for application in applications
        ]

    def apply(self, job_id: str, jobs: Sequence[Job]) -> ApplicationWithJob:
        jobs_by_id = {job.job_id: job for job in jobs}
        job = jobs_by_id.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} was not found in the current dataset.")

        with _storage_lock:
            applications = self._read()
            existing = next((application for application in applications if application.job_id == job_id), None)
            if existing:
                raise DuplicateApplicationError(existing)
            application = JobApplication(
                job_id=job_id,
                applied_at=datetime.now(timezone.utc),
            )
            applications.append(application)
            self._write(applications)
        return ApplicationWithJob(**application.model_dump(), job=job)
