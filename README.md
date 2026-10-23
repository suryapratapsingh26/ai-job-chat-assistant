# AI Job Chat Assistant

## Job data pipeline

The standalone collector retrieves current listings from the public [Arbeitnow job API](https://www.arbeitnow.com/api/job-board-api) and optional public Greenhouse boards, normalizes fields, derives stable IDs, and removes duplicates. The normalized dataset is stored in `data/jobs.json`; the target is up to 1,800 real listings, depending on source availability.

From the repository root, run:

```powershell
python scripts/scrape_jobs.py
python scripts/validate_jobs.py
```

Configuration is read from environment variables (copy `.env.example` as a reference; the scripts do not require a dotenv package). `SCRAPER_MAX_JOBS`, request delay, timeout, retries, and maximum pages control collection. `GREENHOUSE_BOARDS` accepts optional comma-separated public Greenhouse board slugs to supplement the default Arbeitnow feed. `JOBS_OUTPUT` can override the output path.

The FastAPI service loads this JSON through `backend/app/services/job_dataset.py`. `GET /api/jobs?offset=0&limit=100` returns a page and total count; the existing `GET /health` remains available.
