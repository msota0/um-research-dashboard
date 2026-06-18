"""Shared helpers for the API layer.

All endpoints return the same envelope the frontend expects
(see ``frontend/lib/api.ts``):

    { data, source, cached, fetched_at, institution_id, source_error? }
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import settings


def meta_time(db: Session, source: str) -> str | None:
    row = db.get(models.DatasetMeta, source)
    return row.fetched_at.isoformat() if row and row.fetched_at else None


def envelope(data: Any, db: Session, source: str = "openalex", **extra) -> dict:
    return {
        "data": data,
        "source": source,
        "cached": True,  # everything is precomputed in Postgres
        "fetched_at": meta_time(db, source),
        "institution_id": settings.inst_openalex_id,
        **extra,
    }
