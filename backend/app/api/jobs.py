from fastapi import APIRouter, Depends, Query

from backend.app.models.matching import JobMatchRequest, JobMatchResponse
from backend.app.models.job import Job
from backend.app.services.job_dataset import JobDataset
from backend.app.services.job_matcher import match_jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
dataset = JobDataset()


def get_jobs() -> list[Job]:
    return dataset.load()


@router.post("/match", response_model=JobMatchResponse)
def recommend_jobs(
    request: JobMatchRequest,
    limit: int = Query(default=24, ge=1, le=100),
    jobs: list[Job] = Depends(get_jobs),
) -> JobMatchResponse:
    recommendations, total_matches = match_jobs(request.profile, jobs, limit)
    return JobMatchResponse(total_matches=total_matches, recommendations=recommendations)
