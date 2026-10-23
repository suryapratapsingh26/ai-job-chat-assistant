import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.resume import router as resume_router
from backend.app.api.jobs import router as jobs_router
from backend.app.services.job_dataset import JobDataset

app = FastAPI(title="AI Job Chat Assistant")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)
dataset = JobDataset()
app.include_router(resume_router)
app.include_router(jobs_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/jobs")
def list_jobs(offset: int = 0, limit: int = 100):
    """Return a page of prepared jobs and the total record count."""
    jobs = dataset.load()
    safe_offset = max(0, offset)
    safe_limit = min(max(1, limit), 500)
    return {"total": len(jobs), "offset": safe_offset, "limit": safe_limit, "jobs": jobs[safe_offset:safe_offset + safe_limit]}
