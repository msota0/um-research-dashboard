"""Journals, collaborations, open-access trend, grants summary, departments, patents."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import get_db
from backend.app.deps import envelope

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/journals/top")
def journals_top(
    db: Session = Depends(get_db),
    search: str = "",
    limit: int = Query(200, le=1000),
    year_from: int | None = None,
    year_to: int | None = None,
):
    """Top journals by publication count.

    With `search`, filters case-insensitively across ALL journals (not just the
    default top slice) so lower-ranked journals are still reachable, then returns
    the top `limit` matches by count.

    With a year range, recompute from canonical works joined to their source
    (the precomputed journal_counts table carries no year dimension), keeping the
    same repository/index exclusion that ingest applies.
    """
    search = search.strip()

    if year_from or year_to:
        q = (
            db.query(models.Source.name, func.count(models.Work.id).label("count"))
            .join(models.Work, models.Work.primary_source_id == models.Source.id)
            .filter(
                models.Work.is_duplicate_of.is_(None),
                models.Work.excluded_reason.is_(None),
                models.Source.is_repository_or_index.is_(False),
            )
        )
        if year_from:
            q = q.filter(models.Work.year >= year_from)
        if year_to:
            q = q.filter(models.Work.year <= year_to)
        if search:
            q = q.filter(func.lower(models.Source.name).like(f"%{search.lower()}%"))
        rows = (
            q.group_by(models.Source.name)
            .order_by(func.count(models.Work.id).desc())
            .limit(limit)
            .all()
        )
        return envelope([{"name": r.name, "count": r.count} for r in rows], db)

    q = db.query(models.JournalCount)
    if search:
        q = q.filter(func.lower(models.JournalCount.name).like(f"%{search.lower()}%"))
    rows = q.order_by(models.JournalCount.count.desc()).limit(limit).all()
    return envelope([{"name": r.name, "count": r.count} for r in rows], db)


@router.get("/collaborations/institutions")
def collab_institutions(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CollabInstitution)
        .order_by(models.CollabInstitution.count.desc())
        .limit(20)
        .all()
    )
    return envelope(
        [{"name": r.name, "count": r.count, "country": r.country} for r in rows], db
    )


@router.get("/collaborations/countries")
def collab_countries(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CollabCountry)
        .order_by(models.CollabCountry.count.desc())
        .all()
    )
    return envelope(
        [
            {"country": r.country, "country_code": r.country_code, "count": r.count}
            for r in rows
        ],
        db,
    )


@router.get("/open-access/trend")
def oa_trend(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
):
    q = db.query(models.OAByYear)
    if year_from:
        q = q.filter(models.OAByYear.year >= year_from)
    if year_to:
        q = q.filter(models.OAByYear.year <= year_to)
    rows = q.order_by(models.OAByYear.year).all()
    data = [
        {
            "year": r.year,
            "oa_count": r.oa_count,
            "total": r.total,
            "oa_percentage": round(100.0 * r.oa_count / r.total, 1) if r.total else 0.0,
        }
        for r in rows
    ]
    return envelope(data, db)


@router.get("/grants/summary")
def grants_summary(db: Session = Depends(get_db)):
    s = db.get(models.GrantSummary, 1)
    funders = (
        db.query(models.GrantByFunder)
        .order_by(models.GrantByFunder.total_usd.desc())
        .limit(10)
        .all()
    )
    data = {
        "total_grants": s.total_grants if s else 0,
        "total_funding_usd": s.total_funding_usd if s else 0.0,
        "by_funder": [
            {"name": f.name, "count": f.count, "total_usd": f.total_usd} for f in funders
        ],
    }
    return envelope(data, db, source="dimensions")


@router.get("/patents/summary")
def patents_summary(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
):
    # With a year range, recompute every rollup from the filtered patent rows
    # (the precomputed summary tables carry no year dimension). Patents with no
    # year can't be placed in a range, so they're excluded when filtering.
    if year_from or year_to:
        q = db.query(models.Patent)
        if year_from:
            q = q.filter(models.Patent.year >= year_from)
        if year_to:
            q = q.filter(models.Patent.year <= year_to)
        pats = q.all()

        year_counts: dict[int, int] = {}
        inventor_counts: dict[str, int] = {}
        total_cited = 0
        for p in pats:
            total_cited += p.times_cited or 0
            if p.year is not None:
                year_counts[p.year] = year_counts.get(p.year, 0) + 1
            for name in (json.loads(p.inventors) if p.inventors else []):
                inventor_counts[name] = inventor_counts.get(name, 0) + 1

        top_inventors = sorted(
            inventor_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:20]
        data = {
            "total_patents": len(pats),
            "total_cited": total_cited,
            "unique_inventors": len(inventor_counts),
            "by_year": [{"year": y, "count": c} for y, c in sorted(year_counts.items())],
            "top_inventors": [{"name": n, "count": c} for n, c in top_inventors],
        }
        return envelope(data, db, source="dimensions")

    s = db.get(models.PatentSummary, 1)
    by_year = db.query(models.PatentByYear).order_by(models.PatentByYear.year).all()
    inventors = (
        db.query(models.PatentTopInventor)
        .order_by(models.PatentTopInventor.count.desc())
        .limit(20)
        .all()
    )
    data = {
        "total_patents": s.total_patents if s else 0,
        "total_cited": s.total_cited if s else 0,
        "unique_inventors": s.unique_inventors if s else 0,
        "by_year": [{"year": r.year, "count": r.count} for r in by_year],
        "top_inventors": [{"name": r.name, "count": r.count} for r in inventors],
    }
    return envelope(data, db, source="dimensions")


@router.get("/patents/list")
def patents_list(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
):
    q = db.query(models.Patent)
    if year_from:
        q = q.filter(models.Patent.year >= year_from)
    if year_to:
        q = q.filter(models.Patent.year <= year_to)
    rows = (
        q.order_by(models.Patent.year.desc().nullslast(), models.Patent.times_cited.desc())
        .all()
    )
    data = [
        {
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "times_cited": r.times_cited,
            "inventors": json.loads(r.inventors) if r.inventors else [],
            "assignees": json.loads(r.assignees) if r.assignees else [],
            "filing_status": r.filing_status,
        }
        for r in rows
    ]
    return envelope(data, db, source="dimensions")


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Department)
        .order_by(models.Department.publication_count.desc())
        .all()
    )
    data = [
        {
            "name": r.name_display,
            "publication_count": r.publication_count,
            "citation_count": r.citation_count,
        }
        for r in rows
    ]
    return envelope(data, db, source="dimensions")
