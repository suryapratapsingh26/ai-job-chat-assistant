import json
from datetime import timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.agents.orchestrator import JobChatOrchestrator
from backend.app.api import applications as applications_api
from backend.app.api import chat as chat_api
from backend.app.models.chat import ChatRequest, IntentAction, IntentPlan
from backend.app.models.job import Job
from backend.app.services.application_service import (
    ApplicationService,
    DuplicateApplicationError,
    JobNotFoundError,
)


def make_job(job_id: str = "job-1", title: str = "Backend Engineer") -> Job:
    return Job(
        job_id=job_id,
        title=title,
        company="Example Co",
        location="Remote",
        skills=["Python"],
        description="Build services.",
        source_link=f"https://example.com/{job_id}",
    )


def make_plan(intent: IntentAction, job_reference: int | None = None) -> IntentPlan:
    return IntentPlan(
        intent=intent,
        skills=[],
        location=None,
        remote=None,
        role=None,
        experience_level=None,
        replace_skills=False,
        clear_filters=False,
        explanation_index=None,
        job_reference=job_reference,
    )


class FakeParser:
    def __init__(self, plan: IntentPlan):
        self.plan = plan

    def parse(self, request: ChatRequest) -> IntentPlan:
        return self.plan


def test_application_is_persisted_with_timestamp_and_status(tmp_path):
    store = tmp_path / "applications.json"
    job = make_job()
    application = ApplicationService(store).apply(job.job_id, [job])

    assert application.job_id == job.job_id
    assert application.applied_at.tzinfo == timezone.utc
    assert application.status.value == "applied"
    saved = json.loads(store.read_text(encoding="utf-8"))
    assert saved == [{
        "job_id": job.job_id,
        "applied_at": application.applied_at.isoformat().replace("+00:00", "Z"),
        "status": "applied",
    }]
    persisted = ApplicationService(store).list_applications([job])
    assert persisted[0].job.job_id == job.job_id


def test_duplicate_application_and_invalid_job_are_rejected(tmp_path):
    service = ApplicationService(tmp_path / "applications.json")
    job = make_job()
    service.apply(job.job_id, [job])
    with pytest.raises(DuplicateApplicationError):
        service.apply(job.job_id, [job])
    with pytest.raises(JobNotFoundError):
        service.apply("missing", [job])


def test_empty_application_list_is_clean(tmp_path):
    assert ApplicationService(tmp_path / "applications.json").list_applications([make_job()]) == []


def test_application_api_handles_apply_duplicate_invalid_and_list(monkeypatch, tmp_path):
    job = make_job()
    monkeypatch.setattr(applications_api.dataset, "load", lambda: [job])
    monkeypatch.setattr(applications_api, "application_service", ApplicationService(tmp_path / "applications.json"))
    client = TestClient(main.app)

    empty = client.get("/api/applications")
    assert empty.status_code == 200 and empty.json() == {"applications": []}

    created = client.post("/api/applications", json={"job_id": job.job_id})
    assert created.status_code == 201
    assert created.json()["job"]["job_id"] == job.job_id
    assert created.json()["status"] == "applied"

    duplicate = client.post("/api/applications", json={"job_id": job.job_id})
    assert duplicate.status_code == 409
    missing = client.post("/api/applications", json={"job_id": "missing"})
    assert missing.status_code == 404
    listed = client.get("/api/applications")
    assert listed.json()["applications"][0]["job"]["job_id"] == job.job_id


def test_chat_apply_job_three_uses_visible_result_reference_and_lists_status(tmp_path):
    jobs = [
        make_job("job-1", "First Engineer"),
        make_job("job-2", "Second Engineer"),
        make_job("job-3", "Third Engineer"),
    ]
    service = ApplicationService(tmp_path / "applications.json")
    visible_job_ids = ["job-3", "job-1", "job-2"]
    chat = JobChatOrchestrator(FakeParser(make_plan(IntentAction.APPLY_JOB, 3)), service)
    applied = chat.handle(
        ChatRequest(message="apply to job 3", current_job_ids=visible_job_ids), jobs,
    )
    assert applied.jobs[0].job_id == "job-2"
    assert applied.applications[0].status.value == "applied"
    assert "Second Engineer" in applied.assistant_message

    duplicate = chat.handle(
        ChatRequest(message="apply to job 3", current_job_ids=visible_job_ids), jobs,
    )
    assert "already applied" in duplicate.assistant_message

    listed = JobChatOrchestrator(FakeParser(make_plan(IntentAction.LIST_APPLICATIONS)), service).handle(
        ChatRequest(message="show my applied jobs"), jobs,
    )
    assert listed.intent.value == "list_applications"
    assert [job.job_id for job in listed.jobs] == ["job-2"]
    assert listed.applications[0].status.value == "applied"


def test_chat_application_rejects_invalid_reference_and_resolves_this_when_unambiguous(tmp_path):
    job = make_job()
    service = ApplicationService(tmp_path / "applications.json")
    invalid = JobChatOrchestrator(FakeParser(make_plan(IntentAction.APPLY_JOB, 2)), service).handle(
        ChatRequest(message="apply to job 2", current_job_ids=[job.job_id]), [job],
    )
    assert "couldn't identify" in invalid.assistant_message

    applied = JobChatOrchestrator(FakeParser(make_plan(IntentAction.APPLY_JOB)), service).handle(
        ChatRequest(message="apply to this job", current_job_ids=[job.job_id]), [job],
    )
    assert applied.applications[0].job_id == job.job_id


def test_chat_selected_job_context_resolves_this_job_from_multiple_results(tmp_path):
    first, second = make_job("job-1"), make_job("job-2", "Data Engineer")
    chat = JobChatOrchestrator(
        FakeParser(make_plan(IntentAction.APPLY_JOB)),
        ApplicationService(tmp_path / "applications.json"),
    )
    response = chat.handle(
        ChatRequest(
            message="Apply to this job",
            current_job_ids=[first.job_id, second.job_id],
            selected_job_id=second.job_id,
        ),
        [first, second],
    )
    assert response.applications[0].job_id == second.job_id


def test_chat_endpoint_serializes_application_and_uses_visible_job_context(monkeypatch, tmp_path):
    first, second = make_job("job-1"), make_job("job-2", "Data Engineer")
    service = ApplicationService(tmp_path / "applications.json")
    orchestrator = JobChatOrchestrator(FakeParser(make_plan(IntentAction.APPLY_JOB, 2)), service)
    monkeypatch.setitem(main.app.dependency_overrides, chat_api.get_jobs, lambda: [first, second])
    monkeypatch.setitem(main.app.dependency_overrides, chat_api.get_orchestrator, lambda: orchestrator)
    client = TestClient(main.app)

    response = client.post("/api/chat", json={
        "message": "Apply to job 2",
        "current_job_ids": [first.job_id, second.job_id],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "apply_job"
    assert [job["job_id"] for job in body["jobs"]] == [second.job_id]
    assert body["applications"][0]["job"]["job_id"] == second.job_id
