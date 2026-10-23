from pydantic import BaseModel, ConfigDict, Field


class ResumeProfile(BaseModel):
    """Structured candidate details extracted from an uploaded resume."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: str | None = None
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


class ResumeParseResponse(BaseModel):
    profile: ResumeProfile
