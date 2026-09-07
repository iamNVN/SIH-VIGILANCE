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
from datetime import datetime, timezone

import joblib

from ml import advanced_model, baseline_model, calibration
from ml.pipeline import ARTIFACTS_DIR, Dataset, load_or_build_features, temporal_split


def train_and_save(data_dir: str = "../../data/output", seed: int = 42, rebuild: bool = False, log=print) -> dict:
    """The actual training run -- fit both models, calibrate, write joblib
    artifacts + metadata.json. Pulled out of main() so core/retrain_manager.py
    can call this exact same code from a background thread, not a
    reimplementation that could silently drift from the CLI path. `log`
    defaults to `print` (CLI behavior) but the retrain manager passes a
    logger instead, since a background thread's stdout isn't visible
    anywhere useful.

    `train_run` increments on every real training run (read from the
    PREVIOUS metadata.json, if any, before overwriting it) -- MODEL_VERSION
    in advanced_model.py/baseline_model.py names the pipeline/architecture
    ("advanced-v1"), which doesn't change between retrains; appending the
    run number gives each actual fit its own distinct, visibly-incrementing
    version instead of the same static string whether the model has been
    trained once or fifty times."""
    prev_train_run = 0
    meta_path = ARTIFACTS_DIR / "metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                prev_train_run = json.load(f).get("train_run", 0)
        except (json.JSONDecodeError, OSError):
            prev_train_run = 0
    train_run = prev_train_run + 1

    log("Loading dataset...")
    ds = Dataset.from_csv_dir(data_dir)
    train_complaints, test_complaints = temporal_split(ds)
    log(f"Train complaints: {len(train_complaints)}, test complaints: {len(test_complaints)}")

    log("Building/loading TRAIN features...")
    df_train = load_or_build_features(ds, train_complaints, "features_train", rebuild=rebuild)

    log("Fitting + calibrating baseline (Random Forest, tabular-only)...")
    baseline_raw, baseline_calibrated = calibration.fit_and_calibrate(
        baseline_model.fit, df_train, baseline_model.FEATURE_COLUMNS, seed=seed
    )

    log("Fitting + calibrating advanced (XGBoost, fused graph+temporal+geo features)...")
    advanced_raw, advanced_calibrated = calibration.fit_and_calibrate(
        advanced_model.fit, df_train, advanced_model.FEATURE_COLUMNS, seed=seed
    )

    joblib.dump(baseline_raw, ARTIFACTS_DIR / "baseline_raw.joblib")
    joblib.dump(baseline_calibrated, ARTIFACTS_DIR / "baseline_calibrated.joblib")
    joblib.dump(advanced_raw, ARTIFACTS_DIR / "advanced_raw.joblib")
    joblib.dump(advanced_calibrated, ARTIFACTS_DIR / "advanced_calibrated.joblib")

    metadata = {
        "baseline_model_version": f"{baseline_model.MODEL_VERSION}.{train_run}",
        "advanced_model_version": f"{advanced_model.MODEL_VERSION}.{train_run}",
        "baseline_features": baseline_model.FEATURE_COLUMNS,
        "advanced_features": advanced_model.FEATURE_COLUMNS,
        "n_train_complaints": int(len(train_complaints)),
        "n_test_complaints": int(len(test_complaints)),
        "seed": seed,
        "train_run": train_run,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(ARTIFACTS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    log(f"Artifacts saved to {ARTIFACTS_DIR}")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../../data/output")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train_and_save(data_dir=args.data_dir, seed=args.seed, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
