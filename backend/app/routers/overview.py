"""Overview tab + cache status."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import get_db
from backend.app.deps import envelope

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/institution/overview")
def institution_overview(db: Session = Depends(get_db)):
    ov = db.get(models.InstitutionOverview, 1)
    by_year = (
        db.query(models.PublicationsByYear)
        .filter(models.PublicationsByYear.source == "openalex")
        .order_by(models.PublicationsByYear.year)
        .all()
    )
    data = {
        "display_name": ov.display_name if ov else "University of Mississippi",
        "works_count": ov.works_count if ov else 0,
        "cited_by_count": ov.cited_by_count if ov else 0,
        "h_index": ov.h_index if ov else 0,
        "i10_index": ov.i10_index if ov else 0,
        "open_access_pct": ov.open_access_pct if ov else 0.0,
        "counts_by_year": [
            {"year": r.year, "works_count": r.count, "cited_by_count": 0}
            for r in by_year
        ],
    }
    return envelope(data, db)


@router.get("/cache-status")
def cache_status(db: Session = Depends(get_db)):
    return {
        "openalex_fetched_at": (
            m.fetched_at.isoformat()
            if (m := db.get(models.DatasetMeta, "openalex")) and m.fetched_at
            else None
        ),
        "dimensions_fetched_at": (
            m.fetched_at.isoformat()
            if (m := db.get(models.DatasetMeta, "dimensions")) and m.fetched_at
            else None
        ),
        "works": db.query(func.count(models.Work.id)).scalar(),
        "authors": db.query(func.count(models.Author.id))
        .filter(models.Author.scholar_source.isnot(None))
        .scalar(),
    }
