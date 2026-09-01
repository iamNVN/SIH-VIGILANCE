"""
graph.py -- subgraph-for-a-case endpoint + cross-complaint linking
(Blueprint Section 8/12 screen 3 "Transaction Graph", screen 5 "Investigation
View"). Subgraph is capped to a 2-hop neighborhood per Section 24's kill-
switch ("Graph visualization performance ... cap the displayed subgraph to a
2-hop neighborhood ... also more legible for judges anyway").
"""

from datetime import datetime
from typing import Optional

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core import dataset_provider
from core.db import get_db
from graph_engine.features import known_chain_accounts, known_chain_state
from graph_engine.graph_cache import get_graph_and_communities
from models import Complaint

router = APIRouter(tags=["graph"])

# Hard caps on what gets drawn -- see get_case_graph's docstring for why a
# naive BFS-radius approach can't be used here at all.
MAX_COMMUNITY_MEMBERS_SHOWN = 15
MAX_WITHDRAWAL_POINTS_SHOWN = 10


def _complaint_or_404(complaint_id: int, db: Session) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")
    return complaint


def _graph_and_communities(as_of: Optional[datetime]):
    ds = dataset_provider.get_dataset()
    G, node_to_community = get_graph_and_communities(ds, as_of)
    return ds, G, node_to_community


def _serialize_subgraph(H: nx.MultiDiGraph, node_to_community: dict, center_node: str, chain_nodes: set) -> dict:
    nodes = []
    for n, data in H.nodes(data=True):
        nodes.append({
            "id": n,
            "community_id": node_to_community.get(n),
            "is_center": n == center_node,
            "in_chain": n in chain_nodes,
            **data,
        })
    edges = []
    for u, v, data in H.edges(data=True):
        edges.append({
            "source": u, "target": v,
            "kind": data.get("kind"), "amount": data.get("amount"),
            "timestamp": data.get("timestamp").isoformat() if hasattr(data.get("timestamp"), "isoformat") else data.get("timestamp"),
            "complaint_id": data.get("complaint_id"),
        })
    return {"nodes": nodes, "edges": edges}


@router.get("/graph/{complaint_id}")
def get_case_graph(
    complaint_id: int,
    as_of: Optional[datetime] = Query(None, description="Defaults to the complaint's own filed_at (point-in-time)."),
    db: Session = Depends(get_db),
):
    """
    Builds a small, legible, CURATED subgraph -- not a generic BFS/ego-graph
    radius. An earlier version used `nx.ego_graph(..., radius=2, undirected=True)`,
    which looked reasonable but explodes in practice: withdrawal points are
    shared by hundreds of unrelated accounts (one popular ATM can have
    dozens of withdrawal events from completely different rings), so a
    2-hop walk through even one such point pulls in most of the dataset --
    exactly the "thousands of dots" bug this replaces.

    Instead the node set is built explicitly and capped:
    1. The complaint's own traced chain (small, always shown in full).
    2. Up to MAX_COMMUNITY_MEMBERS_SHOWN other accounts from the same
       discovered Louvain community, prioritizing accounts directly
       connected to the traced chain, then by degree (the more
       "hub-like" accounts are the ones worth seeing).
    3. Up to MAX_WITHDRAWAL_POINTS_SHOWN withdrawal points that are
       actually connected to one of the selected accounts.
    Edges are then taken only from `G.subgraph(selected_nodes)` -- never a
    BFS -- so a hub node can never pull in accounts we didn't choose.
    """
    complaint = _complaint_or_404(complaint_id, db)
    as_of = as_of or complaint.filed_at

    ds, G, node_to_community = _graph_and_communities(as_of)
    chain_accounts = known_chain_accounts(ds, complaint_id, as_of)
    frontier, chain_depth, _ = known_chain_state(ds, complaint_id, as_of)
    center_node = f"acc_{frontier}"
    if center_node not in G:
        raise HTTPException(404, "no graph data available for this complaint yet")

    chain_nodes = {f"acc_{a}" for a in chain_accounts}
    community_id = node_to_community.get(center_node)

    all_community_nodes = {n for n, c in node_to_community.items() if c == community_id} if community_id is not None else set()
    community_total_size = len(all_community_nodes)
    other_community_nodes = all_community_nodes - chain_nodes

    neighbors_of_chain = set()
    for n in chain_nodes:
        if n in G:
            neighbors_of_chain.update(G.predecessors(n))
            neighbors_of_chain.update(G.successors(n))

    ranked_candidates = sorted(
        other_community_nodes,
        key=lambda n: (n not in neighbors_of_chain, -(G.in_degree(n) + G.out_degree(n))),
    )
    selected_community_nodes = set(ranked_candidates[:MAX_COMMUNITY_MEMBERS_SHOWN])

    selected_accounts = chain_nodes | selected_community_nodes
    withdrawal_candidates = set()
    for n in selected_accounts:
        if n in G:
            withdrawal_candidates.update(s for s in G.successors(n) if s.startswith("wp_"))
    selected_withdrawal_points = set(list(withdrawal_candidates)[:MAX_WITHDRAWAL_POINTS_SHOWN])

    final_nodes = selected_accounts | selected_withdrawal_points
    H = G.subgraph(final_nodes)

    payload = _serialize_subgraph(H, node_to_community, center_node, chain_nodes)
    payload.update({
        "complaint_id": complaint_id,
        "as_of": as_of.isoformat(),
        "chain_depth": chain_depth,
        # The traced chain IN ORDER (victim -> hop 1 -> ... -> frontier) --
        # already computed by known_chain_accounts(); exposed directly so the
        # UI can render a clean step-by-step trail instead of making the
        # reader infer sequence from a tangle of graph edges.
        "chain_account_ids": chain_accounts,
        "community_id": int(community_id) if community_id is not None else None,
        "community_size_total": community_total_size,
        "community_members_shown": len(selected_community_nodes),
        "withdrawal_points_shown": len(selected_withdrawal_points),
    })
    return payload


def compute_related_complaints(complaint_id: int, as_of: Optional[datetime], db: Session) -> dict:
    """Cross-complaint linking (Blueprint Section 4/8/12): other complaints
    sharing the frontier account's discovered Louvain community -- this is
    what surfaces a fraud RING rather than an isolated case. Shared by the
    `/related/{id}` route and brief.py (direct function call, not a self
    HTTP round-trip)."""
    complaint = _complaint_or_404(complaint_id, db)
    as_of = as_of or complaint.filed_at

    ds, G, node_to_community = _graph_and_communities(as_of)
    frontier, _, _ = known_chain_state(ds, complaint_id, as_of)
    frontier_node = f"acc_{frontier}"
    community_id = node_to_community.get(frontier_node)
    if community_id is None:
        return {"complaint_id": complaint_id, "community_id": None, "related": []}

    member_ids = {int(n.split("_", 1)[1]) for n, c in node_to_community.items() if c == community_id and n.startswith("acc_")}

    tx = ds.transactions[
        (ds.transactions["timestamp"] < as_of) & (ds.transactions["complaint_id"] != complaint_id)
        & (ds.transactions["from_account_id"].isin(member_ids) | ds.transactions["to_account_id"].isin(member_ids))
    ]
    we = ds.withdrawal_events[
        (ds.withdrawal_events["timestamp"] < as_of) & (ds.withdrawal_events["complaint_id"] != complaint_id)
        & (ds.withdrawal_events["account_id"].isin(member_ids))
    ]
    related_ids = sorted(set(tx["complaint_id"].dropna().astype(int)) | set(we["complaint_id"].dropna().astype(int)))

    accounts_by_id = ds.accounts.set_index("id")
    wpoints_by_id = ds.withdrawal_points.set_index("id")

    related = []
    for rid in related_ids:
        c = db.get(Complaint, rid)
        if c is None:
            continue

        # The SPECIFIC shared account(s) that connect this complaint to the
        # base case -- a real, derivable "why", not a generic community
        # match. A complaint can be linked via a shared mule account and/or
        # a shared cash-out point; both are surfaced when present.
        rid_tx = tx[tx["complaint_id"] == rid]
        rid_we = we[we["complaint_id"] == rid]
        shared_account_ids = sorted(
            set(rid_tx["from_account_id"]) & member_ids
            | set(rid_tx["to_account_id"]) & member_ids
            | set(rid_we["account_id"]) & member_ids
        )
        shared_accounts = [
            {
                "account_id": int(aid),
                "bank_name": accounts_by_id.loc[aid, "bank_name"] if aid in accounts_by_id.index else None,
                "account_number_fake": accounts_by_id.loc[aid, "account_number_fake"] if aid in accounts_by_id.index else None,
            }
            for aid in shared_account_ids
        ]

        shared_point_ids = sorted(set(rid_we["withdrawal_point_id"].dropna().astype(int)))
        shared_withdrawal_points = [
            {
                "withdrawal_point_id": int(pid),
                "name": wpoints_by_id.loc[pid, "name"],
                "city": wpoints_by_id.loc[pid, "city"],
            }
            for pid in shared_point_ids
            if pid in wpoints_by_id.index
        ]

        related.append({
            "complaint_id": rid,
            "filed_at": c.filed_at.isoformat(),
            "amount_lost": c.amount_lost,
            "bank_name": c.bank_name,
            "same_bank": c.bank_name == complaint.bank_name,
            "shared_accounts": shared_accounts,
            "shared_withdrawal_points": shared_withdrawal_points,
        })

    return {"complaint_id": complaint_id, "community_id": int(community_id), "community_size": len(member_ids), "related": related}


@router.get("/related/{complaint_id}")
def get_related_complaints(
    complaint_id: int,
    as_of: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    return compute_related_complaints(complaint_id, as_of, db)
