# PredicTrace -- Backend

Predictive cash-out intelligence for cybercrime complaints. See
`SIH26184_EXECUTION_BLUEPRINT.md` for the full architecture/rationale and
`PROGRESS_LOG.md` for what's built, verified, and why.

## Run it (no Docker -- verified working)

Docker Desktop is not actually installed in this dev environment (service
registered, program files absent), so this is the path that's been run and
tested end-to-end today.

```bash
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt                  # macOS/Linux

# from repo root:
python scripts/seed_db.py --data-dir data/output            # loads generator CSVs into SQLite
cd backend/app
python -m ml.train        --data-dir ../../data/output      # trains + calibrates both models
python -m ml.evaluate      --data-dir ../../data/output      # prints the real Section 18 numbers
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then hit `http://127.0.0.1:8000/health`, `/docs` (Swagger UI), or any route
in `backend/app/api/`.

## Run it (Docker, once actually available)

```bash
docker compose up --build
docker compose exec backend python scripts/seed_db.py --data-dir /app/data/output
docker compose exec backend python -m ml.train
```

`DATABASE_URL` is the only thing that changes between the two paths (see
`backend/app/core/config.py`) -- the SQLAlchemy models and every endpoint
are unchanged either way.

## What's real vs. simulated

See Blueprint Section 14. Short version: the synthetic dataset is disclosed
as synthetic; every downstream step (graph, features, models, calibration,
SHAP, cross-complaint linking, evaluation numbers) is real and actually
runs against it.

## Status

Backend (data generator, graph engine, ML pipeline, FastAPI app) is built
and running today. Frontend dashboard and NLP entity extraction are not yet
started -- see `PROGRESS_LOG.md` for the current state and next steps.
