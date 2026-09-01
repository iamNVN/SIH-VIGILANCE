"""evaluation.py -- serves the real, precomputed Section 18 experiment
results (ml/evaluate.py's evaluation_report.json) to the Analytics screen
(Blueprint Section 12 screen 7). Not recomputed per-request: the full
temporal-split experiment takes minutes (point-in-time graph + Louvain per
complaint); the dashboard reads the same numbers that were printed to the
terminal when `python -m ml.evaluate` was run."""

from fastapi import APIRouter, HTTPException

from core.model_registry import registry

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation")
def get_evaluation():
    if registry.evaluation_report is None:
        raise HTTPException(503, "no evaluation report yet -- run `python -m ml.evaluate` first")
    return registry.evaluation_report
