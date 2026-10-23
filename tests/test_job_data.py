import json
import tempfile
import unittest
from pathlib import Path

from backend.app.models import Job
from backend.app.services.job_dataset import JobDataset
from backend.app.services.normalization import normalize_skills, normalize_url
from scripts.scrape_jobs import deduplicate_jobs, normalize_record, stable_job_id
from scripts.validate_jobs import validate_dataset


class JobDataTests(unittest.TestCase):
    def test_model_normalizes_fields(self):
        job = Job(job_id="x", title="  Data   Engineer ", company=" Acme ", location="Remote", source_link="https://example.com/jobs/1", skills=[" Python ", "python"])
        self.assertEqual(job.title, "Data Engineer")
        self.assertEqual(job.skills, ["Python"])

    def test_normalization(self):
        self.assertEqual(normalize_skills(["Python", " python ", "SQL"]), ["Python", "SQL"])
        self.assertEqual(normalize_url("HTTPS://EXAMPLE.COM/jobs/1/#apply"), "https://example.com/jobs/1")

    def test_stable_id_and_record_parsing(self):
        fields = {"title": "Engineer", "company": "Acme", "location": "Remote", "source_link": "https://example.com/1"}
        self.assertEqual(stable_job_id("feed", "123", fields), stable_job_id("feed", "123", fields))
        parsed = normalize_record("feed", {"title": " Engineer ", "company_name": " Acme ", "location": "Remote", "url": "https://example.com/1", "tags": ["Python"]}, "123")
        self.assertEqual(parsed.company, "Acme")
        self.assertEqual(parsed.skills, ["Python"])

    def test_deduplicates_by_stable_id_and_listing_fingerprint(self):
        first = normalize_record("feed", {"title": "Engineer", "company": "Acme", "location": "Remote", "url": "https://example.com/1"}, "1")
        same_listing_different_id = normalize_record("other", {"title": "Engineer", "company": "Acme", "location": "Remote", "url": "https://example.com/1"}, "2")
        unique, duplicates = deduplicate_jobs([first, first, same_listing_different_id])
        self.assertEqual(len(unique), 1)
        self.assertEqual(duplicates, 2)

    def test_dataset_validation_and_loading(self):
        record = {"job_id": "a", "title": "Engineer", "company": "Acme", "location": "Remote", "experience": "", "skills": [], "description": "", "source_link": "https://example.com/job"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "jobs.json"
            path.write_text(json.dumps([record]), encoding="utf-8")
            count, duplicates, errors = validate_dataset(path)
            self.assertEqual((count, duplicates, errors), (1, 0, []))
            self.assertEqual(JobDataset(path).load()[0].job_id, "a")
            path.write_text(json.dumps([record, record]), encoding="utf-8")
            self.assertEqual(validate_dataset(path)[1], 1)


if __name__ == "__main__":
    unittest.main()
