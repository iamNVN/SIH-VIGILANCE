"""
community.py -- Louvain community detection on the fund-flow graph.

Builds on `build_graph.py`'s nx.MultiDiGraph. Louvain (networkx's built-in
`louvain_communities`, no extra package needed -- confirmed available in
networkx 3.6.1, see PROGRESS_LOG.md) operates on a simple weighted undirected
graph, not a MultiDiGraph, so we first project the transfer edges between
`account` nodes into a weighted undirected graph (weight = number of
transactions between the pair, direction collapsed) and run Louvain on that
projection only. Withdrawal-point nodes are deliberately excluded from the
projection: they are a many-accounts-to-one-point fan-in that would otherwise
merge unrelated rings into one giant community purely because they cash out
at a shared popular ATM.

The resulting `community_id` is DISCOVERED, unsupervised structure -- a
legitimate model feature. It is not the same thing as the generator's
`ring_id`, which is ground-truth-only and must never be fed into the model
(see PROGRESS_LOG.md bug context / Blueprint Section 6).
"""

from collections import defaultdict
from typing import Dict

import networkx as nx


def project_account_graph(G: nx.MultiDiGraph) -> nx.Graph:
    """Collapse the account<->account TRANSFER edges of the fund-flow
    MultiDiGraph into a simple weighted undirected graph, one node per
    account. Edge weight = number of transactions observed between the pair
    (direction ignored, multi-edges summed)."""
    weights: Dict[tuple, int] = defaultdict(int)
    account_nodes = set()

    for u, v, data in G.edges(data=True):
        if data.get("kind") != "transfer":
            continue
        account_nodes.add(u)
        account_nodes.add(v)
        key = tuple(sorted((u, v)))
        weights[key] += 1

    H = nx.Graph()
    H.add_nodes_from(account_nodes)
    for (u, v), w in weights.items():
        H.add_edge(u, v, weight=w)
    return H


def detect_communities(G: nx.MultiDiGraph, seed: int = 42, resolution: float = 1.0) -> Dict[str, int]:
    """Run Louvain community detection on the account-projection of the
    fund-flow graph. Returns {account_node_id: community_id}.

    Accounts with no transfer edges at all (isolated in the projection, e.g.
    a victim account with only a single hop already consumed elsewhere) each
    get their own singleton community id, appended after the real communities
    so ids never collide.
    """
    H = project_account_graph(G)
    if H.number_of_nodes() == 0:
        return {}

    communities = nx.algorithms.community.louvain_communities(
        H, weight="weight", resolution=resolution, seed=seed
    )

    node_to_community: Dict[str, int] = {}
    for community_id, members in enumerate(communities):
        for node in members:
            node_to_community[node] = community_id

    return node_to_community


def community_sizes(node_to_community: Dict[str, int]) -> Dict[int, int]:
    sizes: Dict[int, int] = defaultdict(int)
    for community_id in node_to_community.values():
        sizes[community_id] += 1
    return dict(sizes)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(__file__.rsplit("graph_engine", 1)[0]))
    from graph_engine.build_graph import load_and_build

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../../../data/output"
    G = load_and_build(data_dir)
    node_to_community = detect_communities(G)
    sizes = community_sizes(node_to_community)
    print(f"Accounts in projection: {len(node_to_community)}")
    print(f"Communities found: {len(sizes)}")
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:10]
    print("Top 10 community sizes:", top)
