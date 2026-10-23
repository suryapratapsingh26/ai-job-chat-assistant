import json
from pathlib import Path

from backend.app.models import Job

DEFAULT_DATASET = Path(__file__).resolve().parents[3] / "data" / "jobs.json"


class JobDataset:
    def __init__(self, path: Path = DEFAULT_DATASET):
        self.path = Path(path)

    def load(self) -> list[Job]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as dataset_file:
            records = json.load(dataset_file)
        if not isinstance(records, list):
            raise ValueError("Job dataset must contain a JSON array")
        return [Job.model_validate(record) for record in records]
