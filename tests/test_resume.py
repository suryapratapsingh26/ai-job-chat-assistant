import asyncio
import json
from io import BytesIO

from docx import Document

from backend.app.main import app
from backend.app.api import jobs as jobs_api
from backend.app.models.job import Job
from backend.app.services.resume_parser import ResumeProcessingError, parse_profile, parse_resume_document


def make_text_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 12 Tf", "72 740 Td"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -18 Td")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())
    return bytes(pdf)


def make_docx(lines: list[str]) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    content = BytesIO()
    document.save(content)
    return content.getvalue()


def call_asgi(method: str, path: str, body: bytes, content_type: str):
    async def call():
        delivered = False
        response_messages = []

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            response_messages.append(message)

        path_bytes = path.encode()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path_bytes,
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", content_type.encode()),
                (b"content-length", str(len(body)).encode()),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        start = next(message for message in response_messages if message["type"] == "http.response.start")
        response_body = b"".join(message.get("body", b"") for message in response_messages if message["type"] == "http.response.body")
        return start["status"], json.loads(response_body)

    return asyncio.run(call())


def multipart(file_name: str | None, file_type: str, content: bytes):
    boundary = "resume-test-boundary"
    filename_part = f'; filename="{file_name}"' if file_name is not None else ""
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"{filename_part}\r\n"
        f"Content-Type: {file_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return boundary, body


def test_extracts_profile_from_pdf():
    pdf = make_text_pdf([
        "Jane Doe",
        "Software Engineer",
        "jane.doe@example.com",
        "+1 415 555 0132",
        "Skills",
        "Python, React, SQL",
        "Experience",
        "Software Engineer at Example Co (2022-2025)",
        "Education",
        "B.S. Computer Science, Example University",
        "Projects",
        "Built a scheduling tool",
    ])
    profile = parse_resume_document("resume.pdf", "application/pdf", pdf)
    assert profile.name == "Jane Doe"
    assert profile.designation == "Software Engineer"
    assert profile.email == "jane.doe@example.com"
    assert profile.skills == ["Python", "React", "SQL"]
    assert "Example Co" in profile.experience
    assert profile.education == ["B.S. Computer Science, Example University"]
    assert profile.projects == ["Built a scheduling tool"]


def test_extracts_profile_from_docx():
    content = make_docx(["Alex Morgan", "Product Designer", "alex@example.com", "Skills: Figma; UX Research"])
    profile = parse_resume_document(
        "resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", content
    )
    assert profile.name == "Alex Morgan"
    assert profile.designation == "Product Designer"
    assert profile.skills == ["Figma", "UX Research"]


def test_unsupported_and_malformed_uploads_are_rejected():
    try:
        parse_resume_document("resume.txt", "text/plain", b"hello")
    except ResumeProcessingError as exc:
        assert exc.status_code == 415
        assert "PDF or DOCX" in str(exc)
    else:
        raise AssertionError("unsupported file was accepted")

    try:
        parse_resume_document("resume.pdf", "application/pdf", b"%PDF-1.4 not a valid PDF")
    except ResumeProcessingError as exc:
        assert exc.status_code == 422
        assert "PDF" in str(exc)
    else:
        raise AssertionError("malformed PDF was accepted")

    try:
        parse_resume_document("resume.pdf", "application/pdf", b" " * (10 * 1024 * 1024 + 1))
    except ResumeProcessingError as exc:
        assert exc.status_code == 413
        assert "10 MB" in str(exc)
    else:
        raise AssertionError("oversized file was accepted")


def test_empty_text_pdf_has_actionable_error():
    try:
        parse_resume_document("empty.pdf", "application/pdf", make_text_pdf([]))
    except ResumeProcessingError as exc:
        assert "No extractable text" in str(exc)
    else:
        raise AssertionError("empty text PDF was accepted")


def test_missing_profile_fields_are_optional():
    profile = parse_profile("contact@example.com")
    assert profile.name is None
    assert profile.email == "contact@example.com"
    assert profile.phone is None
    assert profile.skills == []
    assert profile.education == []
    assert profile.projects == []


def test_resume_parse_endpoint_returns_profile_and_clear_errors():
    boundary, body = multipart("resume.pdf", "application/pdf", make_text_pdf(["Sam Taylor", "sam@example.com"]))
    status, payload = call_asgi("POST", "/api/resume/parse", body, f"multipart/form-data; boundary={boundary}")
    assert status == 200
    assert payload["profile"]["name"] == "Sam Taylor"
    assert payload["profile"]["email"] == "sam@example.com"

    boundary, body = multipart("resume.pdf", "application/pdf", b"%PDF-1.4 broken")
    status, payload = call_asgi("POST", "/api/resume/parse", body, f"multipart/form-data; boundary={boundary}")
    assert status == 422
    assert "detail" in payload
    assert "Traceback" not in str(payload)

    boundary = "resume-test-boundary"
    body = f"--{boundary}--\r\n".encode()
    status, payload = call_asgi("POST", "/api/resume/parse", body, f"multipart/form-data; boundary={boundary}")
    assert status == 400
    assert "Choose a PDF or DOCX" in payload["detail"]


def test_parsed_resume_profile_produces_personalized_job_recommendations(monkeypatch):
    job = Job(
        job_id="software-engineer",
        title="Software Engineer",
        company="Example Co",
        location="Remote",
        experience="3+ years",
        skills=["Python", "React"],
        description="Build software products with Python and React.",
        source_link="https://example.com/software-engineer",
    )
    monkeypatch.setattr(jobs_api.dataset, "load", lambda: [job])

    boundary, body = multipart("resume.pdf", "application/pdf", make_text_pdf([
        "Jane Doe",
        "Software Engineer",
        "jane.doe@example.com",
        "Skills",
        "Python, React",
        "Experience",
        "Software Engineer at Example Co (2022-2025)",
        "Education",
        "B.S. Computer Science, Example University",
        "Projects",
        "Built a scheduling tool",
    ]))
    status, parsed = call_asgi(
        "POST", "/api/resume/parse", body,
        f"multipart/form-data; boundary={boundary}",
    )
    assert status == 200
    profile = parsed["profile"]
    assert profile["name"] == "Jane Doe"
    assert profile["skills"] == ["Python", "React"]

    status, match_response = call_asgi(
        "POST", "/api/jobs/match", json.dumps({"profile": profile}).encode(), "application/json",
    )
    assert status == 200
    recommendation = match_response["recommendations"][0]
    assert recommendation["job"]["job_id"] == "software-engineer"
    assert recommendation["match_score"] > 0
    assert recommendation["matched_skills"] == ["Python", "React"]
    assert recommendation["match_reasons"]
