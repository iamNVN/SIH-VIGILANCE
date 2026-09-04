"""
City-scoping is the real, server-enforced part of this project's RBAC (see
PROGRESS_LOG.md's RBAC section) -- these tests hit the actual filtered
endpoints directly, not just the frontend's use of them. Assumes the
seeded dataset spans multiple cities including Chennai (true of
generate_synthetic_data.py's default 5-city config).
"""

CITY = "Chennai"


def test_complaints_list_respects_city_filter(client):
    r = client.get(f"/complaints?limit=50&city={CITY}")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0, f"no seeded complaints in {CITY} -- adjust CITY or check seed data"
    assert all(row["victim_city"] == CITY for row in rows)


def test_complaints_count_matches_filtered_list(client):
    count = client.get(f"/complaints/count?city={CITY}").json()["total"]
    unscoped_count = client.get("/complaints/count").json()["total"]
    assert 0 < count < unscoped_count, "a city filter should narrow the total, not match or exceed it"


def test_stats_scope_reflects_city(client):
    scoped = client.get(f"/stats?city={CITY}").json()
    national = client.get("/stats").json()
    assert scoped["scope"] == CITY
    assert national["scope"] == "national"
    assert scoped["total_complaints"] < national["total_complaints"]
    assert scoped["total_amount_at_risk"] <= national["total_amount_at_risk"]


def test_rings_city_filter_only_returns_touching_rings(client):
    r = client.get(f"/rings?city={CITY}")
    assert r.status_code == 200
    rings = r.json()["rings"]
    for ring in rings:
        assert CITY in ring["cities_touched"]


def test_feed_endpoints_accept_city_filter(client):
    for path in ["/feed/predictions", "/feed/alerts"]:
        r = client.get(f"{path}?city={CITY}&limit=20")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["victim_city"] == CITY
