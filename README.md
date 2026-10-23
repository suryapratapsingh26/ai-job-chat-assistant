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

Copy `backend/.env.example` to `backend/.env` and add your Groq API key. The backend loads that local file without overriding environment variables already set by your shell or host. Conversational search requires `GROQ_API_KEY`; `GROQ_MODEL` is optional and defaults to `openai/gpt-oss-20b`. You can also configure these environment variables in the shell that starts the backend.

```powershell
$env:GROQ_API_KEY = "your-key"
$env:GROQ_MODEL = "openai/gpt-oss-20b" # optional; this is the default
python -m uvicorn backend.app.main:app --reload
```

In Windows Command Prompt (`cmd.exe`):

```bat
set "GROQ_API_KEY=your-key"
set "GROQ_MODEL=openai/gpt-oss-20b"
python -m uvicorn backend.app.main:app --reload
```

The orchestrator uses Groq through the OpenAI-compatible API, backed by the existing OpenAI Python SDK. Its default model supports strict JSON Schema structured output; Pydantic validates each result before the backend applies deterministic filtering and matching. Without `GROQ_API_KEY`, upload, job listing, and deterministic resume matching continue to work; `POST /api/chat` returns a clear configuration error.

The existing `GET /health` endpoint returns API status. `GET /api/jobs?offset=0&limit=100` returns a page of general listings and the total dataset count. FastAPI allows the local Vite origins `http://localhost:5173` and `http://127.0.0.1:5173` by default. Set `FRONTEND_ORIGINS` to a comma-separated list of exact origins to change this allowlist.

`POST /api/resume/parse` accepts a multipart `file` field with a PDF or DOCX resume (up to 10 MB) and returns a structured candidate profile. Text extraction and profile parsing run in memory; uploads are not saved. Scanned/image-only PDFs and password-protected PDFs are not supported. Profile parsing uses deterministic text/section heuristics and may leave fields empty when they are not clearly present.

`POST /api/jobs/match?limit=24` accepts `{ "profile": <parsed profile> }` and returns ranked recommendations from the existing dataset. The limit is optional and supports 1–100 results. Matching is deterministic: skills carry 60% of the weight, title alignment 25%, experience compatibility 10%, and resume experience/project description overlap 5%; unavailable signals are excluded and remaining weights are normalized. Each result includes its 0–100 score, matched skills, reasons, and per-signal scores. The resume upload panel offers “Find matching jobs” after parsing; files and profiles are not stored by the API.

`POST /api/chat` accepts a message, optional parsed profile, recent conversation turns, active filters, and current result IDs. It returns an assistant message, the selected intent, bounded job results, active filters, and personalized match details when a profile is present. The orchestrator uses Groq strict JSON Schema output to extract a closed intent/filter schema, validates it, then runs deterministic filtering and the existing matcher locally. The model never receives the job dataset or selects job IDs/scores; the parsed resume profile is also kept out of the intent prompt. Only the current message, up to 12 prior turns, and active filter state are sent to Groq. No conversation state is persisted by this application.

## Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the app at `http://127.0.0.1:5173`. The API client uses `http://localhost:8000` by default. Copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to change the backend base URL, then restart Vite.

The frontend includes a conversational workspace, a PDF/DOCX resume upload and parsed-profile view, and a job-listings panel connected to `GET /api/jobs`. After parsing a resume, “Find matching jobs” requests recommendations from `POST /api/jobs/match`. Chat messages call `POST /api/chat`, display the assistant response, and update the results panel; follow-up messages include history and active filters so the backend can refine the current result set. General searches work without a resume and are labeled separately from personalized recommendations.

## Job data pipeline

The standalone collector retrieves current listings from the public [Arbeitnow job API](https://www.arbeitnow.com/api/job-board-api) and optional public Greenhouse boards, normalizes fields, derives stable IDs, and removes duplicates. The normalized dataset is stored in `data/jobs.json`; the target is up to 1,800 real listings, depending on source availability.

From the repository root, run:

```powershell
python scripts/scrape_jobs.py
python scripts/validate_jobs.py
```

Scraper settings such as `SCRAPER_MAX_JOBS`, request delay, timeout, retries, maximum pages, and `GREENHOUSE_BOARDS` are read from environment variables. See `.env.example` for the available settings.

## Later stages

Job application and application tracking are not implemented. Conversational filtering is deterministic after the Groq intent parser returns a validated plan; filtering/scoring, application submission, and application status are not delegated to the LLM.
