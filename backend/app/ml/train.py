"""
train.py -- fits and calibrates both the baseline (Random Forest) and
advanced (XGBoost) models on the temporal-split TRAIN complaints only, and
saves artifacts for the FastAPI app to load at request time. This is the
"production" training entrypoint; ml/evaluate.py re-runs the identical
split+fit to additionally score against the held-out TEST complaints and
print the Section 18 metrics -- the two never diverge because both import
from ml/pipeline.py.

Run:
    python -m ml.train                 # from backend/app
    python -m ml.train --rebuild       # force-recompute features, ignore cache
"""

import argparse
import json

import joblib

from ml import advanced_model, baseline_model, calibration
from ml.pipeline import ARTIFACTS_DIR, Dataset, load_or_build_features, temporal_split


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../../data/output")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("Loading dataset...")
    ds = Dataset.from_csv_dir(args.data_dir)
    train_complaints, test_complaints = temporal_split(ds)
    print(f"Train complaints: {len(train_complaints)}, test complaints: {len(test_complaints)}")

    print("Building/loading TRAIN features...")
    df_train = load_or_build_features(ds, train_complaints, "features_train", rebuild=args.rebuild)

    print("Fitting + calibrating baseline (Random Forest, tabular-only)...")
    baseline_raw, baseline_calibrated = calibration.fit_and_calibrate(
        baseline_model.fit, df_train, baseline_model.FEATURE_COLUMNS, seed=args.seed
    )

    print("Fitting + calibrating advanced (XGBoost, fused graph+temporal+geo features)...")
    advanced_raw, advanced_calibrated = calibration.fit_and_calibrate(
        advanced_model.fit, df_train, advanced_model.FEATURE_COLUMNS, seed=args.seed
    )

    joblib.dump(baseline_raw, ARTIFACTS_DIR / "baseline_raw.joblib")
    joblib.dump(baseline_calibrated, ARTIFACTS_DIR / "baseline_calibrated.joblib")
    joblib.dump(advanced_raw, ARTIFACTS_DIR / "advanced_raw.joblib")
    joblib.dump(advanced_calibrated, ARTIFACTS_DIR / "advanced_calibrated.joblib")

    metadata = {
        "baseline_model_version": baseline_model.MODEL_VERSION,
        "advanced_model_version": advanced_model.MODEL_VERSION,
        "baseline_features": baseline_model.FEATURE_COLUMNS,
        "advanced_features": advanced_model.FEATURE_COLUMNS,
        "n_train_complaints": int(len(train_complaints)),
        "n_test_complaints": int(len(test_complaints)),
        "seed": args.seed,
    }
    with open(ARTIFACTS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Artifacts saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
