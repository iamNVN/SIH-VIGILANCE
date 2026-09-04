def test_rings_all_meet_the_size_threshold(client):
    r = client.get("/rings?limit=200")
    assert r.status_code == 200
    rings = r.json()["rings"]
    assert len(rings) > 0, "no rings detected at all -- community detection likely broken"
    for ring in rings:
        assert ring["size"] >= 3, "a 'ring' below the 3-account threshold shouldn't be listed"
        assert ring["num_complaints"] >= 1
        assert ring["total_amount_at_risk"] >= 0
        assert ring["sample_complaint_id"] > 0


def test_rings_sorted_by_amount_at_risk_descending(client):
    rings = client.get("/rings?limit=200").json()["rings"]
    amounts = [r["total_amount_at_risk"] for r in rings]
    assert amounts == sorted(amounts, reverse=True)


def test_ring_detail_matches_list_entry(client):
    rings = client.get("/rings?limit=1").json()["rings"]
    assert len(rings) == 1
    ring_id = rings[0]["community_id"]

    detail = client.get(f"/rings/{ring_id}")
    assert detail.status_code == 200
    assert detail.json()["community_id"] == ring_id


def test_nonexistent_ring_404s(client):
    r = client.get("/rings/999999999")
    assert r.status_code == 404
