"""Deterministic job filtering shared by conversational searches."""

from collections.abc import Sequence

from backend.app.models.chat import ChatFilters, ExperienceLevel
from backend.app.models.job import Job
from backend.app.models.matching import JobRecommendation
from backend.app.services.job_matcher import normalize_text

MAX_CHAT_RESULTS = 24
EXPERIENCE_LEVELS = {
    "intern": {"intern", "internship", "graduate", "trainee"},
    "entry": {"entry", "junior", "jr", "associate", "graduate", "intern"},
    "junior": {"junior", "jr", "entry", "associate", "intern"},
    "mid": {"mid", "intermediate", "regular"},
    "senior": {"senior", "sr", "lead", "principal", "staff", "head"},
    "lead": {"lead", "principal", "staff", "head", "director"},
}


def _has_phrase(haystack: str, phrase: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    return bool(normalized_phrase) and f" {normalized_phrase} " in f" {normalize_text(haystack)} "


def _is_remote(job: Job) -> bool:
    return (
        _has_phrase(job.location, "remote")
        or any(normalize_text(skill) == "remote" for skill in job.skills)
        or _has_phrase(job.title, "remote")
    )


def _matches_experience(job: Job, level: ExperienceLevel) -> bool:
    expected = EXPERIENCE_LEVELS.get(normalize_text(level))
    if not expected:
        return False
    title_tokens = set(normalize_text(job.title).split())
    experience_tokens = set(normalize_text(job.experience).split())
    return bool((title_tokens | experience_tokens) & expected)


def matches_filters(job: Job, filters: ChatFilters) -> bool:
    if filters.remote is not None and _is_remote(job) is not filters.remote:
        return False
    if filters.location and not _has_phrase(job.location, filters.location):
        return False
    if filters.role:
        role_tokens = set(normalize_text(filters.role).split())
        title_tokens = set(normalize_text(job.title).split())
        if not role_tokens or len(role_tokens & title_tokens) / len(role_tokens) < 0.5:
            return False
    if filters.experience_level and not _matches_experience(job, filters.experience_level):
        return False
    if filters.skills:
        search_text = " ".join([*job.skills, job.description])
        if not all(_has_phrase(search_text, skill) for skill in filters.skills):
            return False
    return True


def filter_jobs(jobs: Sequence[Job], filters: ChatFilters, limit: int = MAX_CHAT_RESULTS) -> list[Job]:
    seen = set()
    filtered = []
    for job in jobs:
        if job.job_id in seen or not matches_filters(job, filters):
            continue
        seen.add(job.job_id)
        filtered.append(job)
    return filtered[:max(0, min(limit, MAX_CHAT_RESULTS))]


def filter_recommendations(
    recommendations: Sequence[JobRecommendation],
    filters: ChatFilters,
    limit: int = MAX_CHAT_RESULTS,
) -> list[JobRecommendation]:
    return [item for item in recommendations if matches_filters(item.job, filters)][:max(0, min(limit, MAX_CHAT_RESULTS))]
