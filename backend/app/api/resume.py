from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.models.resume import ResumeParseResponse
from backend.app.services.resume_parser import MAX_RESUME_BYTES, ResumeProcessingError, parse_resume_document

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile | None = File(default=None)):
    if file is None:
        raise HTTPException(status_code=400, detail="Choose a PDF or DOCX resume to upload.")
    try:
        contents = await file.read(MAX_RESUME_BYTES + 1)
        return {"profile": parse_resume_document(file.filename or "", file.content_type or "", contents)}
    except ResumeProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        await file.close()
