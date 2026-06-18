"""Publications tab: by-year, by-field, by-type, open-access, list.

All counts use only canonical, non-excluded works (dedup-clean).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import get_db
from backend.app.deps import envelope

router = APIRouter(prefix="/api/publications", tags=["publications"])

# Reusable filter: a work that counts in headline figures.
def _canonical(q):
    return q.filter(
        models.Work.is_duplicate_of.is_(None),
        models.Work.excluded_reason.is_(None),
    )


@router.get("/by-year")
def by_year(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
):
    def rows(source: str):
        q = db.query(models.PublicationsByYear).filter(
            models.PublicationsByYear.source == source
        )
        if year_from:
            q = q.filter(models.PublicationsByYear.year >= year_from)
        if year_to:
            q = q.filter(models.PublicationsByYear.year <= year_to)
        return [{"year": r.year, "count": r.count} for r in q.order_by(models.PublicationsByYear.year)]

    return envelope({"openalex": rows("openalex"), "dimensions": rows("dimensions")}, db)


@router.get("/by-field")
def by_field(db: Session = Depends(get_db)):
    rows = db.query(models.FieldCount).order_by(models.FieldCount.count.desc()).all()
    return envelope([{"field_name": r.field_name, "count": r.count} for r in rows], db)


@router.get("/open-access")
def open_access(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
):
    # With a year range, recompute from canonical works (the precomputed
    # oa_status_counts table carries no year dimension). Without one, serve the
    # fast precomputed path — identical to the full-range result.
    if year_from or year_to:
        q = _canonical(
            db.query(models.Work.oa_status, func.count().label("count"))
        )
        if year_from:
            q = q.filter(models.Work.year >= year_from)
        if year_to:
            q = q.filter(models.Work.year <= year_to)
        rows = q.group_by(models.Work.oa_status).order_by(func.count().desc()).all()
        return envelope(
            [{"oa_status": r.oa_status or "unknown", "count": r.count} for r in rows], db
        )

    rows = db.query(models.OAStatusCount).order_by(models.OAStatusCount.count.desc()).all()
    return envelope([{"oa_status": r.oa_status, "count": r.count} for r in rows], db)


@router.get("/by-type")
def by_type(db: Session = Depends(get_db)):
    rows = db.query(models.TypeCount).order_by(models.TypeCount.count.desc()).all()
    return envelope([{"type": r.type, "count": r.count} for r in rows], db)


@router.get("/list")
def publications_list(
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = Query(25, le=200),
    type: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
):
    q = _canonical(db.query(models.Work))
    if type:
        q = q.filter(models.Work.type == type)
    if year_from:
        q = q.filter(models.Work.year >= year_from)
    if year_to:
        q = q.filter(models.Work.year <= year_to)
    total = q.with_entities(func.count()).scalar()
    rows = (
        q.order_by(models.Work.cited_by_count.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = [
        {
            "id": r.id, "title": r.title, "doi": r.doi, "year": r.year,
            "type": r.type, "oa_status": r.oa_status, "is_oa": r.is_oa,
        }
        for r in rows
    ]
    return envelope({"items": items, "total": total, "page": page, "per_page": per_page}, db)
