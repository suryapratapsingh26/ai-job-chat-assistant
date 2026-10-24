from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.app.agents.orchestrator import (
    ChatConfigurationError,
    ChatProviderError,
    InvalidIntentPlanError,
    GroqIntentParser,
    JobChatOrchestrator,
)
from backend.app.models.chat import ChatRequest, ChatResponse
from backend.app.models.job import Job
from backend.app.services.job_dataset import JobDataset
from backend.app.services.application_service import ApplicationStorageError

router = APIRouter(prefix="/api/chat", tags=["chat"])
dataset = JobDataset()


def get_jobs() -> list[Job]:
    return dataset.load()


def get_orchestrator() -> JobChatOrchestrator:
    return JobChatOrchestrator(GroqIntentParser())


@router.post("", response_model=ChatResponse, responses={
    502: {"model": ChatResponse, "description": "Intent planning failed"},
    503: {"model": ChatResponse, "description": "Groq configuration required"},
    500: {"model": ChatResponse, "description": "Application storage unavailable"},
})
def chat(
    request: ChatRequest,
    orchestrator: JobChatOrchestrator = Depends(get_orchestrator),
    jobs: list[Job] = Depends(get_jobs),
) -> ChatResponse:
    try:
        return orchestrator.handle(request, jobs)
    except ChatConfigurationError as exc:
        message = str(exc)
        return JSONResponse(
            status_code=503,
            content=ChatResponse(assistant_message=message, intent="error", error=message).model_dump(mode="json"),
        )
    except InvalidIntentPlanError as exc:
        message = "The assistant returned an invalid search plan. No job action was executed; please try again."
        return JSONResponse(
            status_code=502,
            content=ChatResponse(assistant_message=message, intent="error", error=message).model_dump(mode="json"),
        )
    except ChatProviderError as exc:
        message = str(exc)
        return JSONResponse(
            status_code=502,
            content=ChatResponse(assistant_message=message, intent="error", error=message).model_dump(mode="json"),
        )
    except ApplicationStorageError:
        message = "Application records are unavailable. Please try again later."
        return JSONResponse(
            status_code=500,
            content=ChatResponse(assistant_message=message, intent="error", error=message).model_dump(mode="json"),
        )
