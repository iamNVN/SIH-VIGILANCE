"""
explain.py -- SHAP TreeExplainer wrapper (Blueprint Section 4/17/25).

Explains the RAW (uncalibrated) advanced model's decision -- SHAP's
TreeExplainer needs direct access to the underlying tree ensemble, which
`CalibratedClassifierCV` wraps and hides. The confidence NUMBER shown to a
user still comes from the calibrated model; this module only answers "why",
using the base model's tree structure. This split (raw model explains,
calibrated model scores) is standard practice, not a shortcut.
"""

from typing import List

import pandas as pd
import shap

_explainer_cache = {}


def get_explainer(base_model) -> shap.TreeExplainer:
    key = id(base_model)
    if key not in _explainer_cache:
        _explainer_cache[key] = shap.TreeExplainer(base_model)
    return _explainer_cache[key]


def explain_row(base_model, feature_columns: List[str], row: pd.Series) -> dict:
    """Returns {"top_features": [...], "shap_values": {feature: value}} for one candidate row."""
    explainer = get_explainer(base_model)
    # `row` is a Series sliced from a mixed-dtype DataFrame (names, lat/lon,
    # ids alongside these numeric features), so its own dtype is `object`
    # even though every value here is numeric -- cast explicitly or XGBoost's
    # DMatrix construction rejects the whole frame as non-numeric.
    X = row[feature_columns].to_frame().T.astype(float)
    shap_values = explainer.shap_values(X)
    values = shap_values[0] if shap_values.ndim == 2 else shap_values[0, :, 1]

    contributions = list(zip(feature_columns, values))
    contributions.sort(key=lambda kv: -abs(kv[1]))

    top_features = [f"{name}={row[name]:.3g} (impact {value:+.3f})" for name, value in contributions[:3]]
    return {
        "top_features": top_features,
        "shap_values": {name: float(value) for name, value in contributions},
    }


def narrative_from_explanation(explanation: dict, community_size: int, community_num_complaints: int) -> str:
    if community_num_complaints > 0:
        return (
            f"This account's cluster shows activity linked to {community_num_complaints} other "
            f"complaint(s) (community size {community_size}), and historically cashes out near "
            f"this location. Top drivers: {', '.join(explanation['top_features'])}."
        )
    return (
        f"No prior linked complaints found for this cluster yet; ranking is driven by geospatial "
        f"and recency signal. Top drivers: {', '.join(explanation['top_features'])}."
    )
