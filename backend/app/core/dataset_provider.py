"""
dataset_provider.py -- builds a graph_engine.features.Dataset (the same
object ml/evaluate.py uses) from the live database instead of CSVs, via
pandas.read_sql against the same engine. This is the "pass DataFrames from
SQLAlchemy queries instead of pd.read_csv" swap that build_graph.py's and
features.py's own docstrings call for.

Cached at module scope and refreshed on demand -- rebuilding from the DB on
every single request would re-run Louvain from scratch per candidate
request, which is fine for a demo's request volume but should be refreshed
whenever new complaints/transactions are ingested (`refresh()`).
"""

import pandas as pd

from core.db import engine
from graph_engine.features import Dataset

_cached: Dataset | None = None


def _read(table: str) -> pd.DataFrame:
    return pd.read_sql_table(table, engine)


def get_dataset(force_refresh: bool = False) -> Dataset:
    global _cached
    if _cached is None or force_refresh:
        # A fresh Dataset object each refresh (not mutated in place) is what
        # lets graph_engine/graph_cache.py invalidate for free -- it keys on
        # id(dataset), so a new object here can never collide with a stale
        # cached graph/community-detection result from before this refresh.
        _cached = Dataset(
            accounts=_read("accounts"),
            transactions=_read("transactions"),
            withdrawal_points=_read("withdrawal_points"),
            withdrawal_events=_read("withdrawal_events"),
            complaints=_read("complaints"),
            victims=_read("victims"),
        )
    return _cached


def refresh():
    return get_dataset(force_refresh=True)
