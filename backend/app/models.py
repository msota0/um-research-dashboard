"""ORM models = the canonical, deduplicated, query-optimized data store.

Design notes
------------
* Everything is filtered to ``YEAR_FROM..YEAR_TO`` (2018-2026) at ingest time.
* ``works`` holds one row per *record* we ingested, but dedup marks non-canonical
  rows via ``is_duplicate_of`` and disqualified rows via ``excluded_reason`` so
  headline counts can simply filter ``is_duplicate_of IS NULL AND
  excluded_reason IS NULL``. We keep (not delete) duplicates for auditability.
* Aggregate tables (``fields``, ``oa_by_year`` …) are precomputed by the
  pipeline so the API never aggregates at request time.
* Author *list*-view fields are deliberately separated in the API layer from the
  *modal*-only competitive metrics, but both live on ``authors`` here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


# ─────────────────────────── Works & sources ────────────────────────────────
class Source(Base):
    """A venue/journal/repository (OpenAlex source)."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # OpenAlex source id
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(String)
    # True for repositories/indexes/preprint servers that must be excluded from
    # journal rankings & headline counts (PNNL repo, OSTI, PubMed, SSRN, …).
    is_repository_or_index: Mapped[bool] = mapped_column(Boolean, default=False)

    works: Mapped[list["Work"]] = relationship(back_populates="primary_source")


class Work(Base):
    """One scholarly work. Dedup flags decide whether it counts in headlines."""

    __tablename__ = "works"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # OpenAlex work id
    doi: Mapped[str | None] = mapped_column(String)  # normalized (no url prefix)
    title: Mapped[str | None] = mapped_column(Text)
    title_norm: Mapped[str | None] = mapped_column(Text)  # for fuzzy dedup
    year: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[str | None] = mapped_column(String)
    oa_status: Mapped[str | None] = mapped_column(String)
    is_oa: Mapped[bool | None] = mapped_column(Boolean)
    cited_by_count: Mapped[int] = mapped_column(Integer, default=0)

    primary_source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    primary_source: Mapped[Source | None] = relationship(back_populates="works")

    # Dedup bookkeeping (see module docstring).
    is_duplicate_of: Mapped[str | None] = mapped_column(ForeignKey("works.id"))
    excluded_reason: Mapped[str | None] = mapped_column(String)  # dataset|repository|type|...

    authors: Mapped[list["AuthorWork"]] = relationship(back_populates="work")

    __table_args__ = (
        Index("ix_works_doi", "doi"),
        Index("ix_works_title_norm", "title_norm"),
        Index("ix_works_year", "year"),
        Index("ix_works_type", "type"),
        Index("ix_works_canonical", "is_duplicate_of", "excluded_reason"),
    )


# ─────────────────────────────── Authors ────────────────────────────────────
class Author(Base):
    """An author. List-view exposes only neutral fields; modal exposes metrics."""

    __tablename__ = "authors"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # OpenAlex author id
    name: Mapped[str] = mapped_column(Text, nullable=False)
    orcid: Mapped[str | None] = mapped_column(String)

    # Neutral, non-competitive fields shown in the list view.
    primary_field: Mapped[str | None] = mapped_column(String)
    # Department/school, name-matched from Dimensions raw_affiliation (best-effort).
    department: Mapped[str | None] = mapped_column(Text)
    scholar_url: Mapped[str | None] = mapped_column(Text)
    scholar_source: Mapped[str | None] = mapped_column(String)  # orcid|scholarly|search

    # Competitive metrics — MODAL ONLY (never surfaced in the list endpoint).
    total_publications: Mapped[int] = mapped_column(Integer, default=0)
    um_publications: Mapped[int] = mapped_column(Integer, default=0)
    cited_by_count: Mapped[int] = mapped_column(Integer, default=0)
    h_index: Mapped[int] = mapped_column(Integer, default=0)
    i10_index: Mapped[int] = mapped_column(Integer, default=0)

    # Stable per-author key so the API can shuffle deterministically yet page.
    shuffle_key: Mapped[int] = mapped_column(BigInteger, default=0)

    works: Mapped[list["AuthorWork"]] = relationship(back_populates="author")
    expertise: Mapped[list["AuthorExpertise"]] = relationship(back_populates="author")
    citation_sources: Mapped[list["AuthorCitationSource"]] = relationship(
        back_populates="author"
    )

    __table_args__ = (Index("ix_authors_shuffle", "shuffle_key"),)


class AuthorWork(Base):
    """M:N author <-> work (only UM-affiliated authorships are stored)."""

    __tablename__ = "author_works"

    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), primary_key=True)

    author: Mapped[Author] = relationship(back_populates="works")
    work: Mapped[Work] = relationship(back_populates="authors")


class AuthorExpertise(Base):
    """Expertise keyword for an author (modal). Mirrors old researcher.py output."""

    __tablename__ = "author_expertise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"))
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    sources: Mapped[str | None] = mapped_column(Text)  # JSON-encoded list[str]
    type: Mapped[str | None] = mapped_column(String)  # topic|concept|extracted|self_reported

    author: Mapped[Author] = relationship(back_populates="expertise")

    __table_args__ = (Index("ix_expertise_author", "author_id"),)


class AuthorCitationSource(Base):
    """A source an author cites, with how often + OA status (modal / tab)."""

    __tablename__ = "author_citation_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"))
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str | None] = mapped_column(Text)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    is_oa: Mapped[bool] = mapped_column(Boolean, default=False)
    oa_type: Mapped[str | None] = mapped_column(String)

    author: Mapped[Author] = relationship(back_populates="citation_sources")

    __table_args__ = (Index("ix_citsrc_author", "author_id"),)


class ReferencedWorkVenue(Base):
    """Permanent cache: a referenced work's venue/OA, resolved exactly once.

    This is what makes citation-source ingestion cheap — the union of all
    referenced works is resolved here in 100-id batches and never re-fetched.
    """

    __tablename__ = "referenced_work_venues"

    referenced_work_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String)
    source_name: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    is_oa: Mapped[bool] = mapped_column(Boolean, default=False)
    oa_type: Mapped[str | None] = mapped_column(String)


# ───────────────────────── Precomputed aggregates ───────────────────────────
class FieldCount(Base):
    __tablename__ = "fields"

    field_name: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class PublicationsByYear(Base):
    """Per-year counts, one row per (year, source)."""

    __tablename__ = "publications_by_year"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, primary_key=True)  # openalex|dimensions
    count: Mapped[int] = mapped_column(Integer, default=0)


class OAByYear(Base):
    __tablename__ = "oa_by_year"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    oa_count: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)


class OAStatusCount(Base):
    __tablename__ = "oa_status_counts"

    oa_status: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class TypeCount(Base):
    __tablename__ = "type_counts"

    type: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class JournalCount(Base):
    """Top journals (repository/index sources already excluded at ingest)."""

    __tablename__ = "journal_counts"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)


class CollabInstitution(Base):
    __tablename__ = "collaborations_institutions"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    country: Mapped[str | None] = mapped_column(String)


class CollabCountry(Base):
    __tablename__ = "collaborations_countries"

    country_code: Mapped[str] = mapped_column(String, primary_key=True)
    country: Mapped[str | None] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer, default=0)


# ──────────────────────── Departments (Dimensions) ──────────────────────────
class Department(Base):
    """UM-Oxford department parsed & normalized from Dimensions raw_affiliation."""

    __tablename__ = "departments"

    name_norm: Mapped[str] = mapped_column(String, primary_key=True)
    name_display: Mapped[str] = mapped_column(Text, nullable=False)
    publication_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)


# ───────────────────────────── Grants (Overview) ────────────────────────────
class GrantSummary(Base):
    """Single-row institution grant totals (id=1)."""

    __tablename__ = "grant_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_grants: Mapped[int] = mapped_column(Integer, default=0)
    total_funding_usd: Mapped[float] = mapped_column(Float, default=0.0)
    top_funder: Mapped[str | None] = mapped_column(Text)


class GrantByFunder(Base):
    __tablename__ = "grants_by_funder"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    total_usd: Mapped[float] = mapped_column(Float, default=0.0)


# ────────────────────────────── Patents (Dimensions) ────────────────────────
class PatentSummary(Base):
    """Single-row institution patent totals (id=1)."""

    __tablename__ = "patent_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_patents: Mapped[int] = mapped_column(Integer, default=0)
    total_cited: Mapped[int] = mapped_column(Integer, default=0)
    unique_inventors: Mapped[int] = mapped_column(Integer, default=0)


class PatentByYear(Base):
    __tablename__ = "patents_by_year"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class PatentTopInventor(Base):
    __tablename__ = "patent_top_inventors"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Patent(Base):
    """One patent (UM as assignee). inventors/assignees are JSON-encoded lists."""

    __tablename__ = "patents"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Dimensions patent id
    title: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    times_cited: Mapped[int] = mapped_column(Integer, default=0)
    inventors: Mapped[str | None] = mapped_column(Text)   # JSON-encoded list[str]
    assignees: Mapped[str | None] = mapped_column(Text)   # JSON-encoded list[str]
    filing_status: Mapped[str | None] = mapped_column(String)

    __table_args__ = (Index("ix_patents_year", "year"),)


class AuthorGrant(Base):
    """A Dimensions grant matched to an author by investigator name (best-effort)."""

    __tablename__ = "author_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"))
    grant_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(Text)
    funder: Mapped[str | None] = mapped_column(Text)
    funding_usd: Mapped[float] = mapped_column(Float, default=0.0)
    start_year: Mapped[int | None] = mapped_column(Integer)
    role: Mapped[str | None] = mapped_column(String)

    __table_args__ = (Index("ix_author_grants_author", "author_id"),)


class AuthorPatent(Base):
    """A patent matched to an author by inventor name (best-effort)."""

    __tablename__ = "author_patents"

    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    patent_id: Mapped[str] = mapped_column(ForeignKey("patents.id"), primary_key=True)


# ─────────────────────── Institution overview / meta ────────────────────────
class InstitutionOverview(Base):
    """Single-row institution headline metrics (id=1)."""

    __tablename__ = "institution_overview"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    display_name: Mapped[str | None] = mapped_column(Text)
    works_count: Mapped[int] = mapped_column(Integer, default=0)
    cited_by_count: Mapped[int] = mapped_column(BigInteger, default=0)
    h_index: Mapped[int] = mapped_column(Integer, default=0)
    i10_index: Mapped[int] = mapped_column(Integer, default=0)
    open_access_pct: Mapped[float] = mapped_column(Float, default=0.0)


class IngestCheckpoint(Base):
    """Resume state for the ingestion pipeline. One row per stage."""

    __tablename__ = "ingest_checkpoint"

    stage: Mapped[str] = mapped_column(String, primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text)
    last_completed_key: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[str | None] = mapped_column(Text)  # JSON-encoded stage state
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DatasetMeta(Base):
    """When each source's data was last refreshed (powers the UI timestamps)."""

    __tablename__ = "dataset_meta"

    source: Mapped[str] = mapped_column(String, primary_key=True)  # openalex|dimensions
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
