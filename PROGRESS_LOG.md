# PredicTrace — Progress Log (handoff to Claude Code)

This documents everything already built and verified in the prior web-chat session,
before continuing in Claude Code. Read this AND the attached
`SIH26184_EXECUTION_BLUEPRINT.md` before writing any new code — this file tells you
what already exists and what's already been debugged; the blueprint tells you the
overall plan, schema, and architecture.

## Environment note
The web-chat sandbox that built this had **no internet access** — could not
`pip install` FastAPI/SQLAlchemy/XGBoost/SHAP or run Postgres. Everything below was
built and tested using only pre-installed packages: `networkx`, `pandas`, `numpy`,
`scikit-learn`, `Jinja2`, `PyYAML`, stdlib `sqlite3`. That's why only the data
generator and graph builder exist so far — everything needing FastAPI/XGBoost/SHAP/
Postgres was blocked on missing packages, not because it wasn't planned yet.
**You have real internet — use it. Install everything in `backend/requirements.txt`
and actually run the full stack, not just write code for it.**

## What's DONE and VERIFIED (do not casually rewrite these — see bugs fixed below)

### 1. `data/generator/generate_synthetic_data.py` + `rings_config.yaml`
Generates the full synthetic dataset (no real NCRP data — access-restricted, disclosed
openly). Run: `python3 generate_synthetic_data.py` from `data/generator/`.

Verified output (seed=42): 744 victims/complaints, 1719 accounts (800 normal / 744
victim / 175 mule), 2680 transactions, 200 withdrawal points, 744 withdrawal events,
25 fraud rings.

**Verified properties (do not regress these):**
- Zero referential integrity violations (all foreign keys resolve).
- 134/175 mule accounts (77%) are reused across >1 distinct complaint — up to 36
  complaints sharing a single mule account. **This reuse is the entire point** — it's
  what makes cross-complaint ring linking and community detection possible. If a
  refactor drops this, the product's core signal is gone.
- Actionable/too-late split: 80.4% of complaints filed before ground-truth withdrawal
  (target ~80%).
- Ring geographic concentration: sampled ring showed 82% of withdrawals at its
  designated "hot" points (target ~70%, config-driven, some sampling variance expected).
- Unseen test-only patterns (40 complaints, single-hop, brand-new never-reused mule
  accounts) are 100% confined to the final 20% (test) time period, for genuine
  generalization testing later.
- Amounts are monotonically non-increasing hop to hop (money only loses value to fees
  through layering, never gains — see bug #3 below).
- `fraud_rings.csv` / `ring_id` column is GENERATOR-SIDE GROUND TRUTH ONLY for
  evaluation. **Never feed `ring_id` into the ML pipeline as a feature — that's label
  leakage.** The model must discover ring-like structure itself via Louvain community
  detection on the transaction graph; that discovered `community_id` is a different,
  legitimate, unsupervised feature.

**Three real bugs found and fixed during generation — don't reintroduce them:**
1. **Inconsistent timestamp precision.** `datetime.isoformat()` silently varies format
   depending on whether microseconds are non-zero, breaking downstream `pd.to_datetime`
   parsing. Fixed by using `.isoformat(timespec='seconds')` everywhere for datetimes
   (NOT for plain `.date().isoformat()` calls, which don't take that argument).
2. **`nx.DiGraph` instead of `nx.MultiDiGraph` silently collapsed repeated edges.**
   2680 transactions had only 1850 unique (from,to) pairs; 744 withdrawal events had
   only 464 unique (account, withdrawal_point) pairs. A plain DiGraph overwrites the
   earlier edge whenever the same pair repeats — which **destroys exactly the
   mule-account-reuse signal the whole product depends on**. Fixed by using
   `nx.MultiDiGraph()`. Verified fix: edge count went from 2314 to 3424 (now exactly
   matches 2680 + 744, zero data loss).
3. **Amount could grow across hops.** Original code applied `(1 - fee) * (1 + jitter)`
   where jitter was `±15%`, which could make money *increase* during laundering —
   physically wrong. Fixed to `(1 - fee - extra_loss)` where `extra_loss` is one-sided
   (`0` to `+15%`), guaranteeing strictly non-increasing amounts hop to hop. Verified:
   `amount_lost - final_withdrawal_amount` is now always >= 0 across all 744 cases.

### 2. `backend/app/graph_engine/build_graph.py`
Builds the fund-flow graph from the generator's CSVs (or, in the real backend, from
DB query results — same function signature, just pass DataFrames from SQLAlchemy
queries instead of `pd.read_csv`). Supports `as_of` point-in-time filtering — this is
what the evaluation script MUST use per-complaint (`as_of = complaint.filed_at`) to
avoid leaking future events into training/prediction. See Blueprint Section 18.

Verified: `python3 build_graph.py ../../../data/output` → 1919 nodes (1719 accounts +
200 withdrawal points), 3424 edges (2680 transfer + 744 withdrawal), matching the raw
row counts exactly — confirms no more silent edge collapsing.

## What's NOT started yet (this is today's job)
Everything else in the Blueprint's Section 21 repo structure and Section 4 "must
build by 5 Sep" table:
- `graph_engine/community.py` — Louvain community detection (`networkx.algorithms
  .community.louvain_communities` is built into networkx 3.6+, no extra package
  needed — confirmed available)
- `graph_engine/features.py` — the full feature pipeline (graph + temporal-decay +
  geospatial-density) per candidate withdrawal point, feeding the ranking model
- `ml/baseline_model.py` (Random Forest, tabular-only) + `ml/advanced_model.py`
  (XGBoost, fused features) + `ml/train.py` + `ml/evaluate.py` (precision@1/@5,
  hit-rate@2km, lead time, calibration — exact experiment in Blueprint Section 18,
  including point-in-time graph construction per complaint)
- `ml/calibration.py` (CalibratedClassifierCV) + `ml/explain.py` (SHAP)
- `brief/template_brief.py` (Jinja2 — Jinja2 is available and tested-friendly)
- The entire FastAPI app: `main.py`, all of `api/`, `models/` (SQLAlchemy), `core/`
- `docker-compose.yml`, seed script, Dockerfile
- Frontend is a separate, later concern — focus on backend today per the Blueprint's
  Section 5 Day 1-2 scope

## Ground rules for continuing (from the Blueprint — don't relitigate these)
- No trained GNN before 5 Sep (Section 9) — graph-derived features feed XGBoost.
- NetworkX in-memory, not Neo4j (Section 8) — sufficient at this data scale.
- Single Python FastAPI backend, not split Node+Python (Section 2 decision).
- Never use `ring_id` as a model feature (see bug context above — it's the label).
- Every claim to judges must be backed by a real, run experiment — no invented numbers
  (Section 18).

---

## 2026-09-03 session (Claude Code, real internet, real packages) — everything below is DONE and VERIFIED

**Environment note:** Docker Desktop's *service* is registered on this machine but the
actual program files are absent (no `docker.exe` anywhere) — Docker is not usable here.
Ran the full stack on SQLite instead; every SQLAlchemy model is plain/portable and runs
unchanged against Postgres once Docker actually is available (`docker-compose.yml` is
written and ready, just untested against a real Postgres). `DATABASE_URL` is the only
thing that changes — see `backend/app/core/config.py`.

### Built, in order
1. `graph_engine/community.py` — Louvain (`networkx.algorithms.community.louvain_communities`)
   on an undirected weighted projection of the account⇄account TRANSFER edges (withdrawal
   points deliberately excluded from the projection — they're a many-to-one fan-in that
   would otherwise merge unrelated rings). Verified: 1555 accounts → 126 communities on the
   full dataset.
2. `graph_engine/features.py` — the fused feature pipeline. Key design decisions, all
   documented in the module's own docstrings:
   - **What's "known" at complaint time:** hop-0 (victim→first mule) is always known —
     it's the victim's own bank statement, i.e. the "first known transaction reference"
     Blueprint Section 2 lists as an input. Every later hop is only known once its own
     timestamp is before `as_of`, traced via `transactions.complaint_id` (a real schema
     column per Section 6, not generator-only ground truth like `ring_id`).
   - **Two leakage guards, not one:** point-in-time graph construction (existing,
     Section 18) PLUS **self-exclusion** — a complaint's own transactions/withdrawal_event
     are always excluded from any historical aggregate computed for it. This second guard
     was necessary because ~20% of complaints are "too-late" (filed after their own
     withdrawal already happened, Section 6) — without self-exclusion, a too-late
     complaint's own cash-out would leak into "historical density near the true point"
     for that very complaint.
   - **`account_type` (mule/victim/normal) is NEVER a feature** — same leakage class as
     `ring_id`. An investigator doesn't know a priori which accounts are mules; that's the
     question being solved. Caught this myself while designing the feature set — worth
     flagging if anyone's tempted to add it back as a "quick win" feature later.
   - Features: `chain_depth`, `recency_decay` (single-kernel Hawkes approximation, Section
     10), `degree_centrality_global`, `community_size`, `local_betweenness` (computed on
     the small community-induced subgraph, not the full graph — cheap), `community_num_
     complaints` (cross-complaint linking signal), `global_geo_density` and
     `community_geo_density` (Gaussian-kernel haversine, 2km bandwidth matching the
     hit-rate metric). Baseline gets tabular + `global_geo_density` only; advanced gets
     everything.
   - **Pointwise binary classification, not `XGBRanker`** — deliberate, so
     `CalibratedClassifierCV` (which needs a probabilistic classifier) can produce a
     genuine calibrated confidence per prediction. Documented in the module docstring.
   - Runtime: ~0.25s/complaint worst case (late-window, largest graph); full 784-complaint
     dataset in a couple of minutes. Results cached to CSV (`ml/artifacts/features_train.csv`
     / `features_test.csv`) so train.py/evaluate.py don't recompute every run.
3. SQLAlchemy models (`models/orm.py`) mirroring Section 6 exactly + `core/db.py` +
   `core/config.py` (SQLite-by-default, see environment note) + `scripts/seed_db.py`.
   Verified: seeds all 744 victims/complaints, 1719 accounts, 2680 transactions, 200
   withdrawal points, 744 withdrawal events, 25 fraud rings with zero errors.
4. `ml/baseline_model.py` (Random Forest, tabular-only), `ml/advanced_model.py` (XGBoost,
   fused features), `ml/calibration.py`, `ml/explain.py` (SHAP `TreeExplainer`),
   `ml/pipeline.py` (shared temporal-split + feature-cache plumbing so train.py and
   evaluate.py can never silently diverge), `ml/train.py`.

   **Two real bugs found and fixed while wiring these up — don't reintroduce them:**
   - **xgboost 2.1.1 is incompatible with sklearn 1.8's tag-based estimator system.**
     `XGBClassifier().__sklearn_tags__().estimator_type` came back `None` under sklearn
     1.8, so `CalibratedClassifierCV` + `FrozenEstimator` (the current, non-deprecated way
     to calibrate an already-fitted estimator — `cv="prefit"` was removed) raised
     `"FrozenEstimator should either be a classifier... Got a regressor"`. Fixed by
     bumping to **xgboost 2.1.4** (confirmed `is_classifier()` now returns `True`).
     `requirements.txt` updated accordingly.
   - **SHAP's `TreeExplainer.shap_values` rejects a single-row slice of a mixed-dtype
     DataFrame.** `row[feature_columns].to_frame().T` inherits `dtype=object` from the
     source row (which also has string/id columns), even though every value in the slice
     is numeric — XGBoost's DMatrix construction then rejects the whole frame. Fixed with
     an explicit `.astype(float)` in `ml/explain.py`'s `explain_row`.
   - Calibration splits by **whole complaint**, not by row (`ml/calibration.py`'s
     `split_by_complaint`) — rows from the same complaint share a graph/community
     snapshot and are correlated; row-level splitting would leak a complaint's own
     candidates across the model-fit and calibration subsets.
5. `ml/evaluate.py` — the exact Section 18 experiment. **Real numbers, temporal split
   (595 train / 149 test complaints), run against our own generated data:**

   | Metric | Baseline (RF, tabular-only) | Advanced (XGBoost, fused) |
   |---|---|---|
   | Precision@1 | 0.040 | **0.174** |
   | Precision@5 (=Recall@5) | 0.121 | **0.530** |
   | Hit-rate within 2km @5 | 0.221 | **0.591** |
   | Mean rank of true point | 18.80 | **10.21** |
   | Brier score (lower=better) | 0.0249 | **0.0232** |

   Lift: **advanced Precision@5 − baseline Precision@5 = +0.409**. Lead time (125
   actionable test complaints): mean 4.46h / median 4.19h available to act before
   cash-out; 4.99h mean when the top-5 actually contains the true point. No prediction
   crossed the 0.5 high-confidence threshold in this run (both models are conservatively
   calibrated on ~40-way candidate sets) — false-positive-rate-at-high-confidence is
   reportable as "none observed at threshold 0.5" honestly, not fabricated; worth
   lowering the reporting threshold (e.g. 0.3) if judges ask for this metric specifically.
   Full report: `backend/app/ml/artifacts/evaluation_report.json`.
6. `brief/template_brief.py` (Jinja2) — verified rendering against a real `/predict`
   response.
7. Full FastAPI app: `main.py` + `api/{complaints,graph,predict,explain,brief,evaluation,
   stream}.py`, `core/model_registry.py` (loads joblib artifacts once), `core/
   dataset_provider.py` (builds the same `Dataset` object from the live DB via
   `pandas.read_sql_table` instead of CSVs). `docker-compose.yml` + `backend/Dockerfile`
   written and ready (untested — no Docker here, see environment note).

   **Verified live against a running server** (seeded SQLite DB, trained models):
   `GET /health`, `GET/POST /complaints`, `POST /predict/{id}` (real top-5 + real SHAP +
   real ring narrative), `GET /explain/{id}`, `GET /related/{id}` (real cross-complaint
   linking — e.g. complaint 410 correctly surfaced 26 other complaints sharing its
   discovered community), `GET /graph/{id}` (2-hop ego-graph, capped per Section 24),
   `GET /evaluation` (serves the real numbers above), `GET /brief/{id}` (real rendered
   brief text), `POST /stream/trigger-next` + `/stream/reset` (manual kill-switch replay,
   Section 24) — the full WebSocket auto-replay path is written
   (`GET /stream/live-complaints`) but not yet exercised end-to-end with a real client.

## What's NOT started yet
- NLP entity extraction (regex/spaCy) on narrative text — out of today's scope, still
  open per the original list.
- Frontend (React dashboard, 8 screens) — explicitly deferred, backend-only today.
- Live-stream WebSocket replay: written, unit-hit via the manual trigger endpoint, not
  yet tested with an actual WebSocket client end-to-end.
- Docker/Postgres path: written, not runnable/tested in this environment (no Docker
  install) — SQLite path is what's actually been verified.
