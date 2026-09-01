"""
graph_cache.py -- memoizes the (point-in-time graph, Louvain communities)
pair, shared across every caller that needs it.

WHY THIS EXISTS: `/predict`, `/graph`, `/related`, and `/explain` each need
a point-in-time graph + community assignment for the SAME complaint's SAME
`as_of` (its `filed_at`, per the point-in-time discipline in Section 18).
Before this, each endpoint independently called `build_graph` +
`detect_communities` from scratch -- visiting the Investigation tab alone
(which calls all four) triggered four full graph rebuilds and four Louvain
runs for identical input. Under React 18 StrictMode's dev-mode double-effect
invocation this doubled again, and the resulting pile-up of concurrent
CPU-bound (GIL-bound) work was the actual cause of requests appearing to
"hang" in the browser -- caught while visually verifying the frontend, not
a theoretical concern.

Cache key is `(id(dataset), as_of_ns)` -- `id(dataset)` rather than a
version counter deliberately, so this stays correct for BOTH callers of
`build_candidate_features`: the live API (whose `Dataset` comes from
`core.dataset_provider`, replaced wholesale on `refresh()`, which changes
its `id()` for free) AND the offline `ml/evaluate.py` / `ml/train.py` path
(whose `Dataset` is loaded straight from CSVs and never touches
`dataset_provider` at all). Keying on the dataset object's own identity
means this module has no dependency on either caller's notion of
"version" -- a new/different Dataset object always misses the cache, a
reused one always hits it. `as_of_ns` is the exact int64 nanosecond
timestamp (or None for "now"), so this is a precise cache, not an
approximation.
"""

from typing import Optional

import pandas as pd

from graph_engine.build_graph import build_graph
from graph_engine.community import detect_communities

_MAX_ENTRIES = 256
_cache: dict = {}
_order: list = []


def get_graph_and_communities(ds, as_of: Optional[pd.Timestamp], seed: int = 42):
    """Returns (graph, node_to_community) for this `ds`/`as_of`/`seed`,
    reusing a cached build whenever the same combination was already
    computed."""
    as_of_ns = int(pd.Timestamp(as_of).value) if as_of is not None else None
    key = (id(ds), as_of_ns, seed)

    cached = _cache.get(key)
    if cached is not None:
        return cached

    G = build_graph(ds.accounts, ds.transactions, ds.withdrawal_points, ds.withdrawal_events, as_of=as_of)
    node_to_community = detect_communities(G, seed=seed)
    result = (G, node_to_community)

    _cache[key] = result
    _order.append(key)
    if len(_order) > _MAX_ENTRIES:
        oldest = _order.pop(0)
        _cache.pop(oldest, None)

    return result
