"""Collect jobs from public, unauthenticated JSON feeds."""

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.models import Job
from backend.app.services.normalization import normalize_company, normalize_location, normalize_skills, normalize_url

LOG = logging.getLogger("job_scraper")
DEFAULT_OUTPUT = ROOT / "data" / "jobs.json"
USER_AGENT = "AIJobChatAssistant/1.0 (public job feed collector)"


@dataclass(frozen=True)
class ScraperConfig:
    max_jobs: int = 1800
    request_delay: float = 0.5
    timeout: float = 20
    retries: int = 3
    max_pages: int = 100
    greenhouse_boards: tuple[str, ...] = ()

    @classmethod
    def from_env(cls):
        return cls(
            max_jobs=max(1, int(os.getenv("SCRAPER_MAX_JOBS", "1800"))),
            request_delay=max(0, float(os.getenv("SCRAPER_REQUEST_DELAY", "0.5"))),
            timeout=max(1, float(os.getenv("SCRAPER_TIMEOUT", "20"))),
            retries=max(0, int(os.getenv("SCRAPER_RETRIES", "3"))),
            max_pages=max(1, int(os.getenv("SCRAPER_MAX_PAGES", "100"))),
            greenhouse_boards=tuple(x.strip() for x in os.getenv("GREENHOUSE_BOARDS", "").split(",") if x.strip()),
        )


def fetch_json(url: str, config: ScraperConfig):
    for attempt in range(config.retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= config.retries:
                raise
            wait = min(2 ** attempt, 8)
            LOG.warning("Request failed (%s); retrying in %ss: %s", exc, wait, url)
            time.sleep(wait)


def stable_job_id(source: str, identifier: str, fields: dict) -> str:
    identity = identifier or "|".join(fields.get(key, "") for key in ("title", "company", "location", "source_link"))
    digest = hashlib.sha256(f"{source}:{identity}".encode("utf-8")).hexdigest()[:20]
    return f"{source}-{digest}"


def normalize_record(source: str, item: dict, identifier: str = "") -> Job | None:
    title = " ".join(str(item.get("title") or "").split())
    company = normalize_company(item.get("company") or item.get("company_name"))
    raw_location = item.get("location")
    if isinstance(raw_location, dict):
        raw_location = raw_location.get("name") or raw_location.get("location")
    location = normalize_location(raw_location) or ("Remote" if item.get("remote") else "Unspecified")
    source_link = normalize_url(item.get("url") or item.get("absolute_url"))
    if not title or not company or not source_link:
        LOG.warning("Skipping %s listing with missing title/company/valid URL", source)
        return None
    description = item.get("description") or item.get("content") or ""
    skills = item.get("skills") or item.get("tags") or []
    if isinstance(skills, str):
        skills = [skills]
    fields = {"title": title, "company": company, "location": location, "source_link": source_link}
    return Job(
        job_id=stable_job_id(source, str(identifier or item.get("slug") or item.get("id") or source_link), fields),
        title=title,
        company=company,
        location=location,
        experience=str(item.get("experience") or ""),
        skills=normalize_skills(skills),
        description=description,
        source_link=source_link,
    )


def arbeitnow_jobs(config: ScraperConfig):
    url = "https://www.arbeitnow.com/api/job-board-api"
    seen_pages = set()
    for _ in range(config.max_pages):
        if not url or url in seen_pages:
            break
        seen_pages.add(url)
        try:
            payload = fetch_json(url, config)
        except Exception as exc:
            LOG.error("Arbeitnow page failed: %s", exc)
            break
        for item in payload.get("data", []):
            job = normalize_record("arbeitnow", item, item.get("slug", ""))
            if job:
                yield job
        links = payload.get("links") or {}
        next_url = links.get("next")
        url = urljoin(url, next_url) if next_url else ""
        if url:
            time.sleep(config.request_delay)


def greenhouse_jobs(config: ScraperConfig):
    for board in config.greenhouse_boards:
        url = f"https://boards-api.greenhouse.io/v1/boards/{quote(board)}/jobs?content=true"
        try:
            payload = fetch_json(url, config)
        except Exception as exc:
            LOG.error("Greenhouse board %s failed: %s", board, exc)
            continue
        for item in payload.get("jobs", []):
            item["company"] = board.replace("-", " ").title()
            job = normalize_record("greenhouse-" + board, item, str(item.get("id", "")))
            if job:
                yield job
        time.sleep(config.request_delay)


def deduplicate_jobs(jobs):
    unique = []
    seen_ids = set()
    seen_fingerprints = set()
    duplicates = 0
    for job in jobs:
        fingerprint = "|".join((job.title.casefold(), job.company.casefold(), job.location.casefold(), str(job.source_link).casefold()))
        if job.job_id in seen_ids or fingerprint in seen_fingerprints:
            duplicates += 1
            continue
        unique.append(job)
        seen_ids.add(job.job_id)
        seen_fingerprints.add(fingerprint)
    return unique, duplicates


def collect_jobs(config: ScraperConfig):
    collected = []
    sources = [arbeitnow_jobs(config), greenhouse_jobs(config)]
    for source in sources:
        for job in source:
            collected.append(job)
            if len(collected) % 100 == 0:
                LOG.info("Collected %d source records", len(collected))
    unique, duplicate_count = deduplicate_jobs(collected)
    LOG.info("Deduplicated %d source records; removed %d duplicates", len(collected), duplicate_count)
    return unique[:config.max_jobs]


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    config = ScraperConfig.from_env()
    output = Path(os.getenv("JOBS_OUTPUT", str(DEFAULT_OUTPUT)))
    jobs = collect_jobs(config)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    LOG.info("Wrote %d unique jobs to %s", len(jobs), output)


if __name__ == "__main__":
    main()
