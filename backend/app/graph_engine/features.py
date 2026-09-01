"""
features.py -- the fused feature pipeline: graph + temporal-decay +
geospatial-density features per (complaint, candidate withdrawal point),
per Execution Blueprint Section 3/4/18.

DESIGN NOTE -- what is "known" at complaint-filing time
--------------------------------------------------------
Per Blueprint Section 2, a complaint's inputs include "the first known
transaction reference" -- i.e. the victim's own bank statement shows the
debit and which account it went to. That first hop (hop_index=0) is
therefore always treated as known, regardless of `as_of`. Every subsequent
hop (mule-to-mule, mule-to-withdrawal) is only "known" once its own
timestamp is strictly before `as_of` -- this is what `transactions.complaint_id`
represents in the real schema (Blueprint Section 6): the traced chain as
investigators establish it over time, not a generator-only label. This is
different from `fraud_rings.ring_id`, which IS generator-only ground truth
and is never touched here.

DESIGN NOTE -- point-in-time + self-exclusion (no leakage)
-------------------------------------------------------------
Two separate leakage guards are applied, per Blueprint Section 18:
1. Point-in-time graph construction: `build_graph(..., as_of=filed_at)` only
   includes events strictly before the complaint's own filed_at.
2. Self-exclusion: a complaint's OWN transactions/withdrawal_event are always
   excluded from any "historical popularity" aggregate computed for it (e.g.
   community_geo_density, community_num_complaints) -- this matters
   specifically for the ~20% "too-late" complaints (Blueprint Section 6),
   where the complaint's own true withdrawal event may already be time-wise
   *before* its own filed_at and would otherwise leak into "historical
   density near the true point" for that very complaint.

DESIGN NOTE -- account_type is NOT a feature
-------------------------------------------------------------
`accounts.account_type` (mule/victim/normal) is generator-side ground truth
about ring membership -- in reality an investigator does not know a priori
which accounts are "mule" accounts (that's the very question being solved).
It is used only to build the synthetic data, never as a model input.

DESIGN NOTE -- why pointwise binary classification, not a learning-to-rank
objective
-------------------------------------------------------------
Blueprint Section 4 calls for calibrated confidence per prediction
(`CalibratedClassifierCV`, Section 4/18), which wraps binary/multiclass
classifiers, not ranking objectives. So both the baseline and advanced
models are trained as binary classifiers over (complaint, candidate) pairs
predicting P(this candidate is the true cash-out point), then ranked by that
probability within each complaint's candidate set. This is a standard,
defensible "pointwise learning-to-rank" formulation and is what makes a
genuine calibrated confidence score possible in the output JSON (Section 11).
"""

import math
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd

from graph_engine.build_graph import build_graph
from graph_engine.community import detect_communities

RECENCY_DECAY_LAMBDA = 1.0 / 12.0  # per hour -- half-life-ish over ~8 hours, tuned to the rings_config fast/slow delay split (1-48h)
GEO_KERNEL_BANDWIDTH_KM = 2.0       # matches Blueprint Section 18's "hit-rate within 2km" operational radius
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorized haversine distance in km. Scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


class Dataset:
    """Loads the generator's CSVs once and exposes point-in-time helpers.
    Pass DataFrames straight from SQLAlchemy query results in the real
    backend instead of `from_csv_dir` -- `build_graph()` already documents
    this same swap (see its module docstring)."""

    def __init__(self, accounts, transactions, withdrawal_points, withdrawal_events, complaints, victims):
        self.accounts = accounts
        self.transactions = transactions.copy()
        self.withdrawal_points = withdrawal_points
        self.withdrawal_events = withdrawal_events.copy()
        self.complaints = complaints.copy()
        self.victims = victims

        self.transactions["timestamp"] = pd.to_datetime(self.transactions["timestamp"], format="%Y-%m-%dT%H:%M:%S")
        self.withdrawal_events["timestamp"] = pd.to_datetime(self.withdrawal_events["timestamp"], format="%Y-%m-%dT%H:%M:%S")
        self.complaints["filed_at"] = pd.to_datetime(self.complaints["filed_at"], format="%Y-%m-%dT%H:%M:%S")

        self.victim_city = self.victims.set_index("id")["city"]
        # withdrawal_events joined with their point's lat/lon/city, for fast geo aggregation
        self.we_geo = self.withdrawal_events.merge(
            self.withdrawal_points[["id", "lat", "lon", "city"]],
            left_on="withdrawal_point_id", right_on="id", suffixes=("", "_wp"),
        )

    @classmethod
    def from_csv_dir(cls, data_dir: str) -> "Dataset":
        from pathlib import Path

        d = Path(data_dir)
        return cls(
            accounts=pd.read_csv(d / "accounts.csv"),
            transactions=pd.read_csv(d / "transactions.csv"),
            withdrawal_points=pd.read_csv(d / "withdrawal_points.csv"),
            withdrawal_events=pd.read_csv(d / "withdrawal_events.csv"),
            complaints=pd.read_csv(d / "complaints.csv"),
            victims=pd.read_csv(d / "victims.csv"),
        )

    def candidate_points_for_city(self, city: str) -> pd.DataFrame:
        return self.withdrawal_points[self.withdrawal_points["city"] == city].reset_index(drop=True)


def known_chain_state(ds: Dataset, complaint_id: int, as_of: pd.Timestamp):
    """Returns (frontier_account_id, chain_depth, last_known_timestamp) for
    what is knowable about this complaint's fund-flow chain strictly before
    `as_of`, per the module's "known chain" design note above."""
    ctx = ds.transactions[ds.transactions["complaint_id"] == complaint_id].sort_values("hop_index")
    hop0 = ctx[ctx["hop_index"] == 0].iloc[0]
    frontier = hop0["to_account_id"]
    depth = 1
    last_ts = hop0["timestamp"]

    known_later_hops = ctx[(ctx["hop_index"] > 0) & (ctx["timestamp"] < as_of)]
    if not known_later_hops.empty:
        last_row = known_later_hops.sort_values("hop_index").iloc[-1]
        frontier = last_row["to_account_id"]
        depth = int(last_row["hop_index"]) + 1
        last_ts = last_row["timestamp"]

    return frontier, depth, last_ts


def build_candidate_features(ds: Dataset, complaint_row: pd.Series, seed: int = 42) -> pd.DataFrame:
    """Build one feature row per candidate withdrawal point (all points in
    the victim's city) for a single complaint. Returns a DataFrame with a
    `label` column (1 for the true cash-out point, else 0)."""
    complaint_id = complaint_row["id"]
    as_of = complaint_row["filed_at"]
    victim_city = ds.victim_city[complaint_row["victim_id"]]

    G = build_graph(ds.accounts, ds.transactions, ds.withdrawal_points, ds.withdrawal_events, as_of=as_of)
    node_to_community = detect_communities(G, seed=seed)

    frontier, chain_depth, last_ts = known_chain_state(ds, complaint_id, as_of)
    frontier_node = f"acc_{frontier}"
    frontier_community = node_to_community.get(frontier_node)

    hours_since_last_event = max((as_of - last_ts).total_seconds() / 3600.0, 0.0)
    recency_decay = math.exp(-RECENCY_DECAY_LAMBDA * hours_since_last_event)

    degree_centrality_global = 0.0
    if frontier_node in G:
        degree_centrality_global = G.in_degree(frontier_node) + G.out_degree(frontier_node)
        degree_centrality_global /= max(G.number_of_nodes() - 1, 1)

    # community members + a small induced subgraph for a cheap local betweenness score
    community_members = [n for n, c in node_to_community.items() if c == frontier_community] if frontier_community is not None else [frontier_node]
    community_size = len(community_members)

    local_betweenness = 0.0
    if len(community_members) >= 3:
        H = G.subgraph(community_members)
        try:
            bc = nx.betweenness_centrality(H, seed=seed)
            local_betweenness = bc.get(frontier_node, 0.0)
        except Exception:
            local_betweenness = 0.0

    # --- cross-complaint linking: how many OTHER complaints touch this community, before as_of, excluding this complaint itself ---
    member_ids = {int(n.split("_", 1)[1]) for n in community_members if n.startswith("acc_")}
    tx_before = ds.transactions[(ds.transactions["timestamp"] < as_of) & (ds.transactions["complaint_id"] != complaint_id)]
    we_before = ds.withdrawal_events[(ds.withdrawal_events["timestamp"] < as_of) & (ds.withdrawal_events["complaint_id"] != complaint_id)]
    linked_via_tx = tx_before[tx_before["from_account_id"].isin(member_ids) | tx_before["to_account_id"].isin(member_ids)]
    linked_via_we = we_before[we_before["account_id"].isin(member_ids)]
    community_num_complaints = pd.concat([linked_via_tx["complaint_id"], linked_via_we["complaint_id"]]).dropna().nunique()

    # --- geospatial density, both global and community-scoped, self-excluded, point-in-time ---
    we_hist = ds.we_geo[(ds.we_geo["timestamp"] < as_of) & (ds.we_geo["complaint_id"] != complaint_id) & (ds.we_geo["city"] == victim_city)]
    we_hist_community = we_hist[we_hist["account_id"].isin(member_ids)]

    candidates = ds.candidate_points_for_city(victim_city).copy()
    candidates["complaint_id"] = complaint_id
    candidates["chain_depth"] = chain_depth
    candidates["recency_decay"] = recency_decay
    candidates["degree_centrality_global"] = degree_centrality_global
    candidates["community_size"] = community_size
    candidates["local_betweenness"] = local_betweenness
    candidates["community_num_complaints"] = community_num_complaints
    candidates["amount_lost"] = complaint_row["amount_lost"]
    candidates["hour_of_day"] = as_of.hour
    candidates["bank_match"] = (candidates["bank_name"] == complaint_row["bank_name"]).astype(int)

    if len(we_hist) > 0:
        d = haversine_km(candidates["lat"].values[:, None], candidates["lon"].values[:, None],
                          we_hist["lat"].values[None, :], we_hist["lon"].values[None, :])
        candidates["global_geo_density"] = np.exp(-(d ** 2) / (2 * GEO_KERNEL_BANDWIDTH_KM ** 2)).sum(axis=1)
    else:
        candidates["global_geo_density"] = 0.0

    if len(we_hist_community) > 0:
        d = haversine_km(candidates["lat"].values[:, None], candidates["lon"].values[:, None],
                          we_hist_community["lat"].values[None, :], we_hist_community["lon"].values[None, :])
        candidates["community_geo_density"] = np.exp(-(d ** 2) / (2 * GEO_KERNEL_BANDWIDTH_KM ** 2)).sum(axis=1)
    else:
        candidates["community_geo_density"] = 0.0

    true_wp_row = ds.withdrawal_events[ds.withdrawal_events["complaint_id"] == complaint_id]
    true_wp_id = int(true_wp_row.iloc[0]["withdrawal_point_id"]) if not true_wp_row.empty else None
    candidates["label"] = (candidates["id"] == true_wp_id).astype(int)

    return candidates.rename(columns={"id": "withdrawal_point_id"})


BASELINE_FEATURE_COLUMNS = ["amount_lost", "hour_of_day", "bank_match", "global_geo_density"]
ADVANCED_FEATURE_COLUMNS = BASELINE_FEATURE_COLUMNS + [
    "chain_depth", "recency_decay", "degree_centrality_global",
    "community_size", "local_betweenness", "community_num_complaints",
    "community_geo_density",
]


def build_dataset(ds: Dataset, complaints_subset: pd.DataFrame, seed: int = 42, progress_every: int = 50) -> pd.DataFrame:
    """Loop `build_candidate_features` over many complaints and concatenate.
    Used identically by ml/train.py and ml/evaluate.py so train and test
    features are always computed the same, honest, point-in-time way."""
    frames = []
    for i, (_, row) in enumerate(complaints_subset.iterrows()):
        frames.append(build_candidate_features(ds, row, seed=seed))
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  features: {i + 1}/{len(complaints_subset)} complaints done")
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../../../data/output"
    ds = Dataset.from_csv_dir(data_dir)
    sample = ds.complaints.sort_values("filed_at").head(5)
    df = build_dataset(ds, sample, progress_every=1)
    pd.set_option("display.width", 200)
    print(df[["complaint_id", "withdrawal_point_id", "label"] + ADVANCED_FEATURE_COLUMNS].to_string())
