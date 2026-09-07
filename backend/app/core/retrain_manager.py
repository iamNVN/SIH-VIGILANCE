"""
retrain_manager.py -- the automated retraining trigger the feedback loop
(api/feedback.py) was built to feed. Fires a real training run
(ml/train.py's train_and_save) in a background thread once enough new
investigator decisions have accumulated since the last retrain, then
hot-swaps core/model_registry's loaded artifacts so the very next
prediction uses the freshly-trained model -- no backend restart needed.

Honest scope: the trigger and the training run are both real -- this is
not a fake progress bar. What retraining does NOT do in this demo is
learn a different target FROM investigator feedback: ml/train.py still
fits against the generator's own ground-truth withdrawal_events, same as
before, because a real "was this actually where the money was withdrawn"
label doesn't exist for a synthetic complaint beyond what the generator
assigned. Investigator feedback is the real, honest TRIGGER (proof of
genuine ongoing usage, not a fabricated one) rather than a training LABEL
that reshapes the target -- in a real NCRP deployment, where
independently-verified case outcomes replace generator ground truth,
feedback would extend into the label itself, not just the schedule.
"""

import threading
from datetime import datetime, timezone

from sqlalchemy import func, select

RETRAIN_LABEL_THRESHOLD = 5

_state = {
    "last_retrained_at": None,       # iso string, or None if never retrained since this boot
    "last_retrain_label_count": 0,   # total feedback labels present at the time of the last retrain
    "in_progress": False,
    "last_error": None,
}
_lock = threading.Lock()


def _total_feedback_labels() -> int:
    from core.db import SessionLocal
    from models import InvestigatorFeedback

    db = SessionLocal()
    try:
        return db.execute(select(func.count(InvestigatorFeedback.id))).scalar_one()
    finally:
        db.close()


def status() -> dict:
    total = _total_feedback_labels()
    with _lock:
        labels_since = max(0, total - _state["last_retrain_label_count"])
        return {
            "last_retrained_at": _state["last_retrained_at"],
            "in_progress": _state["in_progress"],
            "last_error": _state["last_error"],
            "total_labels": total,
            "labels_since_last_retrain": labels_since,
            "threshold": RETRAIN_LABEL_THRESHOLD,
        }


def _run_retrain(trigger: str):
    from core import event_log
    from core.model_registry import registry
    from ml.train import train_and_save

    with _lock:
        if _state["in_progress"]:
            return
        _state["in_progress"] = True
        _state["last_error"] = None

    def log(msg):
        print(f"[retrain:{trigger}] {msg}")

    try:
        log("starting")
        # rebuild=False -- reuses the cached TRAIN feature matrix (the
        # underlying complaint/account/transaction set doesn't change in
        # this demo, see dataset_provider.py's docstring), so a retrain is
        # a real ~3s refit, not a full ~2.5min feature rebuild every time.
        train_and_save(log=log)
        registry.reload()
        with _lock:
            _state["last_retrained_at"] = datetime.now(timezone.utc).isoformat()
            _state["last_retrain_label_count"] = _total_feedback_labels()
            label_count = _state["last_retrain_label_count"]
        log("done -- registry reloaded, next prediction uses the new artifacts")
        event_log.log_event(
            "model_retrained",
            "Model retrained",
            f"Triggered by {trigger} decision volume -- {label_count} investigator labels captured to date.",
            None,
        )
    except Exception as e:
        with _lock:
            _state["last_error"] = str(e)
        log(f"FAILED: {e}")
    finally:
        with _lock:
            _state["in_progress"] = False


def maybe_trigger_retrain():
    """Called right after apply_decision() persists a new feedback label
    (complaints.py) -- checks whether enough real labels have accumulated
    since the last retrain and, if so, kicks off a real training run in a
    background thread. Non-blocking: the investigator's Approve/Reject
    click returns immediately either way."""
    st = status()
    if not st["in_progress"] and st["labels_since_last_retrain"] >= RETRAIN_LABEL_THRESHOLD:
        threading.Thread(target=_run_retrain, args=("threshold",), daemon=True).start()


def trigger_now() -> bool:
    """Manual override (Settings page's 'Retrain Now') -- the exact same
    real training run, just skipping the threshold wait so it's demoable
    on demand instead of needing 5 organic decisions to accumulate first.
    Returns False (no-op) if a retrain is already running."""
    if _state["in_progress"]:
        return False
    threading.Thread(target=_run_retrain, args=("manual",), daemon=True).start()
    return True
