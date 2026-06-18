"""Authors tab.

Design constraint (per requirements): the LIST view is non-competitive —
random order, searchable, and only neutral fields (name, ORCID, Google Scholar,
primary field). Competitive metrics (publications, citations, h-index) and the
richer detail live ONLY in the per-author modal endpoints.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import get_db
from backend.app.deps import envelope

router = APIRouter(prefix="/api/authors", tags=["authors"])


def _real_authors(db: Session):
    """Only authors we built full profiles for (excludes co-author stubs)."""
    return db.query(models.Author).filter(models.Author.scholar_source.isnot(None))


@router.get("/top")
def authors_list(
    db: Session = Depends(get_db),
    search: str = "",
    page: int = 1,
    per_page: int = Query(25, le=200),
):
    q = _real_authors(db)
    search = search.strip()
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(func.lower(models.Author.name).like(like))
    total = q.with_entities(func.count()).scalar()
    # Random but stable order via the precomputed shuffle_key (lets paging work).
    rows = (
        q.order_by(models.Author.shuffle_key)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = [
        {
            "id": a.id,
            "name": a.name,
            "orcid": a.orcid,
            "scholar_url": a.scholar_url,
            "primary_field": a.primary_field,
            "department": a.department,
        }
        for a in rows
    ]
    return envelope({"items": items, "total": total, "page": page, "per_page": per_page}, db)


@router.get("/{author_id}")
def author_detail(author_id: str, db: Session = Depends(get_db)):
    """Full modal detail — competitive metrics live here, not in the list."""
    a = db.get(models.Author, author_id)
    if not a:
        return envelope(None, db)
    data = {
        "id": a.id, "name": a.name, "orcid": a.orcid,
        "scholar_url": a.scholar_url, "primary_field": a.primary_field,
        "department": a.department,
        "total_publications": a.total_publications,
        "um_publications": a.um_publications,
        "cited_by_count": a.cited_by_count,
        "h_index": a.h_index, "i10_index": a.i10_index,
    }
    return envelope(data, db)


@router.get("/{author_id}/works")
def author_works(author_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Work)
        .join(models.AuthorWork, models.AuthorWork.work_id == models.Work.id)
        .filter(
            models.AuthorWork.author_id == author_id,
            models.Work.is_duplicate_of.is_(None),
            models.Work.excluded_reason.is_(None),
        )
        .order_by(models.Work.cited_by_count.desc())
        .limit(10)
        .all()
    )
    data = [
        {"title": r.title, "doi": r.doi, "year": r.year, "citations": r.cited_by_count}
        for r in rows
    ]
    return envelope(data, db)


@router.get("/{author_id}/expertise")
def author_expertise(author_id: str, db: Session = Depends(get_db), orcid: str | None = None):
    rows = (
        db.query(models.AuthorExpertise)
        .filter(models.AuthorExpertise.author_id == author_id)
        .order_by(models.AuthorExpertise.total_score.desc())
        .all()
    )
    data = [
        {
            "keyword": r.keyword,
            "total_score": r.total_score,
            "sources": json.loads(r.sources) if r.sources else [],
            "type": r.type,
        }
        for r in rows
    ]
    return envelope(data, db, source="both")


@router.get("/{author_id}/grants")
def author_grants(author_id: str, db: Session = Depends(get_db)):
    """Grants matched to this author by investigator name (Dimensions, best-effort)."""
    rows = (
        db.query(models.AuthorGrant)
        .filter(models.AuthorGrant.author_id == author_id)
        .order_by(models.AuthorGrant.funding_usd.desc())
        .all()
    )
    data = [
        {
            "grant_id": r.grant_id,
            "title": r.title,
            "funder": r.funder,
            "funding_usd": r.funding_usd,
            "start_year": r.start_year,
            "role": r.role,
        }
        for r in rows
    ]
    return envelope(data, db, source="dimensions")


@router.get("/{author_id}/patents")
def author_patents(author_id: str, db: Session = Depends(get_db)):
    """Patents matched to this author by inventor name (Dimensions, best-effort)."""
    rows = (
        db.query(models.Patent)
        .join(models.AuthorPatent, models.AuthorPatent.patent_id == models.Patent.id)
        .filter(models.AuthorPatent.author_id == author_id)
        .order_by(models.Patent.year.desc().nullslast(), models.Patent.times_cited.desc())
        .all()
    )
    data = [
        {
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "times_cited": r.times_cited,
            "inventors": json.loads(r.inventors) if r.inventors else [],
            "filing_status": r.filing_status,
        }
        for r in rows
    ]
    return envelope(data, db, source="dimensions")


@router.get("/{author_id}/citation-sources")
def author_citation_sources(author_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(models.AuthorCitationSource)
        .filter(models.AuthorCitationSource.author_id == author_id)
        .order_by(models.AuthorCitationSource.citation_count.desc())
        .all()
    )
    data = [
        {
            "source_name": r.source_name,
            "publisher": r.publisher,
            "citation_count": r.citation_count,
            "is_oa": r.is_oa,
            "oa_type": r.oa_type,
        }
        for r in rows
    ]
    return envelope(data, db)
