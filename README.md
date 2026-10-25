# AI Job Chat Assistant

AI Job Chat Assistant is a job-search assistant that helps users find jobs using their resume and chat.

You can upload a PDF/DOCX resume, get matching jobs, refine the results by chatting with the assistant, and keep track of jobs you have applied to.

## Tech Stack

- **React + TypeScript + Vite** — frontend
- **Python + FastAPI** — backend
- **Groq** — AI for understanding chat requests
- **Pydantic** — data validation
- **JSON** — job dataset and application records

## How it works

1. Upload your resume.
2. The application extracts your profile.
3. Matching jobs are shown based on your skills and experience.
4. You can refine the results by chatting with the assistant.
5. You can apply to a job from the results.
6. Your applications are saved so you can check them later.

## Architecture

The application has a React frontend and a FastAPI backend.

The backend is divided into separate parts for resume parsing, job matching, job search, chat orchestration, and application tracking.

Groq is used to understand what the user wants from the conversation. The actual job filtering, matching, and application handling are done by the backend.

## Data Flow

1. The user uploads a PDF or DOCX resume through the React frontend.
2. The FastAPI backend parses the resume and extracts a structured candidate profile.
3. The matching service compares the profile against the job dataset and generates ranked job recommendations.
4. Chat requests are sent to the backend orchestrator, which uses Groq to understand the requested action or refinement.
5. The backend applies deterministic job filters, matching logic, or application actions based on the interpreted request.
6. When a user applies to a job, the application record is saved with the job ID, application date, and status.
7. Application status requests retrieve the saved application records and return them to the frontend.

## Job Data

The project uses a dataset of around 1,800 real job listings collected from public job sources.

Each job contains information such as the title, company, location, skills, description, and source link.

The scraper and validation scripts are included in the `scripts` folder.

## API Endpoints

### Resume

- `POST /api/resume/parse` — upload and parse a PDF/DOCX resume.

### Jobs

- `GET /api/jobs` — retrieve available job listings.
- `POST /api/jobs/match` — generate job recommendations based on a candidate profile.

### Chat

- `POST /api/chat` — process conversational job-search, refinement, application, and application-status requests.

### Applications

- `POST /api/applications` — record an application.
- `GET /api/applications` — retrieve recorded applications.

## Run Locally

### Backend

```powershell
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Add your `GROQ_API_KEY` to `backend/.env`, then run:

```powershell
python -m uvicorn backend.app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Project Structure

```text
frontend/   React frontend
backend/    FastAPI backend
data/       Job data and applications
scripts/    Job scraper and validation
tests/      Tests
```
