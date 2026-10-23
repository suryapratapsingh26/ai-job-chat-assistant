"""Deterministic, explainable matching between parsed profiles and job records."""

import re
import unicodedata
from collections.abc import Sequence

from backend.app.models.job import Job
from backend.app.models.matching import (
    JobRecommendation,
    MatchScoringDetails,
)
from backend.app.models.resume import ResumeProfile

WEIGHTS = {"skills": 60, "title": 25, "experience": 10, "description": 5}
STOP_WORDS = {
    "about", "after", "also", "been", "being", "between", "both", "could", "from", "have", "into",
    "more", "most", "other", "over", "their", "there", "these", "this", "those", "through", "under",
    "using", "very", "with", "work", "working", "years", "year", "experience", "responsibilities",
    "requirements", "required", "skills", "knowledge", "ability", "strong", "good", "team", "teams",
    "will", "your", "you", "and", "for", "the", "our", "are", "was", "who", "job", "role",
}
ROLE_TOKEN_ALIASES = {"engineering": "engineer", "developers": "developer", "developing": "developer"}
YEAR_RE = re.compile(r"(?<!\d)(\d{1,2})(?:\s*[-–to]+\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)(?!\w)", re.I)
DATE_RANGE_RE = re.compile(r"\b((?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current)\b", re.I)
EXPERIENCE_REQUIREMENT_RE = re.compile(
    r"(?:(\d{1,2})(?:\s*[-–to]+\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)"
    r"\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience)"
    r"|(?:experience.{0,45}?(\d{1,2})(?:\s*[-–to]+\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?))",
    re.I,
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = value.replace("&", " and ").replace("+", " plus ")
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _tokens(value: str, *, title: bool = False) -> set[str]:
    tokens = set(normalize_text(value).split())
    tokens -= {"m", "w", "d"}
    if title:
        tokens = {ROLE_TOKEN_ALIASES.get(token, token) for token in tokens}
    return tokens


def _skill_matches(profile_skills: list[str], job: Job) -> list[str]:
    job_skill_keys = {normalize_text(skill) for skill in job.skills if normalize_text(skill)}
    description = f" {normalize_text(job.description)} "
    matched = []
    seen = set()
    for skill in profile_skills:
        key = normalize_text(skill)
        if not key or key in seen:
            continue
        # Exact normalized job skill or a whole-phrase match in the description.
        if key in job_skill_keys or f" {key} " in description:
            matched.append(skill.strip())
            seen.add(key)
    return matched


def _unique_skills(skills: list[str]) -> list[str]:
    unique = []
    seen = set()
    for skill in skills:
        key = normalize_text(skill)
        if key and key not in seen:
            unique.append(skill)
            seen.add(key)
    return unique


def _title_score(designation: str, title: str) -> float | None:
    target = _tokens(designation, title=True)
    if not target:
        return None
    job_tokens = _tokens(title, title=True)
    return len(target & job_tokens) / len(target)


def _experience_years(text: str | None, *, requirement: bool = False) -> float | None:
    if not text:
        return None
    explicit = YEAR_RE.search(text)
    if explicit:
        lower = float(explicit.group(1))
        upper = float(explicit.group(2)) if explicit.group(2) else lower
        return (lower + upper) / 2 if requirement and explicit.group(2) else lower
    if requirement:
        return None
    ranges = []
    for start, end in DATE_RANGE_RE.findall(text):
        start_year = int(start)
        end_year = 2026 if end.casefold() in {"present", "current"} else int(end)
        if start_year <= end_year <= 2026:
            ranges.append(end_year - start_year)
    return float(max(ranges)) if ranges else None


def _experience_score(candidate: float, required: float) -> float:
    if candidate >= required:
        return 1.0
    if required - candidate <= 1:
        return 0.5
    return 0.0


def _job_experience_requirement(job: Job) -> float | None:
    explicit_field = _experience_years(job.experience, requirement=True)
    if explicit_field is not None:
        return explicit_field
    match = EXPERIENCE_REQUIREMENT_RE.search(job.description)
    if not match:
        return None
    first = match.group(1) or match.group(3)
    second = match.group(2) or match.group(4)
    lower = float(first)
    upper = float(second) if second else lower
    return (lower + upper) / 2 if second else lower


def _description_score(profile: ResumeProfile, description: str) -> float | None:
    candidate_text = " ".join([*(profile.projects or []), profile.experience or ""])
    candidate_tokens = {
        token for token in _tokens(candidate_text)
        if len(token) >= 4 and token not in STOP_WORDS and not token.isdigit()
    }
    if not candidate_tokens:
        return None
    job_tokens = _tokens(description)
    return len(candidate_tokens & job_tokens) / len(candidate_tokens)


def _reasons(
    profile_skills: list[str],
    matched_skills: list[str],
    title_score: float | None,
    experience_score: float | None,
    skills_score: float | None,
) -> list[str]:
    reasons = []
    if profile_skills:
        reasons.append(f"Matches {len(matched_skills)} of your {len(profile_skills)} listed skills")
        if skills_score is not None and skills_score >= 0.5:
            reasons.append("Strong overlap with your technical skills")
    if title_score is not None and title_score > 0:
        reasons.append(
            "Job title aligns with your designation"
            if title_score >= 0.5 else "Job title shares terms with your designation"
        )
    if experience_score is not None and experience_score >= 0.5:
        reasons.append("Experience level appears compatible")
    return reasons


def match_jobs(
    profile: ResumeProfile,
    jobs: Sequence[Job],
    limit: int = 24,
) -> tuple[list[JobRecommendation], int]:
    """Score jobs from available profile signals and return ordered unique matches."""
    recommendations = []
    seen_ids = set()
    candidate_years = _experience_years(profile.experience)

    for job in jobs:
        if not job.job_id or job.job_id in seen_ids:
            continue
        seen_ids.add(job.job_id)

        candidate_skills = _unique_skills(profile.skills)
        matched_skills = _skill_matches(candidate_skills, job)
        skills_score = len(matched_skills) / len(candidate_skills) if candidate_skills else None
        title_score = _title_score(profile.designation, job.title) if profile.designation else None

        required_years = _job_experience_requirement(job)
        experience_score = (
            _experience_score(candidate_years, required_years)
            if candidate_years is not None and required_years is not None
            else None
        )
        description_score = _description_score(profile, job.description)
        details = {
            "skills": skills_score,
            "title": title_score,
            "experience": experience_score,
            "description": description_score,
        }
        active_weight = sum(WEIGHTS[name] for name, score in details.items() if score is not None)
        if not active_weight:
            continue
        score = round(100 * sum(WEIGHTS[name] * value for name, value in details.items() if value is not None) / active_weight)
        if score <= 0:
            continue
        reasons = _reasons(candidate_skills, matched_skills, title_score, experience_score, skills_score)
        if description_score is not None and description_score > 0 and len(reasons) < 3:
            reasons.append("Resume experience or projects share relevant terms with the job description")
        if not reasons:
            reasons.append("Some experience or project terms overlap with the job description")
        recommendations.append(JobRecommendation(
            job=job,
            match_score=max(0, min(100, score)),
            matched_skills=matched_skills,
            match_reasons=reasons,
            scoring_details=MatchScoringDetails(**details),
        ))

    recommendations.sort(key=lambda item: (-item.match_score, item.job.job_id))
    total_matches = len(recommendations)
    return recommendations[:max(0, limit)], total_matches
