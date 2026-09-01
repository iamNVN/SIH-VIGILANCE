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
from graph_engine.build_graph import build_graph
from graph_engine.community import detect_communities
from graph_engine.features import known_chain_state
from models import Complaint

router = APIRouter(tags=["graph"])


def _complaint_or_404(complaint_id: int, db: Session) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, f"complaint {complaint_id} not found")
    return complaint


def _graph_and_communities(as_of: Optional[datetime]):
    ds = dataset_provider.get_dataset()
    G = build_graph(ds.accounts, ds.transactions, ds.withdrawal_points, ds.withdrawal_events, as_of=as_of)
    node_to_community = detect_communities(G)
    return ds, G, node_to_community


def _serialize_subgraph(G: nx.MultiDiGraph, H: nx.MultiDiGraph, node_to_community: dict, center_node: str) -> dict:
    nodes = []
    for n, data in H.nodes(data=True):
        node = {"id": n, "community_id": node_to_community.get(n), "is_center": n == center_node, **data}
        nodes.append(node)
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
    hops: int = Query(2, ge=1, le=4),
    db: Session = Depends(get_db),
):
    complaint = _complaint_or_404(complaint_id, db)
    as_of = as_of or complaint.filed_at

    ds, G, node_to_community = _graph_and_communities(as_of)
    frontier, chain_depth, _ = known_chain_state(ds, complaint_id, as_of)
    center_node = f"acc_{frontier}"
    if center_node not in G:
        raise HTTPException(404, "no graph data available for this complaint yet")

    H = nx.ego_graph(G, center_node, radius=hops, undirected=True)
    payload = _serialize_subgraph(G, H, node_to_community, center_node)
    payload.update({"complaint_id": complaint_id, "as_of": as_of.isoformat(), "chain_depth": chain_depth, "hops": hops})
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

    related = []
    for rid in related_ids:
        c = db.get(Complaint, rid)
        if c is not None:
            related.append({"complaint_id": rid, "filed_at": c.filed_at.isoformat(), "amount_lost": c.amount_lost})

    return {"complaint_id": complaint_id, "community_id": int(community_id), "community_size": len(member_ids), "related": related}


@router.get("/related/{complaint_id}")
def get_related_complaints(
    complaint_id: int,
    as_of: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    return compute_related_complaints(complaint_id, as_of, db)
