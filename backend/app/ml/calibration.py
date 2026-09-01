"""
calibration.py -- turns a raw model score into a genuinely calibrated
confidence (Blueprint Section 4/18/25: "is your confidence score genuinely
calibrated? Yes -- wrapped with CalibratedClassifierCV").

Splits the training complaints (not rows -- see note below) into a
model-fit subset and a held-out calibration subset, fits the base model on
the former, then wraps it in `CalibratedClassifierCV` fit on the latter.

WHY SPLIT BY COMPLAINT, NOT BY ROW
-------------------------------------------------------------
Each complaint contributes ~40 candidate rows (one per withdrawal point in
its city). Rows from the same complaint share the same graph/community
snapshot and are highly correlated. Splitting rows randomly would leak a
complaint's own candidates across both the model-fit and calibration sets,
inflating the calibration fit's apparent honesty. Splitting by whole
complaint avoids that.

WHY `FrozenEstimator`, NOT the old `cv="prefit"`
-------------------------------------------------------------
scikit-learn 1.8 (installed here) removed `cv="prefit"` in favour of
explicitly wrapping an already-fitted estimator with `sklearn.frozen.
FrozenEstimator`, then calibrating with `cv=None`'s default internal
behaviour disabled by the Frozen wrapper -- this is the documented
replacement, not a workaround.
"""

from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator


def split_by_complaint(df: pd.DataFrame, calib_fraction: float = 0.2, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    complaint_ids = df["complaint_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(complaint_ids)
    n_calib = max(1, int(len(complaint_ids) * calib_fraction))
    calib_ids = set(complaint_ids[:n_calib])
    is_calib = df["complaint_id"].isin(calib_ids)
    return df[~is_calib], df[is_calib]


def calibrate(fitted_model, feature_columns, df_calib: pd.DataFrame, method: str = "isotonic") -> CalibratedClassifierCV:
    calibrated = CalibratedClassifierCV(estimator=FrozenEstimator(fitted_model), method=method)
    calibrated.fit(df_calib[feature_columns], df_calib["label"])
    return calibrated


def fit_and_calibrate(fit_fn, df_train: pd.DataFrame, feature_columns, method: str = "isotonic", calib_fraction: float = 0.2, seed: int = 42):
    """`fit_fn(df_subset, seed=...) -> fitted base model`, e.g. advanced_model.fit."""
    df_fit, df_calib = split_by_complaint(df_train, calib_fraction=calib_fraction, seed=seed)
    base_model = fit_fn(df_fit, seed=seed)
    calibrated_model = calibrate(base_model, feature_columns, df_calib, method=method)
    return base_model, calibrated_model
