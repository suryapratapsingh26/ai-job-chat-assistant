from fastapi import FastAPI

from backend.app.services.job_dataset import JobDataset

app = FastAPI(title="AI Job Chat Assistant")
dataset = JobDataset()


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
