"""main.py -- FastAPI entrypoint, Blueprint Section 21."""

import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import brief, complaints, evaluation, events, explain, feed, graph, predict, rings, settings, stats, stream
from api.feed import _cached_feed
from api.rings import _cached_rings, log_initial_ring_detections
from core.activity_simulator import start_simulator
from core.db import Base, engine
from core.model_registry import registry
from graph_engine.features import NoKnownTransactionChain

app = FastAPI(title="PredicTrace API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NoKnownTransactionChain)
def no_chain_handler(request: Request, exc: NoKnownTransactionChain):
    return JSONResponse(
        status_code=422,
        content={"detail": (
            f"Complaint {exc.complaint_id} has no recorded transaction chain yet -- "
            "graph/prediction/explanation need at least the victim's first known transfer."
        )},
    )


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    # Command Center's first load fires several requests that all depend on
    # the batch feed / rings caches (see feed.py, rings.py) -- without this,
    # whichever real user opens the app first pays that ~5-6s cold-cache
    # cost themselves. Warming both once here in a background thread means
    # by the time anyone's browser has finished loading the page, the first
    # real request already hits a warm cache.
    def _warm_caches():
        if registry.ready:
            _cached_feed()
        _cached_rings()
        log_initial_ring_detections()
        # Only after the caches above are warm -- the simulator's
        # "prediction"/"ring_found" events read from them directly (see
        # activity_simulator.py) and need real data to sample from from
        # its very first tick, not an empty cache.
        start_simulator()

    threading.Thread(target=_warm_caches, daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok", "models_ready": registry.ready}


@app.get("/system/info")
def system_info():
    return {
        "models_ready": registry.ready,
        "metadata": registry.metadata,
    }


app.include_router(complaints.router)
app.include_router(graph.router)
app.include_router(predict.router)
app.include_router(explain.router)
app.include_router(brief.router)
app.include_router(evaluation.router)
app.include_router(stats.router)
app.include_router(stream.router)
app.include_router(rings.router)
app.include_router(feed.router)
app.include_router(events.router)
app.include_router(settings.router)
