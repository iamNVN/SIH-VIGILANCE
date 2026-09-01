"""
model_registry.py -- loads the joblib artifacts produced by `ml/train.py`
once per process and hands them out to the API routers. If artifacts are
missing (train.py hasn't been run yet), the API still starts -- predict/
explain endpoints raise a clear 503 instead of crashing at import time,
so `GET /health` and complaint intake still work independently.
"""

import json
from pathlib import Path
from typing import Optional

import joblib

from core.config import MODEL_ARTIFACTS_DIR


class ModelRegistry:
    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = Path(artifacts_dir)
        self.baseline_raw = None
        self.baseline_calibrated = None
        self.advanced_raw = None
        self.advanced_calibrated = None
        self.metadata: Optional[dict] = None
        self.evaluation_report: Optional[dict] = None
        self._load()

    def _load(self):
        try:
            self.baseline_raw = joblib.load(self.artifacts_dir / "baseline_raw.joblib")
            self.baseline_calibrated = joblib.load(self.artifacts_dir / "baseline_calibrated.joblib")
            self.advanced_raw = joblib.load(self.artifacts_dir / "advanced_raw.joblib")
            self.advanced_calibrated = joblib.load(self.artifacts_dir / "advanced_calibrated.joblib")
            with open(self.artifacts_dir / "metadata.json") as f:
                self.metadata = json.load(f)
        except FileNotFoundError:
            pass  # ml/train.py hasn't been run yet -- endpoints report 503 until it has

        eval_path = self.artifacts_dir / "evaluation_report.json"
        if eval_path.exists():
            with open(eval_path) as f:
                self.evaluation_report = json.load(f)

    @property
    def ready(self) -> bool:
        return self.advanced_calibrated is not None and self.baseline_calibrated is not None


registry = ModelRegistry(MODEL_ARTIFACTS_DIR)
