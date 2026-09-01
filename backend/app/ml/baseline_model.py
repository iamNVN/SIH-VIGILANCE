"""
baseline_model.py -- "what everyone else will build" (Blueprint Section 7).

Random Forest over TABULAR-ONLY features: amount, hour-of-day, bank match,
and raw historical withdrawal-point popularity (`global_geo_density` -- an
aggregate popularity count, not a graph-derived or community-scoped signal).
No community/centrality/chain-depth/recency features -- those require
relational graph reasoning, which is exactly what this baseline is missing
by design, so the Section 18 evaluation can show a real, honest lift.
"""

from sklearn.ensemble import RandomForestClassifier

from graph_engine.features import BASELINE_FEATURE_COLUMNS

FEATURE_COLUMNS = BASELINE_FEATURE_COLUMNS
MODEL_VERSION = "baseline-v1"


def build_model(seed: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )


def fit(df_train, seed: int = 42) -> RandomForestClassifier:
    model = build_model(seed=seed)
    model.fit(df_train[FEATURE_COLUMNS], df_train["label"])
    return model
