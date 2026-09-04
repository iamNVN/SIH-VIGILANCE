"""
Smoke tests for the prediction pipeline against the real seeded DB and
real trained models -- no mocks. Complaint #1 is assumed to exist with a
real transaction chain (true of any freshly seeded dataset from
generate_synthetic_data.py); if it doesn't, that's itself worth knowing.
"""


def test_models_ready(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["models_ready"] is True, (
        "models not trained -- run `python -m ml.train` from backend/app before testing"
    )


def test_predict_known_good_complaint(client):
    r = client.post("/predict/1")
    assert r.status_code == 200
    body = r.json()

    assert body["complaint_id"] == 1
    assert 1 <= len(body["predictions"]) <= 5
    assert body["n_candidates"] > 0

    for p in body["predictions"]:
        assert 0.0 <= p["confidence"] <= 1.0
        assert p["urgency"] in {"HIGH", "MEDIUM", "LOW"}
        assert isinstance(p["lat"], float) and isinstance(p["lon"], float)
        assert len(p["explanation"]["top_features"]) > 0

    ranks = [p["rank"] for p in body["predictions"]]
    assert ranks == sorted(ranks)  # ranked, not just returned in arbitrary order
    confidences = [p["confidence"] for p in body["predictions"]]
    assert confidences == sorted(confidences, reverse=True)  # rank 1 = highest confidence


def test_predict_urgency_actually_varies(client):
    # Regression guard for a real bug: urgency used to be computed from an
    # absolute confidence >= 0.5 threshold that this calibrated model can
    # never reach with ~40 candidates/city, so every single complaint came
    # back "MEDIUM" forever. Confirms at least two distinct urgency values
    # show up across a small sample -- not a hardcoded single value.
    seen = set()
    for complaint_id in [1, 50, 100, 200, 300]:
        r = client.post(f"/predict/{complaint_id}")
        if r.status_code == 200:
            seen.add(r.json()["predictions"][0]["urgency"])
    assert len(seen) >= 2, f"urgency barely varies across sample complaints: {seen}"


def test_predict_nonexistent_complaint_404s(client):
    r = client.post("/predict/999999999")
    assert r.status_code == 404


def test_predict_complaint_with_no_chain_yet_422s_not_500(client):
    # Regression guard for the exact #745 bug: a complaint with no recorded
    # transaction chain must fail with a clear 422, never an unhandled 500.
    victim = client.get("/complaints/1").json()
    created = client.post("/complaints", json={
        "victim_id": victim["victim_id"],
        "amount_lost": 1000.0,
        "narrative_text": "pytest throwaway complaint with no transaction history",
        "bank_name": "Test Bank",
    })
    assert created.status_code == 201
    new_id = created.json()["id"]
    try:
        r = client.post(f"/predict/{new_id}")
        assert r.status_code == 422
        assert "no recorded transaction chain" in r.json()["detail"]
    finally:
        # Keep the seeded DB clean -- this is exactly the kind of stray
        # test row that caused the original #745 confusion.
        from core.db import SessionLocal
        from models import Complaint

        db = SessionLocal()
        try:
            row = db.get(Complaint, new_id)
            if row is not None:
                db.delete(row)
                db.commit()
        finally:
            db.close()
