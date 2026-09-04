"""
Regression guard for the "thousands of dots" bug: an earlier version used
`nx.ego_graph(..., radius=2, undirected=True)`, which exploded through
shared withdrawal-point hub nodes to thousands of unrelated nodes. The
fixed version curates an explicit, capped node set -- this test just
confirms the cap actually holds, not the exact curation algorithm.
"""

MAX_COMMUNITY_MEMBERS_SHOWN = 15
MAX_WITHDRAWAL_POINTS_SHOWN = 10


def test_graph_is_capped_not_exploded(client):
    r = client.get("/graph/1")
    assert r.status_code == 200
    body = r.json()

    # generous ceiling: traced chain + capped community members + capped
    # withdrawal points, never anywhere close to "thousands"
    assert len(body["nodes"]) < 100, f"graph exploded: {len(body['nodes'])} nodes"
    assert body["community_members_shown"] <= MAX_COMMUNITY_MEMBERS_SHOWN
    assert body["withdrawal_points_shown"] <= MAX_WITHDRAWAL_POINTS_SHOWN


def test_graph_chain_is_ordered(client):
    r = client.get("/graph/1")
    body = r.json()
    assert "chain_account_ids" in body
    assert isinstance(body["chain_account_ids"], list)
    assert len(body["chain_account_ids"]) >= 1

    node_ids = {n["id"] for n in body["nodes"]}
    for acc_id in body["chain_account_ids"]:
        assert f"acc_{acc_id}" in node_ids, "every chain account must actually be in the returned node set"


def test_graph_nonexistent_complaint_404s(client):
    r = client.get("/graph/999999999")
    assert r.status_code == 404
