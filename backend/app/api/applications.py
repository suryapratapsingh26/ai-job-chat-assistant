from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.application import (
    ApplicationListResponse,
    ApplicationWithJob,
    ApplyToJobRequest,
)
from backend.app.models.job import Job
from backend.app.services.application_service import (
    ApplicationService,
    ApplicationStorageError,
    DuplicateApplicationError,
    JobNotFoundError,
)
from backend.app.services.job_dataset import JobDataset

router = APIRouter(prefix="/api/applications", tags=["applications"])
dataset = JobDataset()
application_service = ApplicationService()


def get_jobs() -> list[Job]:
    return dataset.load()


@router.post("", response_model=ApplicationWithJob, status_code=status.HTTP_201_CREATED)
def apply_to_job(request: ApplyToJobRequest, jobs: list[Job] = Depends(get_jobs)) -> ApplicationWithJob:
    try:
        return application_service.apply(request.job_id, jobs)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That job does not exist.") from exc
    except DuplicateApplicationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already applied to that job.") from exc
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application records are unavailable.") from exc


@router.get("", response_model=ApplicationListResponse)
def list_applications(jobs: list[Job] = Depends(get_jobs)) -> ApplicationListResponse:
    try:
        return ApplicationListResponse(applications=application_service.list_applications(jobs))
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application records are unavailable.") from exc
