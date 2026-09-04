"""
A "last known good" floor, not an exact-match snapshot: exact numbers shift
slightly with every regenerate+retrain (different seed draws, different
candidate pools), so pinning an exact value would make this test flaky by
design. What matters is that a future change doesn't silently regress the
model back toward random-chance performance (or worse than the current
real numbers) without anyone noticing. If evaluate.py is re-run and a
number below its floor is genuinely correct (a deliberate tradeoff, not a
bug), update the floor here in the same commit and say why -- don't just
raise the floor to make the test pass.

Current real numbers (2026-09-03, 552 train / 138 test complaints,
sigmoid calibration, 20 real localities/city): see PROGRESS_LOG.md.
"""

import json
from pathlib import Path

REPORT_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "evaluation_report.json"

# Deliberately below the current real numbers (advanced precision@5 ~0.486,
# precision@1 ~0.174) so ordinary sampling/seed variance across a re-run
# doesn't trip this -- it's a floor against real regression, not a pin.
MIN_ADVANCED_PRECISION_AT_5 = 0.30
MIN_ADVANCED_PRECISION_AT_1 = 0.08
MAX_ADVANCED_BRIER = 0.05


def _load_report():
    assert REPORT_PATH.exists(), f"no evaluation report at {REPORT_PATH} -- run `python -m ml.evaluate` first"
    return json.loads(REPORT_PATH.read_text())


def test_advanced_beats_baseline():
    report = _load_report()
    assert report["advanced"]["precision_at_5"] > report["baseline"]["precision_at_5"], (
        "the whole point of the graph/temporal/geo fusion is beating the tabular-only "
        "baseline -- if this regresses, something in the feature pipeline broke, not "
        "just 'got a bit worse'"
    )


def test_advanced_precision_above_floor():
    report = _load_report()
    assert report["advanced"]["precision_at_5"] >= MIN_ADVANCED_PRECISION_AT_5
    assert report["advanced"]["precision_at_1"] >= MIN_ADVANCED_PRECISION_AT_1


def test_advanced_calibration_is_reasonably_sharp():
    report = _load_report()
    assert report["advanced"]["brier_score"] <= MAX_ADVANCED_BRIER
