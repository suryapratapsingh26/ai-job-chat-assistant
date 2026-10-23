import asyncio
import json

from backend.app import main
from backend.app.api import jobs as jobs_api
from backend.app.models import Job, ResumeProfile
from backend.app.services.job_matcher import match_jobs


def job(job_id: str, title: str, skills: list[str], experience: str = "", description: str = "") -> Job:
    return Job(
        job_id=job_id,
        title=title,
        company="Example Co",
        location="Remote",
        experience=experience,
        skills=skills,
        description=description,
        source_link=f"https://example.com/jobs/{job_id}",
    )


def call_asgi(method: str, path: str, payload: dict | None = None):
    async def call():
        body = json.dumps(payload).encode() if payload is not None else b""
        delivered = False
        messages = []

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": method, "scheme": "http", "path": path.split("?", 1)[0],
            "raw_path": path.split("?", 1)[0].encode(),
            "query_string": path.split("?", 1)[1].encode() if "?" in path else b"", "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode())],
            "client": ("testclient", 50000), "server": ("testserver", 80),
        }
        await main.app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        response = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return start["status"], json.loads(response)

    return asyncio.run(call())


def test_strong_skill_match_is_high_and_returns_exact_matches_and_reasons():
    profile = ResumeProfile(skills=["Python", "JavaScript", "SQL"])
    listing = job("strong", "Backend Engineer", ["Python", "JavaScript", "SQL"])
    recommendations, total = match_jobs(profile, [listing])
    match = recommendations[0]
    assert total == 1
    assert match.match_score == 100
    assert match.matched_skills == ["Python", "JavaScript", "SQL"]
    assert "Matches 3 of your 3 listed skills" in match.match_reasons
    assert match.scoring_details.skills == 1


def test_skill_match_does_not_use_ambiguous_substrings():
    profile = ResumeProfile(skills=["Java", "SQL"])
    listing = job("boundaries", "Developer", ["JavaScript", "NoSQL"])
    recommendations, total = match_jobs(profile, [listing])
    assert recommendations == []
    assert total == 0


def test_designation_alignment_increases_score_and_is_explained():
    profile = ResumeProfile(designation="Software Engineer", skills=["Python"])
    aligned = job("aligned", "Software Engineer", ["Python"])
    unrelated = job("other", "Product Designer", ["Python"])
    results, _ = match_jobs(profile, [unrelated, aligned])
    by_id = {item.job.job_id: item for item in results}
    assert by_id["aligned"].match_score > by_id["other"].match_score
    assert by_id["aligned"].scoring_details.title == 1
    assert "Job title aligns with your designation" in by_id["aligned"].match_reasons


def test_compatible_experience_is_scored_and_reported():
    listing = job("experience", "Engineer", ["Python"], "3+ years", "Requires at least 3 years of experience.")
    compatible = ResumeProfile(skills=["Python"], experience="5 years of experience")
    incompatible = ResumeProfile(skills=["Python"], experience="0 years of experience")
    compatible_result, _ = match_jobs(compatible, [listing])
    incompatible_result, _ = match_jobs(incompatible, [listing])
    assert compatible_result[0].scoring_details.experience == 1
    assert "Experience level appears compatible" in compatible_result[0].match_reasons
    assert compatible_result[0].match_score > incompatible_result[0].match_score


def test_company_tenure_is_not_mistaken_for_job_experience_requirement():
    profile = ResumeProfile(skills=["Python"], experience="5 years of experience")
    listing = job("tenure", "Engineer", ["Python"], description="The company has over 20 years in the industry.")
    recommendations, _ = match_jobs(profile, [listing])
    assert recommendations[0].scoring_details.experience is None


def test_missing_resume_fields_do_not_crash_and_can_match_by_other_signals():
    profile = ResumeProfile()
    listing = job("project", "Generalist", [], description="Built analytics systems with distributed event processing.")
    recommendations, total = match_jobs(profile, [listing])
    assert total == 0
    assert recommendations == []

    profile = ResumeProfile(projects=["Built distributed event processing systems"])
    recommendations, total = match_jobs(profile, [listing])
    assert total == 1
    assert recommendations[0].match_score > 0
    assert recommendations[0].match_reasons


def test_recommendations_sort_by_score_then_stable_id():
    profile = ResumeProfile(skills=["Python", "SQL"])
    listings = [
        job("z-one", "Developer", ["Python"]),
        job("a-two", "Developer", ["Python"]),
        job("top", "Developer", ["Python", "SQL"]),
    ]
    recommendations, _ = match_jobs(profile, listings)
    assert [item.job.job_id for item in recommendations] == ["top", "a-two", "z-one"]


def test_duplicate_ids_are_returned_once_and_limit_keeps_total():
    profile = ResumeProfile(skills=["Python"])
    listing = job("duplicate", "Engineer", ["Python"])
    another = job("another", "Developer", ["Python"])
    recommendations, total = match_jobs(profile, [listing, listing, another], limit=1)
    assert len(recommendations) == 1
    assert total == 2


def test_empty_and_no_overlap_inputs_return_no_recommendations():
    profile = ResumeProfile(skills=["Rust"])
    listings = [job("one", "Accountant", ["Finance"])]
    assert match_jobs(profile, listings) == ([], 0)
    assert match_jobs(ResumeProfile(), listings) == ([], 0)
    assert match_jobs(profile, []) == ([], 0)


def test_match_endpoint_returns_ordered_jobs_details_and_rejects_bad_requests(monkeypatch):
    monkeypatch.setattr(jobs_api.dataset, "load", lambda: [
        job("partial", "Engineer", ["Python"]),
        job("full", "Engineer", ["Python", "SQL"]),
    ])
    payload = {"profile": {"designation": "Engineer", "skills": ["Python", "SQL"]}}
    status, response = call_asgi("POST", "/api/jobs/match?limit=1", payload)
    assert status == 200
    assert response["total_matches"] == 2
    assert len(response["recommendations"]) == 1
    recommendation = response["recommendations"][0]
    assert recommendation["job"]["job_id"] == "full"
    assert recommendation["match_score"] > 0
    assert recommendation["matched_skills"] == ["Python", "SQL"]
    assert recommendation["match_reasons"]
    assert recommendation["scoring_details"]["skills"] == 1

    status, _ = call_asgi("POST", "/api/jobs/match", {"profile": {"skills": [1]}})
    assert status == 422
    status, _ = call_asgi("POST", "/api/jobs/match?limit=101", payload)
    assert status == 422
    status, _ = call_asgi("POST", "/api/jobs/match", {})
    assert status == 422


def test_existing_health_and_jobs_endpoints_remain_usable(monkeypatch):
    monkeypatch.setattr(main.dataset, "load", lambda: [job("existing", "Engineer", ["Python"])])
    status, health = call_asgi("GET", "/health")
    assert status == 200
    assert health == {"status": "ok"}
    status, page = call_asgi("GET", "/api/jobs?offset=0&limit=1")
    assert status == 200
    assert page["total"] == 1
    assert page["jobs"][0]["job_id"] == "existing"
