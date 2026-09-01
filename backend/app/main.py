"""main.py -- FastAPI entrypoint, Blueprint Section 21."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import brief, complaints, evaluation, explain, graph, predict, stream
from core.db import Base, engine
from core.model_registry import registry

app = FastAPI(title="PredicTrace API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "models_ready": registry.ready}


app.include_router(complaints.router)
app.include_router(graph.router)
app.include_router(predict.router)
app.include_router(explain.router)
app.include_router(brief.router)
app.include_router(evaluation.router)
app.include_router(stream.router)
