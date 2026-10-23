from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from backend.app.services.normalization import clean_text, normalize_skills


class Job(BaseModel):
    """Normalized job record shared by the scraper and API."""

    model_config = ConfigDict(str_strip_whitespace=True)

    job_id: str
    title: str
    company: str
    location: str
    experience: str = ""
    skills: list[str] = Field(default_factory=list)
    description: str = ""
    source_link: HttpUrl

    @field_validator("job_id", "title", "company", "location", "experience", "description", mode="before")
    @classmethod
    def normalize_string_fields(cls, value):
        return clean_text(value)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skill_fields(cls, value):
        return normalize_skills(value)
