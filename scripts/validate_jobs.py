"""Validate jobs.json independently from the API server."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "jobs.json"
REQUIRED = ("job_id", "title", "company", "location", "experience", "skills", "description", "source_link")


def validate_dataset(path=DEFAULT_DATASET):
    with Path(path).open(encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list):
        raise ValueError("Dataset must be a JSON array")
    errors = []
    ids = set()
    fingerprints = set()
    duplicate_count = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record {index}: expected object")
            continue
        missing = [key for key in REQUIRED if key not in record]
        if missing:
            errors.append(f"record {index}: missing {', '.join(missing)}")
            continue
        job_id = record["job_id"]
        if not isinstance(job_id, str) or not job_id:
            errors.append(f"record {index}: job_id must be non-empty")
        elif job_id in ids:
            errors.append(f"record {index}: duplicate job_id {job_id}")
        else:
            ids.add(job_id)
        if not record["title"] or not record["company"]:
            errors.append(f"record {index}: title and company must be non-empty")
        if not isinstance(record["skills"], list) or any(not isinstance(skill, str) for skill in record["skills"]):
            errors.append(f"record {index}: skills must be a list of strings")
        parts = urlsplit(str(record["source_link"]))
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            errors.append(f"record {index}: invalid source_link")
        fingerprint = (str(record["title"]).casefold(), str(record["company"]).casefold(), str(record["location"]).casefold(), str(record["source_link"]).casefold())
        if fingerprint in fingerprints:
            duplicate_count += 1
        else:
            fingerprints.add(fingerprint)
    return len(records), duplicate_count, errors


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    try:
        count, duplicates, errors = validate_dataset(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Validation failed: {exc}")
        return 1
    print(f"Records: {count}; duplicate fingerprints: {duplicates}")
    if errors:
        print("Validation errors:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Dataset is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
