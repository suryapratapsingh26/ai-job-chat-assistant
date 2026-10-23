from pydantic import BaseModel, Field

from backend.app.models.job import Job
from backend.app.models.resume import ResumeProfile


class JobMatchRequest(BaseModel):
    profile: ResumeProfile


class MatchScoringDetails(BaseModel):
    skills: float | None = None
    title: float | None = None
    experience: float | None = None
    description: float | None = None


class JobRecommendation(BaseModel):
    job: Job
    match_score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    scoring_details: MatchScoringDetails


class JobMatchResponse(BaseModel):
    total_matches: int = Field(ge=0)
    recommendations: list[JobRecommendation] = Field(default_factory=list)
