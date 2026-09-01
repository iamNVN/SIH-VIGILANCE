"""
build_graph.py — constructs the fund-flow graph.

Nodes: accounts (account_type: victim / mule / normal) and withdrawal_points.
Edges: TRANSFER (account -> account, from a transaction) and
       WITHDRAWAL (account -> withdrawal_point, from a withdrawal_event).

CRITICAL — POINT-IN-TIME CONSTRUCTION (Execution Blueprint, Section 18):
`as_of` restricts the graph to events that happened strictly before that
timestamp. This is what prevents the evaluation from leaking the future into
training: when we ask "what could the system have known at the moment THIS
complaint was filed", the answer must not include that complaint's own
not-yet-happened withdrawal, nor any other complaint's events that haven't
happened yet either.

In production (backend/app/api/graph.py) `as_of` is simply "now". In the
offline evaluation (ml/evaluate.py) it is set to each complaint's own
`filed_at`, complaint by complaint.
"""

from datetime import datetime
from typing import Optional

import networkx as nx
import pandas as pd


def build_graph(
    accounts: pd.DataFrame,
    transactions: pd.DataFrame,
    withdrawal_points: pd.DataFrame,
    withdrawal_events: pd.DataFrame,
    as_of: Optional[datetime] = None,
) -> nx.MultiDiGraph:
    """Build the directed fund-flow graph, optionally restricted to events
    strictly before `as_of` (point-in-time construction — see module docstring).
    """
    tx = transactions.copy()
    we = withdrawal_events.copy()
    tx["timestamp"] = pd.to_datetime(tx["timestamp"], format="%Y-%m-%dT%H:%M:%S")
    we["timestamp"] = pd.to_datetime(we["timestamp"], format="%Y-%m-%dT%H:%M:%S")

    if as_of is not None:
        as_of = pd.Timestamp(as_of)
        tx = tx[tx["timestamp"] < as_of]
        we = we[we["timestamp"] < as_of]

    G = nx.MultiDiGraph()

    for _, row in accounts.iterrows():
        G.add_node(
            f"acc_{row['id']}",
            node_kind="account",
            account_type=row["account_type"],
            bank_name=row["bank_name"],
        )

    for _, row in withdrawal_points.iterrows():
        G.add_node(
            f"wp_{row['id']}",
            node_kind="withdrawal_point",
            lat=row["lat"],
            lon=row["lon"],
            city=row["city"],
            bank_name=row["bank_name"],
        )

    for _, row in tx.iterrows():
        G.add_edge(
            f"acc_{row['from_account_id']}",
            f"acc_{row['to_account_id']}",
            kind="transfer",
            amount=row["amount"],
            timestamp=row["timestamp"],
            complaint_id=row["complaint_id"],
            hop_index=row["hop_index"],
        )

    for _, row in we.iterrows():
        G.add_edge(
            f"acc_{row['account_id']}",
            f"wp_{row['withdrawal_point_id']}",
            kind="withdrawal",
            amount=row["amount"],
            timestamp=row["timestamp"],
            complaint_id=row["complaint_id"],
        )

    return G


def load_and_build(data_dir: str, as_of: Optional[datetime] = None) -> nx.MultiDiGraph:
    """Convenience wrapper for scripts/tests: loads CSVs from `data_dir` and builds the graph."""
    from pathlib import Path

    d = Path(data_dir)
    accounts = pd.read_csv(d / "accounts.csv")
    transactions = pd.read_csv(d / "transactions.csv")
    withdrawal_points = pd.read_csv(d / "withdrawal_points.csv")
    withdrawal_events = pd.read_csv(d / "withdrawal_events.csv")
    return build_graph(accounts, transactions, withdrawal_points, withdrawal_events, as_of=as_of)


if __name__ == "__main__":
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../../../data/output"
    G = load_and_build(data_dir)
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    kinds = {}
    for _, d in G.nodes(data=True):
        kinds[d["node_kind"]] = kinds.get(d["node_kind"], 0) + 1
    print("node kinds:", kinds)
