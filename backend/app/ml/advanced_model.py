"""
advanced_model.py -- the core prediction engine (Blueprint Section 4/7).

XGBoost ranking-by-classification over the fused feature set: everything the
baseline sees, PLUS graph-derived features (community size, cross-complaint
linking count, local betweenness, degree centrality, chain depth), the
temporal recency-decay feature, and the community-scoped geospatial density.

Trained as a binary classifier (P = is this candidate the true cash-out
point), not `XGBRanker` -- see graph_engine/features.py's module docstring
for why: `CalibratedClassifierCV` (Section 4/18) needs a probabilistic
classifier to produce a genuine calibrated confidence score per prediction,
which a pure ranking objective doesn't expose. Ranking is recovered by
sorting candidates within a complaint by predicted probability.
"""

from xgboost import XGBClassifier

from graph_engine.features import ADVANCED_FEATURE_COLUMNS

FEATURE_COLUMNS = ADVANCED_FEATURE_COLUMNS
MODEL_VERSION = "advanced-v1"


def build_model(scale_pos_weight: float = 1.0, seed: int = 42) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=seed,
        n_jobs=-1,
    )


def fit(df_train, seed: int = 42) -> XGBClassifier:
    n_pos = int(df_train["label"].sum())
    n_neg = len(df_train) - n_pos
    scale_pos_weight = max(n_neg / max(n_pos, 1), 1.0)
    model = build_model(scale_pos_weight=scale_pos_weight, seed=seed)
    model.fit(df_train[FEATURE_COLUMNS], df_train["label"])
    return model
