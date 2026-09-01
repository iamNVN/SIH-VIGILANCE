"""
pipeline.py -- shared plumbing used by both ml/train.py and ml/evaluate.py,
so the two scripts can never silently diverge on how features are built or
how the temporal split is drawn (Blueprint Section 18).
"""

from pathlib import Path

import pandas as pd

from graph_engine.features import Dataset, build_dataset

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


def temporal_split(ds: Dataset, train_fraction: float = 0.8):
    """Sort complaints by filed_at; first `train_fraction` = train, rest =
    test (Blueprint Section 18, point 2). This mirrors real deployment and
    avoids leaking future rings into training."""
    ordered = ds.complaints.sort_values("filed_at").reset_index(drop=True)
    cutoff = int(len(ordered) * train_fraction)
    return ordered.iloc[:cutoff].copy(), ordered.iloc[cutoff:].copy()


def load_or_build_features(ds: Dataset, complaints_subset: pd.DataFrame, cache_name: str, rebuild: bool = False) -> pd.DataFrame:
    cache_path = ARTIFACTS_DIR / f"{cache_name}.csv"
    if cache_path.exists() and not rebuild:
        print(f"  [cache hit] {cache_path.name}")
        return pd.read_csv(cache_path)
    print(f"  building features for {len(complaints_subset)} complaints -> {cache_path.name}")
    df = build_dataset(ds, complaints_subset)
    df.to_csv(cache_path, index=False)
    return df
