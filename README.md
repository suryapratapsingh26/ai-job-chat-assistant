# AI Job Chat Assistant

## Stack

- Frontend: React, TypeScript, and Vite
- Backend: Python and FastAPI
- API: REST; job listings are read from `data/jobs.json`

## Backend

From the repository root, install and run the API:

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
```

The backend requirements include `pypdf` for PDF extraction, `python-docx` for DOCX extraction, and `python-multipart` for multipart uploads.

The existing `GET /health` endpoint returns API status. `GET /api/jobs?offset=0&limit=100` returns a page of general listings and the total dataset count. FastAPI allows the local Vite origins `http://localhost:5173` and `http://127.0.0.1:5173` by default. Set `FRONTEND_ORIGINS` to a comma-separated list of exact origins to change this allowlist.

`POST /api/resume/parse` accepts a multipart `file` field with a PDF or DOCX resume (up to 10 MB) and returns a structured candidate profile. Text extraction and profile parsing run in memory; uploads are not saved. Scanned/image-only PDFs and password-protected PDFs are not supported. Profile parsing uses deterministic text/section heuristics and may leave fields empty when they are not clearly present.

## Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the app at `http://127.0.0.1:5173`. The API client uses `http://localhost:8000` by default. Copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to change the backend base URL, then restart Vite.

The frontend includes a conversational workspace, a PDF/DOCX resume upload and parsed-profile view, and a job-listings panel connected to `GET /api/jobs`. Chat messages are local to the page and do not trigger job search, filtering, or AI responses.

## Job data pipeline

The standalone collector retrieves current listings from the public [Arbeitnow job API](https://www.arbeitnow.com/api/job-board-api) and optional public Greenhouse boards, normalizes fields, derives stable IDs, and removes duplicates. The normalized dataset is stored in `data/jobs.json`; the target is up to 1,800 real listings, depending on source availability.

From the repository root, run:

```powershell
python scripts/scrape_jobs.py
python scripts/validate_jobs.py
```

Scraper settings such as `SCRAPER_MAX_JOBS`, request delay, timeout, retries, maximum pages, and `GREENHOUSE_BOARDS` are read from environment variables. See `.env.example` for the available settings.

## Later stages

Resume parsing, job matching and recommendations, conversational refinement, agent orchestration, job application, and application tracking are not implemented yet. These will be added in later stages; the current UI does not claim these capabilities.
