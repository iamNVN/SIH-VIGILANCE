"""
feed.py -- a cross-case top-1 prediction feed (no per-candidate SHAP explain,
unlike /predict/{id} -- this batches over many complaints, so it deliberately
skips the expensive explanation step and just returns the single top-ranked
call to action for each). Backs two sidebar views: Alerts (HIGH urgency only)
and Predictions (the full ranked feed) -- both real model output.

CACHING -- built once, appended to as new complaints arrive, never expired
---------------------------------------------------------------------------
This used to be a TTL cache (recompute the whole ~700-complaint batch every
90s). That meant whichever real request landed just after expiry paid the
full ~25-30s recompute synchronously -- verified live, this is exactly why
Command Center felt slow to load. The data underlying this feed only ever
changes one way while the backend is running: stream.py reveals ONE new
complaint at a time (Simulate Complaint / the replay socket), and nothing
else in this codebase mutates `Complaint.status` or `.revealed` (checked).
So there's no need to ever recompute complaints that were already scored --
`add_revealed_complaint_to_feed()` below scores just the newly-revealed one
and inserts it into the already-built list. The only two paths that touch
every complaint are the initial build (main.py's startup pre-warm, or
lazily on first request) and `/stream/reset` (a bulk un-reveal that
legitimately changes which complaints belong in the feed at all).
"""

import threading
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import SessionLocal
from core.model_registry import registry
from graph_engine.features import ADVANCED_FEATURE_COLUMNS, build_candidate_features
from models import Complaint

from .predict import _complaint_row, lift_urgency

router = APIRouter(tags=["feed"])

_cache = {"initialized": False, "feed": []}
# Guards both the initial full build (main.py's startup pre-warm racing a
# real request) and incremental updates (a reveal landing mid-rebuild) --
# either way, whoever's second just reuses/waits for the other's result
# instead of doing redundant work.
_lock = threading.Lock()


def _score_complaint(ds, complaint) -> Optional[dict]:
    """Scores ONE complaint -- shared by the initial full build and
    incremental single-complaint updates. `graph_as_of` is floored to this
    complaint's own calendar day (see build_candidate_features's docstring):
    cheap, and it can only omit that day's earlier events, never see past
    this complaint's own filing moment, unlike sharing one as_of across
    complaints filed months apart (which used to make a complaint's urgency
    depend on which OTHER complaints happened to be in the batch -- verified
    live, and it disagreed with what /predict/{id} showed for that same
    complaint)."""
    complaint_row = _complaint_row(complaint)
    graph_as_of = pd.Timestamp(complaint.filed_at).normalize()
    try:
        candidates = build_candidate_features(ds, complaint_row, graph_as_of=graph_as_of)
    except Exception:
        return None
    if candidates.empty:
        return None

    candidates["advanced_prob"] = registry.advanced_calibrated.predict_proba(candidates[ADVANCED_FEATURE_COLUMNS])[:, 1]
    top = candidates.sort_values("advanced_prob", ascending=False).iloc[0]
    confidence = float(top["advanced_prob"])
    n_candidates = len(candidates)

    return {
        "complaint_id": complaint.id,
        "victim_name": complaint.victim.name_fake if complaint.victim else None,
        "victim_city": complaint.victim.city if complaint.victim else None,
        "bank_name": complaint.bank_name,
        "amount_lost": complaint.amount_lost,
        "filed_at": complaint.filed_at.isoformat(),
        "top_prediction": {
            "withdrawal_point_id": int(top["withdrawal_point_id"]),
            "name": top["name"],
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "bank_name": top["bank_name"],
            "confidence": round(confidence, 4),
            "n_candidates": n_candidates,
            "urgency": lift_urgency(confidence, n_candidates),
        },
    }


def _compute_full_feed(limit_complaints: int = 700) -> list[dict]:
    # 700, not the dataset's ~690 total -- effectively "every currently
    # open+revealed complaint," not a recency window. A smaller cap (this
    # used to be 150) sounds like a reasonable "recent work queue" size, but
    # verified live: the dataset's fictional filed_at dates span a 3-month
    # range (Jun-Aug 2026), and the most-recent-150-by-filed_at window only
    # covers about 3 weeks of it -- so most of the genuinely HIGH-lift
    # complaints (scattered across the full 3 months, not clustered near the
    # end) fell outside the window entirely, making "High Risk Cases" read
    # as ~0 even though dozens of real HIGH complaints existed in the data.
    if not registry.ready:
        raise HTTPException(503, "models not trained yet -- run `python -m ml.train` first")

    db: Session = SessionLocal()
    try:
        complaints = db.execute(
            select(Complaint)
            .where(Complaint.status == "open", Complaint.revealed.is_(True))
            .order_by(Complaint.filed_at.desc())
            .limit(limit_complaints)
        ).scalars().all()
        if not complaints:
            return []

        ds = dataset_provider.get_dataset()
        items = [item for c in complaints if (item := _score_complaint(ds, c)) is not None]
        items.sort(key=lambda it: it["top_prediction"]["confidence"], reverse=True)
        return items
    finally:
        db.close()


def ensure_feed_built():
    """Builds the cache once if it never has been -- called eagerly by
    main.py's startup pre-warm thread, and lazily here as a fallback for
    whichever request lands first if pre-warming hasn't finished yet."""
    if _cache["initialized"]:
        return _cache["feed"]
    with _lock:
        if _cache["initialized"]:
            return _cache["feed"]
        feed = _compute_full_feed()
        _cache.update({"initialized": True, "feed": feed})
        return _cache["feed"]


def _cached_feed():
    return ensure_feed_built()


def cached_feed_if_warm():
    """Like `_cached_feed()` but never triggers the expensive initial build --
    returns the cached feed if it's already built, else None. For callers
    (like /stats) that want this data ONLY if it's already cheap to get."""
    return _cache["feed"] if _cache["initialized"] else None


def add_revealed_complaint_to_feed(complaint: Complaint):
    """Called by stream.py right after Simulate Complaint (or the replay
    socket) reveals one complaint. Scores just this one and inserts/updates
    it in the already-built cache -- its day's community graph is very
    likely already warm in graph_cache.py's LRU from the initial build, so
    this is cheap (a fraction of a second), unlike the old design's full
    ~700-complaint recompute on every single reveal."""
    if not _cache["initialized"]:
        return  # nothing built yet -- the eventual first build already includes this complaint
    db: Session = SessionLocal()
    try:
        ds = dataset_provider.get_dataset()
        item = _score_complaint(ds, complaint)
    finally:
        db.close()
    with _lock:
        feed = [it for it in _cache["feed"] if it["complaint_id"] != complaint.id]
        if item is not None:
            feed.append(item)
        feed.sort(key=lambda it: it["top_prediction"]["confidence"], reverse=True)
        _cache["feed"] = feed


def remove_complaint_from_feed(complaint_id: int):
    """Called by complaints.py right after Approve/Reject moves a complaint
    off status='open' -- it no longer belongs in this feed (which only ever
    holds open complaints), so it must be dropped explicitly rather than
    left to look scored/HIGH until the next full rebuild."""
    if not _cache["initialized"]:
        return
    with _lock:
        _cache["feed"] = [it for it in _cache["feed"] if it["complaint_id"] != complaint_id]


def rebuild_feed_in_background():
    """Called by stream.py's /stream/reset -- a bulk un-reveal legitimately
    changes which complaints belong in the feed at all (not just one new
    arrival), so this is the one case that still needs a full recompute.
    Runs in a background thread so the reset endpoint itself doesn't block
    on it; the still-stale cache keeps serving in the meantime."""
    def _rebuild():
        feed = _compute_full_feed()
        with _lock:
            _cache.update({"initialized": True, "feed": feed})

    threading.Thread(target=_rebuild, daemon=True).start()


@router.get("/feed/predictions")
def predictions_feed(limit: int = 40, city: Optional[str] = None):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    return {"items": items[: min(limit, 100)]}


@router.get("/feed/alerts")
def alerts_feed(limit: int = 40, city: Optional[str] = None, sort: str = "confidence"):
    items = _cached_feed()
    if city:
        items = [it for it in items if it["victim_city"] == city]
    high = [it for it in items if it["top_prediction"]["urgency"] == "HIGH"]
    if sort == "recent":
        # Command Center's "Recent High Risk Complaints" preview means
        # recent, not "the model's single most confident calls" (the
        # default -- what the dedicated Alerts page wants).
        high = sorted(high, key=lambda it: it["filed_at"], reverse=True)
    # `total` is the real, complete HIGH-urgency count before slicing to
    # `limit` -- Command Center's "High Risk Cases" stat card uses this
    # (this endpoint's own fetch, already happening for the alerts table)
    # rather than a second, separate count.
    return {"items": high[: min(limit, 100)], "total": len(high)}
