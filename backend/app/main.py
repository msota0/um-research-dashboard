"""FastAPI application entrypoint.

Routers are registered here. Each router is a self-contained module under
`backend/app/routers/` that only performs READ-ONLY queries against Postgres —
all data is precomputed by the ingestion pipeline (`backend/ingest/`).

Run locally:  uvicorn backend.app.main:app --reload --port 5000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings

app = FastAPI(title="UM Research Dashboard API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


from backend.app.routers import authors, misc, overview, publications  # noqa: E402

app.include_router(overview.router)
app.include_router(publications.router)
app.include_router(authors.router)
app.include_router(misc.router)
