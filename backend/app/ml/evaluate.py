"""
evaluate.py -- THE Blueprint Section 18 experiment. Baseline vs advanced,
real numbers only, computed against our own generated data -- never
invented (Section 18's own words: "We do not fabricate numbers anywhere in
this document").

Metrics: Precision@1, Precision@5 (== Recall@5 == Hit-Rate@5 here, since
there is exactly one true withdrawal point per complaint -- stated
explicitly, not confused for two different things), Location Hit-Rate
within 2km, False-Positive Rate on high-confidence top-1 predictions,
Prediction Lead Time (actionable complaints only), Brier score + a
reliability table for calibration.

Run:
    python -m ml.evaluate                # from backend/app
    python -m ml.evaluate --rebuild      # force-recompute features
"""

import argparse
import json

import numpy as np
import pandas as pd

from graph_engine.features import haversine_km
from ml import advanced_model, baseline_model, calibration
from ml.pipeline import ARTIFACTS_DIR, Dataset, load_or_build_features, temporal_split

HIT_RADIUS_KM = 2.0
# Was 0.5 -- unreachable on this data (max observed top-1 confidence across
# the test set is ~0.196, since a calibrated pick among ~40 candidates
# rarely clears 20%), so this metric always reported n=0 and was silently
# uninformative. 0.125 is the SAME 5x-lift-over-random-chance threshold the
# live app itself calls "HIGH" urgency (see api/predict.py's lift_urgency)
# -- a principled definition of "high confidence" already used elsewhere,
# not a percentile picked just to get a non-zero sample size. On the
# current test set this yields ~40 qualifying top-1 predictions.
HIGH_CONFIDENCE_THRESHOLD = 0.125


def rank_within_complaint(df: pd.DataFrame, prob_col: str) -> pd.DataFrame:
    df = df.copy()
    df["rank"] = df.groupby("complaint_id")[prob_col].rank(ascending=False, method="first")
    return df


def precision_at_k(df_ranked: pd.DataFrame, k: int) -> float:
    hits = df_ranked[(df_ranked["rank"] <= k) & (df_ranked["label"] == 1)]
    n_complaints = df_ranked["complaint_id"].nunique()
    return len(hits) / n_complaints


def hit_rate_within_km(df_ranked: pd.DataFrame, k: int, radius_km: float) -> float:
    hit_count = 0
    n_complaints = 0
    for complaint_id, group in df_ranked.groupby("complaint_id"):
        n_complaints += 1
        true_row = group[group["label"] == 1]
        if true_row.empty:
            continue
        true_lat, true_lon = true_row.iloc[0][["lat", "lon"]]
        top_k = group[group["rank"] <= k]
        d = haversine_km(top_k["lat"].values, top_k["lon"].values, true_lat, true_lon)
        if (d <= radius_km).any():
            hit_count += 1
    return hit_count / n_complaints


def false_positive_rate_high_confidence(df_ranked: pd.DataFrame, prob_col: str, threshold: float) -> dict:
    top1 = df_ranked[df_ranked["rank"] == 1]
    high_conf = top1[top1[prob_col] > threshold]
    if len(high_conf) == 0:
        return {"n_high_confidence": 0, "false_positive_rate": None}
    wrong = high_conf[high_conf["label"] == 0]
    return {"n_high_confidence": int(len(high_conf)), "false_positive_rate": len(wrong) / len(high_conf)}


def brier_score(df: pd.DataFrame, prob_col: str) -> float:
    return float(np.mean((df[prob_col] - df["label"]) ** 2))


def reliability_table(df: pd.DataFrame, prob_col: str, n_bins: int = 10) -> list:
    df = df.copy()
    df["bin"] = pd.cut(df[prob_col], bins=np.linspace(0, 1, n_bins + 1), include_lowest=True)
    table = []
    for interval, group in df.groupby("bin", observed=True):
        if len(group) == 0:
            continue
        table.append({
            "bin": str(interval),
            "n": int(len(group)),
            "mean_predicted": float(group[prob_col].mean()),
            "observed_frequency": float(group["label"].mean()),
        })
    return table


def mean_rank_of_true_point(df_ranked: pd.DataFrame) -> float:
    return float(df_ranked[df_ranked["label"] == 1]["rank"].mean())


def lead_time_stats(ds: Dataset, test_complaints: pd.DataFrame, df_ranked_advanced: pd.DataFrame) -> dict:
    we = ds.withdrawal_events.set_index("complaint_id")["timestamp"]
    complaints = test_complaints.set_index("id")

    lead_hours = []
    actionable_hit5 = []
    for complaint_id in test_complaints["id"]:
        if complaint_id not in we.index:
            continue
        filed_at = complaints.loc[complaint_id, "filed_at"]
        withdrawn_at = we.loc[complaint_id]
        if filed_at >= withdrawn_at:
            continue  # not actionable -- already withdrawn by the time it was filed (Section 6/18)
        lead = (withdrawn_at - filed_at).total_seconds() / 3600.0
        lead_hours.append(lead)
        group = df_ranked_advanced[df_ranked_advanced["complaint_id"] == complaint_id]
        hit5 = bool(((group["rank"] <= 5) & (group["label"] == 1)).any())
        actionable_hit5.append(hit5)

    lead_hours = np.array(lead_hours)
    actionable_hit5 = np.array(actionable_hit5)
    result = {
        "n_actionable": int(len(lead_hours)),
        "mean_lead_hours_all_actionable": float(lead_hours.mean()) if len(lead_hours) else None,
        "median_lead_hours_all_actionable": float(np.median(lead_hours)) if len(lead_hours) else None,
    }
    if actionable_hit5.any():
        result["mean_lead_hours_when_top5_hit"] = float(lead_hours[actionable_hit5].mean())
        result["median_lead_hours_when_top5_hit"] = float(np.median(lead_hours[actionable_hit5]))
    return result


def evaluate_model(name: str, df_test: pd.DataFrame, prob_col: str) -> dict:
    df_ranked = rank_within_complaint(df_test, prob_col)
    return {
        "model": name,
        "precision_at_1": precision_at_k(df_ranked, 1),
        "precision_at_5": precision_at_k(df_ranked, 5),
        "hit_rate_within_2km_at_5": hit_rate_within_km(df_ranked, 5, HIT_RADIUS_KM),
        "mean_rank_of_true_point": mean_rank_of_true_point(df_ranked),
        "brier_score": brier_score(df_test, prob_col),
        "false_positive": false_positive_rate_high_confidence(df_ranked, prob_col, HIGH_CONFIDENCE_THRESHOLD),
        "reliability_table": reliability_table(df_test, prob_col),
    }, df_ranked


def _fit_and_score_one_seed(df_train: pd.DataFrame, df_test: pd.DataFrame, seed: int):
    """One full fit+calibrate+score pass at a given seed. `seed` drives BOTH
    the model's own randomness (tree construction, subsampling) AND which
    complaints land in the calibration-fit vs calibration-holdout split
    (`calibration.split_by_complaint`) -- so re-running this across several
    seeds is a genuine stability check on the whole fit+calibrate pipeline,
    not just a knob turn. The train/test split itself (`temporal_split`) is
    NOT re-drawn per seed -- that has to stay fixed for "did the graph
    features help" to mean anything; only the fitting randomness is what
    we're checking for stability here."""
    baseline_raw, baseline_calibrated = calibration.fit_and_calibrate(
        baseline_model.fit, df_train, baseline_model.FEATURE_COLUMNS, seed=seed
    )
    advanced_raw, advanced_calibrated = calibration.fit_and_calibrate(
        advanced_model.fit, df_train, advanced_model.FEATURE_COLUMNS, seed=seed
    )

    df_test = df_test.copy()
    df_test["baseline_prob"] = baseline_calibrated.predict_proba(df_test[baseline_model.FEATURE_COLUMNS])[:, 1]
    df_test["advanced_prob"] = advanced_calibrated.predict_proba(df_test[advanced_model.FEATURE_COLUMNS])[:, 1]

    baseline_results, baseline_ranked = evaluate_model("baseline (Random Forest, tabular-only)", df_test, "baseline_prob")
    advanced_results, advanced_ranked = evaluate_model("advanced (XGBoost, fused graph+temporal+geo)", df_test, "advanced_prob")
    return baseline_results, advanced_results, advanced_ranked


def _mean_std(values: list) -> dict:
    arr = np.array(values, dtype=float)
    return {"mean": float(arr.mean()), "std": float(arr.std()), "values": [round(v, 4) for v in values]}


def _stability_across_seeds(per_seed_results: list) -> dict:
    """per_seed_results: list of (seed, baseline_results, advanced_results).
    Aggregates the headline metrics across seeds so "is 48.6% a lucky split"
    has a real, computed answer instead of none."""
    seeds = [s for s, _, _ in per_seed_results]
    return {
        "seeds": seeds,
        "advanced": {
            "precision_at_1": _mean_std([a["precision_at_1"] for _, _, a in per_seed_results]),
            "precision_at_5": _mean_std([a["precision_at_5"] for _, _, a in per_seed_results]),
            "hit_rate_within_2km_at_5": _mean_std([a["hit_rate_within_2km_at_5"] for _, _, a in per_seed_results]),
            "brier_score": _mean_std([a["brier_score"] for _, _, a in per_seed_results]),
        },
        "baseline": {
            "precision_at_5": _mean_std([b["precision_at_5"] for _, b, _ in per_seed_results]),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../../data/output")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--seed", type=int, default=42, help="primary seed -- its full detailed report (reliability table etc.) is what gets saved/served")
    parser.add_argument(
        "--seeds", type=str, default=None,
        help="comma-separated extra seeds for a stability check (mean/std of headline metrics across fits). "
             "Example: --seeds 42,7,123,2024,99. If omitted, only --seed runs (old single-run behavior).",
    )
    args = parser.parse_args()

    print("Loading dataset...")
    ds = Dataset.from_csv_dir(args.data_dir)
    train_complaints, test_complaints = temporal_split(ds)
    print(f"Train complaints: {len(train_complaints)}, test complaints: {len(test_complaints)} (temporal split, Section 18)")

    print("Building/loading TRAIN features (point-in-time, as_of=filed_at per complaint)...")
    df_train = load_or_build_features(ds, train_complaints, "features_train", rebuild=args.rebuild)
    print("Building/loading TEST features (point-in-time, as_of=filed_at per complaint)...")
    df_test = load_or_build_features(ds, test_complaints, "features_test", rebuild=args.rebuild)

    seed_list = [args.seed]
    if args.seeds:
        seed_list += [int(s) for s in args.seeds.split(",") if int(s) != args.seed]

    per_seed_results = []
    primary_advanced_ranked = None
    for i, seed in enumerate(seed_list):
        label = "primary" if i == 0 else "stability check"
        print(f"\nFitting + calibrating both models at seed={seed} ({label})...")
        baseline_results, advanced_results, advanced_ranked = _fit_and_score_one_seed(df_train, df_test, seed)
        per_seed_results.append((seed, baseline_results, advanced_results))
        if i == 0:
            primary_advanced_ranked = advanced_ranked

    # The detailed report (reliability table, false-positive breakdown, the
    # numbers Analytics.jsx renders) is the PRIMARY seed's -- unchanged
    # shape from before, so nothing downstream breaks. Multi-seed stability
    # is additive, not a replacement.
    _, baseline_results, advanced_results = per_seed_results[0]
    lead_time = lead_time_stats(ds, test_complaints, primary_advanced_ranked)

    report = {
        "n_test_complaints": int(len(test_complaints)),
        "baseline": baseline_results,
        "advanced": advanced_results,
        "lead_time_advanced_model": lead_time,
    }
    if len(per_seed_results) > 1:
        report["stability"] = _stability_across_seeds(per_seed_results)

    print("\n" + "=" * 78)
    print("SECTION 18 EVALUATION -- BASELINE vs ADVANCED (real numbers, temporal split)")
    print("=" * 78)
    for r in (baseline_results, advanced_results):
        fp = r["false_positive"]
        print(f"\n{r['model']}")
        print(f"  Precision@1                 : {r['precision_at_1']:.3f}")
        print(f"  Precision@5 (=Recall@5)      : {r['precision_at_5']:.3f}")
        print(f"  Hit-rate within {HIT_RADIUS_KM}km @5      : {r['hit_rate_within_2km_at_5']:.3f}")
        print(f"  Mean rank of true point      : {r['mean_rank_of_true_point']:.2f}")
        print(f"  Brier score (lower=better)   : {r['brier_score']:.4f}")
        if fp["false_positive_rate"] is not None:
            print(f"  False-positive rate (conf>{HIGH_CONFIDENCE_THRESHOLD}, top-1, n={fp['n_high_confidence']}): {fp['false_positive_rate']:.3f}")
        else:
            print(f"  False-positive rate (conf>{HIGH_CONFIDENCE_THRESHOLD}, top-1): no predictions above threshold")

    print(f"\nLead time (actionable test complaints, n={lead_time['n_actionable']}):")
    print(f"  Mean lead time available to act    : {lead_time['mean_lead_hours_all_actionable']:.2f}h")
    print(f"  Median lead time available to act   : {lead_time['median_lead_hours_all_actionable']:.2f}h")
    if "mean_lead_hours_when_top5_hit" in lead_time:
        print(f"  Mean lead time when top-5 hit true point: {lead_time['mean_lead_hours_when_top5_hit']:.2f}h")

    lift_p5 = advanced_results["precision_at_5"] - baseline_results["precision_at_5"]
    print(f"\nLift: advanced Precision@5 - baseline Precision@5 = {lift_p5:+.3f}")

    if "stability" in report:
        st = report["stability"]["advanced"]
        print("\n" + "-" * 78)
        print(f"STABILITY ACROSS {len(seed_list)} SEEDS {seed_list} (fit+calibration randomness only, same temporal split):")
        print(f"  Advanced Precision@1  : {st['precision_at_1']['mean']:.3f} +/- {st['precision_at_1']['std']:.3f}   {st['precision_at_1']['values']}")
        print(f"  Advanced Precision@5  : {st['precision_at_5']['mean']:.3f} +/- {st['precision_at_5']['std']:.3f}   {st['precision_at_5']['values']}")
        print(f"  Advanced Hit-rate@5   : {st['hit_rate_within_2km_at_5']['mean']:.3f} +/- {st['hit_rate_within_2km_at_5']['std']:.3f}")
        print(f"  Advanced Brier score  : {st['brier_score']['mean']:.4f} +/- {st['brier_score']['std']:.4f}")
    print("=" * 78)

    with open(ARTIFACTS_DIR / "evaluation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to {ARTIFACTS_DIR / 'evaluation_report.json'}")


if __name__ == "__main__":
    main()
