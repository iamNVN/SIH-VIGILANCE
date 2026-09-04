# PredicTrace

Predictive cash-out intelligence for cybercrime complaints (SIH26184). See
`SIH26184_EXECUTION_BLUEPRINT.md` for the full architecture/rationale and
`PROGRESS_LOG.md` for what's built, verified, and why -- including two real
bugs found and fixed after the initial build (predicted points landing in
the sea; prediction confidence collapsing to near-identical low values).

## Run it (no Docker -- verified working)

Docker Desktop is not actually installed in this dev environment (service
registered, program files absent), so this is the path that's actually been
run and tested end-to-end.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt                  # macOS/Linux

# from repo root:
python data/generator/generate_synthetic_data.py --config data/generator/rings_config.yaml --outdir data/output --seed 42
python scripts/seed_db.py --data-dir data/output --reset    # loads generator CSVs into SQLite
cd backend/app
python -m ml.train                                          # trains + calibrates both models
python -m ml.evaluate                                        # prints the real Section 18 numbers
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

> **Why port 8001, not 8000:** a backend process from an earlier dev session
> got orphaned on port 8000 on this machine and could not be killed through
> any available channel (`Get-Process`/`taskkill`/`Stop-Process` all report
> "no such process" for the PID that Windows' own `Get-NetTCPConnection`
> says owns the socket -- a genuine OS-level inconsistency). A reboot would
> very likely clear it; until then, 8001 is the working port, and
> `frontend/vite.config.js`'s dev proxy already points there. If you're on a
> clean machine, port 8000 (FastAPI's default) works fine -- just update the
> proxy target back.

Then hit `http://127.0.0.1:8001/health`, `/docs` (Swagger UI), or any route
in `backend/app/api/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`. The demo login screen offers 4 personas
(2 investigators, city-scoped; 2 administrators, national scope) -- no
password, no real accounts. See "What's real vs. simulated" below.

## Run it (Docker, once actually available)

```bash
docker compose up --build
docker compose exec backend python scripts/seed_db.py --data-dir /app/data/output
docker compose exec backend python -m ml.train
```

`DATABASE_URL` is the only thing that changes between the two paths (see
`backend/app/core/config.py`) -- the SQLAlchemy models and every endpoint
are unchanged either way. **Not actually run in this environment** (no
Docker install) -- written and ready, unverified.

## Tests

```bash
# backend -- 23 tests against the real seeded DB and real trained models, no mocks
cd backend/app
../venv/Scripts/python -m pytest        # Windows
# ../venv/bin/pytest                     # macOS/Linux

# frontend -- one E2E spec covering the actual demo walkthrough (login,
# city-scoped dashboard, every sidebar page, all 4 case tabs, RBAC guard)
cd frontend
npm run test:e2e
```

Both assume the backend is already seeded and trained (see above) and, for
the E2E spec, that `npm run dev` is already running.

## What's real vs. simulated

See Blueprint Section 14. Short version: the synthetic dataset is disclosed
as synthetic (real NCRP data is access-restricted); every downstream step
(graph, features, models, calibration, SHAP, cross-complaint linking,
evaluation numbers) is real and actually runs against it. Login is a
demo-mode persona picker, not real authentication -- disclosed on the login
screen itself. Role-based access is real in the sense that it's enforced
server-side (an investigator's city scope actually filters API responses,
not just hidden UI) but the persona itself is self-declared, not
authenticated.

## Status

Backend (data generator, graph engine, ML pipeline, FastAPI app) and
frontend (React + Vite + Tailwind dashboard: Command Center, Cases, Network
Graph, Predictions, Alerts, Reports, Settings, and a 4-tab per-case
workspace) are both built and running. A test suite exists for both (see
"Tests" above) and a real screen recording of the golden-path walkthrough
lives at `backup_demo.mp4` (gitignored -- regenerate per `PROGRESS_LOG.md`).
See `PROGRESS_LOG.md` for the full current state and next steps.
