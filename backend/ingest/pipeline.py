"""Ingestion orchestrator.

Stages (run in order by ``run()``):
  1. overview    — institution headline metrics
  2. works       — bulk OpenAlex pull → works/sources/author_work rows (in-memory
                   records drive later stages)
  3. dedup       — flag duplicates (DOI + fuzzy) & exclusions (type/repository)
  4. aggregates  — precompute fields / OA / types / journals / by-year / collab
  5. authors     — batch author entities → modal metrics + expertise + Scholar
  6. citations   — resolve referenced-work venues (permanent cache) → per-author
  7. dimensions  — departments (raw_affiliation) + grant totals; also backfills
                   ORCID iDs from Dimensions publication authors
  8. patents     — patents + per-author inventor links (Dimensions)
  9. orcid_backfill — last-resort ORCID recovery via ORCID's public search API

Resumability: every write is an idempotent upsert keyed by a stable id, and the
expensive citation stage only fetches venues not already in the permanent
``referenced_work_venues`` cache — so a killed run re-runs cheaply and never
double-counts. The (fast) works pull always re-runs to rebuild in-memory state.

Sampling: ``limit_authors > 0`` caps the run for local dev (works pull and the
author/citation stages are bounded) so it finishes in minutes. ``0`` = full
backfill, intended for the always-on server.
"""
from __future__ import annotations

import json
import logging
import zlib
from collections import defaultdict
from dataclasses import dataclass, field

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import Settings
from backend.ingest import dedup, departments as dept_mod, expertise, name_match, orcid as orcid_mod, scholar
from backend.ingest.dimensions_client import DimensionsClient, iter_raw_affiliations
from backend.ingest.openalex_client import OpenAlexClient, _bare_id

log = logging.getLogger("ingest")


@dataclass
class WorkRecord:
    """Lightweight in-memory view of a work, drives dedup + aggregates."""

    id: str
    doi: str | None
    title: str | None
    title_norm: str | None
    year: int | None
    type: str | None
    oa_status: str | None
    is_oa: bool | None
    cited_by: int
    source_id: str | None
    source_name: str | None
    field_name: str | None
    author_ids: list[str] = field(default_factory=list)
    institutions: list[tuple[str, str | None]] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    referenced_works: list[str] = field(default_factory=list)
    # dedup outcome
    excluded_reason: str | None = None
    is_duplicate_of: str | None = None

    @property
    def counts(self) -> bool:
        return self.excluded_reason is None and self.is_duplicate_of is None


def _upsert(session: Session, model, rows: list[dict], update_cols: list[str]) -> None:
    """Idempotent bulk upsert on the model's primary key."""
    if not rows:
        return
    pk = [c.name for c in model.__table__.primary_key.columns]
    stmt = pg_insert(model).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=pk,
        set_={c: getattr(stmt.excluded, c) for c in update_cols},
    )
    session.execute(stmt)


class Pipeline:
    def __init__(self, session: Session, settings: Settings):
        self.s = session
        self.cfg = settings
        self.oa = OpenAlexClient(settings.openalex_email)
        self.dim = DimensionsClient(settings.dimensions_api_key)
        self.http = httpx.Client()
        self.inst_id = settings.inst_openalex_id
        self.works: list[WorkRecord] = []

    def close(self) -> None:
        self.oa.close()
        self.dim.close()
        self.http.close()

    # ── checkpoint bookkeeping ───────────────────────────────────────────
    def _checkpoint(self, stage: str, payload: dict | None = None) -> None:
        _upsert(
            self.s,
            models.IngestCheckpoint,
            [{"stage": stage, "done": True, "payload": json.dumps(payload or {})}],
            ["done", "payload"],
        )
        self.s.commit()

    # ── orchestration ────────────────────────────────────────────────────
    def run(self, limit_authors: int = 0) -> None:
        works_cap = limit_authors * 40 if limit_authors else None
        ref_cap = 6000 if limit_authors else None

        self.stage_overview()
        self.stage_works(works_cap)
        self.stage_dedup()
        self.stage_aggregates()
        self.stage_authors(limit_authors)
        self.stage_citations(ref_cap)
        self.stage_dimensions()
        self.stage_patents()
        self.stage_orcid_backfill()
        self._stamp_meta()
        log.info("Ingestion complete.")

    # ── 1. overview ──────────────────────────────────────────────────────
    def stage_overview(self) -> None:
        inst = self.oa.get_institution(self.inst_id)  # verifies Oxford
        stats = inst.get("summary_stats") or {}
        _upsert(
            self.s,
            models.InstitutionOverview,
            [{
                "id": 1,
                "display_name": inst.get("display_name"),
                "works_count": inst.get("works_count", 0),
                "cited_by_count": inst.get("cited_by_count", 0),
                "h_index": stats.get("h_index", 0),
                "i10_index": stats.get("i10_index", 0),
            }],
            ["display_name", "works_count", "cited_by_count", "h_index", "i10_index"],
        )
        self._checkpoint("overview")
        log.info("Overview: %s (%s works all-time)", inst.get("display_name"),
                 inst.get("works_count"))

    # ── 2. works ─────────────────────────────────────────────────────────
    def stage_works(self, cap: int | None) -> None:
        select = (
            "id,doi,title,publication_year,type,cited_by_count,open_access,"
            "primary_location,primary_topic,authorships,referenced_works"
        )
        self.works = []
        source_rows: dict[str, dict] = {}
        n = 0
        for w in self.oa.iter_works(
            self.inst_id, self.cfg.year_from, self.cfg.year_to, select=select
        ):
            rec = self._to_record(w)
            self.works.append(rec)
            if rec.source_id:
                source_rows[rec.source_id] = {
                    "id": rec.source_id,
                    "name": rec.source_name or rec.source_id,
                    "type": None,
                    "is_repository_or_index": dedup.is_repository_source(rec.source_name),
                }
            n += 1
            if cap and n >= cap:
                log.info("Works: hit sample cap of %s", cap)
                break
            if n % 2000 == 0:
                log.info("Works: pulled %s", n)

        _upsert(self.s, models.Source, list(source_rows.values()),
                ["name", "type", "is_repository_or_index"])
        self._persist_works()
        self.s.commit()
        self._checkpoint("works", {"count": len(self.works)})
        log.info("Works: %s records pulled & stored", len(self.works))

    def _to_record(self, w: dict) -> WorkRecord:
        oa = w.get("open_access") or {}
        ploc = w.get("primary_location") or {}
        src = ploc.get("source") or {}
        ptopic = w.get("primary_topic") or {}
        fld = (ptopic.get("field") or {}).get("display_name") if ptopic else None
        author_ids, insts, countries = [], [], []
        for a in w.get("authorships", []) or []:
            au = a.get("author") or {}
            for inst in a.get("institutions", []) or []:
                iid = _bare_id(inst.get("id", "")) if inst.get("id") else None
                if iid == self.inst_id and au.get("id"):
                    author_ids.append(_bare_id(au["id"]))
                if inst.get("display_name"):
                    insts.append((inst["display_name"], inst.get("country_code")))
            for cc in a.get("countries", []) or []:
                countries.append(cc)
        title = w.get("title")
        return WorkRecord(
            id=_bare_id(w["id"]),
            doi=dedup.normalize_doi(w.get("doi")),
            title=title,
            title_norm=dedup.normalize_title(title),
            year=w.get("publication_year"),
            type=w.get("type"),
            oa_status=oa.get("oa_status"),
            is_oa=oa.get("is_oa"),
            cited_by=w.get("cited_by_count", 0),
            source_id=_bare_id(src["id"]) if src.get("id") else None,
            source_name=src.get("display_name"),
            field_name=fld,
            author_ids=list(dict.fromkeys(author_ids)),
            institutions=insts,
            countries=countries,
            referenced_works=[_bare_id(r) for r in (w.get("referenced_works") or [])],
        )

    def _persist_works(self) -> None:
        work_rows, link_rows = [], []
        seen_links = set()
        for r in self.works:
            work_rows.append({
                "id": r.id, "doi": r.doi, "title": r.title,
                "title_norm": r.title_norm, "year": r.year, "type": r.type,
                "oa_status": r.oa_status, "is_oa": r.is_oa,
                "cited_by_count": r.cited_by, "primary_source_id": r.source_id,
                "is_duplicate_of": r.is_duplicate_of,
                "excluded_reason": r.excluded_reason,
            })
            for aid in r.author_ids:
                if (aid, r.id) not in seen_links:
                    seen_links.add((aid, r.id))
                    link_rows.append({"author_id": aid, "work_id": r.id})
        # chunk to keep statements reasonable
        for i in range(0, len(work_rows), 1000):
            _upsert(self.s, models.Work, work_rows[i:i + 1000],
                    ["doi", "title", "title_norm", "year", "type", "oa_status",
                     "is_oa", "cited_by_count", "primary_source_id",
                     "is_duplicate_of", "excluded_reason"])
        # author rows must exist before author_works (FK); insert stubs now.
        author_stub = [{"id": aid, "name": aid} for aid in
                       {a for r in self.works for a in r.author_ids}]
        for i in range(0, len(author_stub), 1000):
            _upsert(self.s, models.Author, author_stub[i:i + 1000], ["id"])
        self.s.flush()
        for i in range(0, len(link_rows), 1000):
            stmt = pg_insert(models.AuthorWork).values(link_rows[i:i + 1000])
            self.s.execute(stmt.on_conflict_do_nothing())

    # ── 3. dedup ─────────────────────────────────────────────────────────
    def stage_dedup(self) -> None:
        # (a) exclusions: type / repository
        for r in self.works:
            r.excluded_reason = dedup.classify_excluded(r.type, r.source_name)

        # (b) DOI groups → keep the highest-ranked canonical, flag the rest
        by_doi: dict[str, list[WorkRecord]] = defaultdict(list)
        for r in self.works:
            if r.doi:
                by_doi[r.doi].append(r)
        for group in by_doi.values():
            if len(group) < 2:
                continue
            winner = max(group, key=lambda x: (x.counts, dedup.canonical_rank(x.type, x.source_name), x.cited_by))
            for r in group:
                if r is not winner:
                    r.is_duplicate_of = winner.id

        # (c) fuzzy title+year for DOI-less, non-excluded records
        no_doi = [r for r in self.works if not r.doi and r.counts and r.title_norm]
        buckets: dict[int | None, list[WorkRecord]] = defaultdict(list)
        for r in no_doi:
            buckets[r.year].append(r)
        for recs in buckets.values():
            kept: list[WorkRecord] = []
            for r in recs:
                dup_of = next(
                    (k for k in kept if dedup.fuzzy_duplicate(r.title_norm, k.title_norm)),
                    None,
                )
                if dup_of:
                    r.is_duplicate_of = dup_of.id
                else:
                    kept.append(r)

        self._persist_works()  # rewrite dedup flags
        self.s.commit()
        dups = sum(1 for r in self.works if r.is_duplicate_of)
        excl = sum(1 for r in self.works if r.excluded_reason)
        self._checkpoint("dedup", {"duplicates": dups, "excluded": excl})
        log.info("Dedup: %s canonical, %s duplicates, %s excluded",
                 sum(1 for r in self.works if r.counts), dups, excl)

    # ── 4. aggregates ────────────────────────────────────────────────────
    def stage_aggregates(self) -> None:
        canon = [r for r in self.works if r.counts]

        fields = defaultdict(int)
        oa_status = defaultdict(int)
        types = defaultdict(int)
        journals: dict[str, dict] = {}
        by_year = defaultdict(int)
        oa_year_oa = defaultdict(int)
        oa_year_total = defaultdict(int)
        insts = defaultdict(lambda: {"count": 0, "country": None})
        countries = defaultdict(int)

        for r in canon:
            if r.field_name:
                fields[r.field_name] += 1
            if r.oa_status:
                oa_status[r.oa_status] += 1
            if r.type:
                types[r.type] += 1
            if r.year:
                by_year[r.year] += 1
                oa_year_total[r.year] += 1
                if r.is_oa:
                    oa_year_oa[r.year] += 1
            # journals: skip repository/index sources
            if r.source_id and r.source_name and not dedup.is_repository_source(r.source_name):
                j = journals.setdefault(r.source_id, {"name": r.source_name, "count": 0})
                j["count"] += 1
            for name, cc in r.institutions:
                if name.strip().lower() == "university of mississippi":
                    continue  # exclude the home institution from collaborations
                insts[name]["count"] += 1
                insts[name]["country"] = cc
            for cc in set(r.countries):
                countries[cc] += 1

        self._replace(models.FieldCount, [{"field_name": k, "count": v} for k, v in fields.items()])
        self._replace(models.OAStatusCount, [{"oa_status": k, "count": v} for k, v in oa_status.items()])
        self._replace(models.TypeCount, [{"type": k, "count": v} for k, v in types.items()])
        self._replace(models.JournalCount, [{"source_id": sid, "name": v["name"], "count": v["count"]} for sid, v in journals.items()])
        self._replace(models.PublicationsByYear, [{"year": y, "source": "openalex", "count": c} for y, c in by_year.items()])
        self._replace(models.OAByYear, [{"year": y, "oa_count": oa_year_oa[y], "total": oa_year_total[y]} for y in oa_year_total])
        self._replace(models.CollabInstitution, [{"name": n, "count": v["count"], "country": v["country"]} for n, v in insts.items()])
        self._replace(models.CollabCountry, [{"country_code": cc, "country": cc, "count": c} for cc, c in countries.items()])

        # institution-level OA %
        total = len(canon)
        oa_total = sum(1 for r in canon if r.is_oa)
        self.s.query(models.InstitutionOverview).filter_by(id=1).update(
            {"open_access_pct": round(100.0 * oa_total / total, 1) if total else 0.0}
        )
        self.s.commit()
        self._checkpoint("aggregates", {"canonical_works": total})
        log.info("Aggregates: %s canonical works, %s fields, %s journals",
                 total, len(fields), len(journals))

    def _replace(self, model, rows: list[dict]) -> None:
        """Full replace of a small precomputed aggregate table."""
        self.s.query(model).delete()
        if rows:
            self.s.execute(pg_insert(model).values(rows))

    # ── 5. authors ───────────────────────────────────────────────────────
    def stage_authors(self, limit: int) -> None:
        # rank UM authors by UM-publication count to pick the sample, but the
        # API will serve them in random order (metrics stay modal-only).
        um_counts = defaultdict(int)
        for r in self.works:
            if r.counts:
                for aid in r.author_ids:
                    um_counts[aid] += 1
        author_ids = sorted(um_counts, key=lambda a: um_counts[a], reverse=True)
        if limit:
            author_ids = author_ids[:limit]

        entities = list(self.oa.fetch_by_ids(
            "authors", author_ids,
            select="id,display_name,orcid,works_count,cited_by_count,"
                   "summary_stats,topics,x_concepts",
        ))
        author_rows, expertise_rows = [], []
        for e in entities:
            aid = _bare_id(e["id"])
            stats = e.get("summary_stats") or {}
            name = e.get("display_name") or aid
            orcid = e.get("orcid")
            primary = (e.get("topics") or [{}])[0].get("field", {}).get("display_name") \
                if e.get("topics") else None
            url, src = scholar.resolve(name, orcid, self.http, self.cfg.enable_scholarly)
            author_rows.append({
                "id": aid, "name": name, "orcid": orcid,
                "primary_field": primary, "scholar_url": url, "scholar_source": src,
                "total_publications": e.get("works_count", 0),
                "um_publications": um_counts.get(aid, 0),
                "cited_by_count": e.get("cited_by_count", 0),
                "h_index": stats.get("h_index", 0),
                "i10_index": stats.get("i10_index", 0),
                "shuffle_key": zlib.crc32(aid.encode()),
            })
            for row in expertise.aggregate(e):
                expertise_rows.append({"author_id": aid, **row, "sources": json.dumps(row["sources"])})

        _upsert(self.s, models.Author, author_rows,
                ["name", "orcid", "primary_field", "scholar_url", "scholar_source",
                 "total_publications", "um_publications", "cited_by_count",
                 "h_index", "i10_index", "shuffle_key"])
        self.s.query(models.AuthorExpertise).filter(
            models.AuthorExpertise.author_id.in_([r["id"] for r in author_rows])
        ).delete(synchronize_session=False)
        if expertise_rows:
            for i in range(0, len(expertise_rows), 1000):
                self.s.execute(pg_insert(models.AuthorExpertise).values(expertise_rows[i:i + 1000]))
        self.s.commit()
        self._sampled_authors = set(um_counts) if not limit else set(author_ids)
        self._checkpoint("authors", {"count": len(author_rows)})
        log.info("Authors: %s profiles + expertise stored", len(author_rows))

    # ── 6. citation sources ──────────────────────────────────────────────
    def stage_citations(self, ref_cap: int | None) -> None:
        sampled = getattr(self, "_sampled_authors", None)
        # per-author referenced works (only for stored authors)
        author_refs: dict[str, list[str]] = defaultdict(list)
        all_refs: set[str] = set()
        for r in self.works:
            if not r.counts:
                continue
            for aid in r.author_ids:
                if sampled is not None and aid not in sampled:
                    continue
                author_refs[aid].extend(r.referenced_works)
                all_refs.update(r.referenced_works)

        # resolve only venues not already cached
        cached = {row.referenced_work_id for row in self.s.query(
            models.ReferencedWorkVenue.referenced_work_id).all()}
        to_resolve = [r for r in all_refs if r not in cached]
        if ref_cap:
            to_resolve = to_resolve[:ref_cap]
        log.info("Citations: %s unique refs, %s already cached, resolving %s",
                 len(all_refs), len(cached), len(to_resolve))

        venue_rows = []
        for w in self.oa.fetch_by_ids(
            "works", to_resolve,
            select="id,primary_location,open_access",
        ):
            ploc = w.get("primary_location") or {}
            src = ploc.get("source") or {}
            oa = w.get("open_access") or {}
            venue_rows.append({
                "referenced_work_id": _bare_id(w["id"]),
                "source_id": _bare_id(src["id"]) if src.get("id") else None,
                "source_name": src.get("display_name"),
                "publisher": src.get("host_organization_name"),
                "is_oa": oa.get("is_oa", False),
                "oa_type": oa.get("oa_status"),
            })
        for i in range(0, len(venue_rows), 1000):
            _upsert(self.s, models.ReferencedWorkVenue, venue_rows[i:i + 1000],
                    ["source_id", "source_name", "publisher", "is_oa", "oa_type"])
        self.s.commit()

        # aggregate per author from the (now-populated) venue cache
        venue = {row.referenced_work_id: row for row in self.s.query(models.ReferencedWorkVenue).all()}
        self.s.query(models.AuthorCitationSource).delete()
        cs_rows = []
        for aid, refs in author_refs.items():
            agg: dict[str, dict] = {}
            for ref in refs:
                v = venue.get(ref)
                if not v or not v.source_name:
                    continue
                a = agg.setdefault(v.source_name, {
                    "publisher": v.publisher, "citation_count": 0,
                    "is_oa": v.is_oa, "oa_type": v.oa_type})
                a["citation_count"] += 1
            for name, a in agg.items():
                cs_rows.append({"author_id": aid, "source_name": name, **a})
        for i in range(0, len(cs_rows), 1000):
            self.s.execute(pg_insert(models.AuthorCitationSource).values(cs_rows[i:i + 1000]))
        self.s.commit()
        self._checkpoint("citations", {"sources": len(cs_rows)})
        log.info("Citations: %s author-source rows", len(cs_rows))

    # ── author lookup index (for matching Dimensions records to our authors) ──
    @staticmethod
    def _norm_orcid(raw) -> str | None:
        if isinstance(raw, list):  # Dimensions sometimes returns a list of orcids
            raw = raw[0] if raw else None
        if not raw or not isinstance(raw, str):
            return None
        return raw.rstrip("/").split("/")[-1].lower() or None

    def _author_index(self):
        """Build (by_orcid, by_namekey) lookups for our profiled authors.

        Name keys that map to more than one author are dropped — ambiguous matches
        are skipped rather than risk attributing data to the wrong person.
        """
        authors = (
            self.s.query(models.Author)
            .filter(models.Author.scholar_source.isnot(None))
            .all()
        )
        by_orcid: dict[str, str] = {}
        namekey_to_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
        for a in authors:
            oc = self._norm_orcid(a.orcid)
            if oc:
                by_orcid[oc] = a.id
            k = name_match.author_key(a.name)
            if k:
                namekey_to_ids[k].add(a.id)
        by_namekey = {k: next(iter(ids)) for k, ids in namekey_to_ids.items() if len(ids) == 1}
        return by_orcid, by_namekey

    # ── 7. dimensions (departments + grants) ─────────────────────────────
    def stage_dimensions(self) -> None:
        if not self.dim.enabled:
            log.warning("Dimensions: no valid API key — skipping departments & grants. "
                        "Set DIMENSIONS_API_KEY (rotate the leaked one first).")
            self._checkpoint("dimensions", {"skipped": "no_api_key"})
            return

        by_orcid, by_namekey = self._author_index()
        # Backfill ORCID iDs for authors OpenAlex didn't supply, from the matched
        # Dimensions publication-author records (which carry their own orcid).
        have_orcid = set(by_orcid.values())
        orcid_found: dict[str, str] = {}

        # departments from raw_affiliation (+ per-author department attribution)
        dept_pubs = defaultdict(int)
        dept_cites = defaultdict(int)
        # key -> {display variant -> count}, so we can show the most common form.
        dept_display_votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # author_id -> {dept_display -> count}, to pick each author's main department
        author_dept_votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for pub in self.dim.iter_publications(self.cfg.dim_grid, self.cfg.year_from, self.cfg.year_to):
            cites = pub.get("times_cited", 0) or 0
            seen = set()
            for raw in iter_raw_affiliations(pub):
                disp = dept_mod.extract_department(raw)
                if not disp:
                    continue
                key = dept_mod.normalize_department(disp)
                dept_display_votes[key][disp] += 1
                if key not in seen:
                    seen.add(key)
                    dept_pubs[key] += 1
                    dept_cites[key] += cites
            # attribute a department to each matched author (ORCID first, then name)
            for au in pub.get("authors") or []:
                aid = by_orcid.get(self._norm_orcid(au.get("orcid")))
                if not aid:
                    aid = by_namekey.get(name_match.investigator_key(
                        au.get("first_name"), au.get("last_name")))
                if not aid:
                    continue
                if aid not in have_orcid and aid not in orcid_found:
                    url = orcid_mod.url_from_id(au.get("orcid"))
                    if url:
                        orcid_found[aid] = url
                raws = [a.get("raw_affiliation") for a in (au.get("affiliations") or [])]
                raws.append(au.get("raw_affiliation"))
                for raw in raws:
                    if isinstance(raw, list):
                        candidates = raw
                    elif isinstance(raw, str):
                        candidates = [raw]
                    else:
                        continue
                    for r in candidates:
                        disp = dept_mod.extract_department(r) if r else None
                        if disp:
                            author_dept_votes[aid][disp] += 1

        # Canonical display = the most frequently seen variant for each key.
        dept_display = {
            k: max(variants, key=variants.get) for k, variants in dept_display_votes.items()
        }
        self._replace(models.Department, [
            {"name_norm": k, "name_display": dept_display[k],
             "publication_count": dept_pubs[k], "citation_count": dept_cites[k]}
            for k in dept_pubs
        ])
        # write each author's most-frequent department
        for aid, votes in author_dept_votes.items():
            best = max(votes, key=votes.get)
            self.s.query(models.Author).filter(models.Author.id == aid).update(
                {"department": best})
        # write ORCID iDs recovered from Dimensions publication authors
        for aid, url in orcid_found.items():
            self.s.query(models.Author).filter(models.Author.id == aid).update(
                {"orcid": url})
        if orcid_found:
            log.info("Dimensions: backfilled %s ORCIDs from publication authors",
                     len(orcid_found))

        # grants (funder totals + per-author grant links)
        by_funder = defaultdict(lambda: {"count": 0, "total_usd": 0.0})
        author_grants: list[dict] = []
        total_usd = 0.0
        total = 0
        for g in self.dim.iter_grants(self.cfg.dim_grid, self.cfg.year_from, self.cfg.year_to):
            total += 1
            usd = g.get("funding_usd") or 0
            total_usd += usd
            f = g.get("funder_org_name") or "Unknown"
            by_funder[f]["count"] += 1
            by_funder[f]["total_usd"] += usd
            seen_authors: set[str] = set()
            for inv in g.get("investigators") or []:
                aid = by_namekey.get(name_match.investigator_key(
                    inv.get("first_name"), inv.get("last_name")))
                if not aid or aid in seen_authors:
                    continue
                seen_authors.add(aid)
                author_grants.append({
                    "author_id": aid, "grant_id": g.get("id"), "title": g.get("title"),
                    "funder": f, "funding_usd": usd, "start_year": g.get("start_year"),
                    "role": inv.get("role"),
                })
        top_funder = max(by_funder, key=lambda f: by_funder[f]["total_usd"], default=None)
        self._replace(models.GrantByFunder, [
            {"name": f, "count": v["count"], "total_usd": v["total_usd"]}
            for f, v in by_funder.items()])
        self._replace(models.AuthorGrant, author_grants)
        _upsert(self.s, models.GrantSummary, [{
            "id": 1, "total_grants": total, "total_funding_usd": total_usd,
            "top_funder": top_funder}],
            ["total_grants", "total_funding_usd", "top_funder"])
        self.s.commit()
        self._checkpoint("dimensions", {"departments": len(dept_pubs), "grants": total})
        log.info("Dimensions: %s departments, %s grants ($%.0f), %s author-depts, %s author-grants",
                 len(dept_pubs), total, total_usd, len(author_dept_votes), len(author_grants))

    # ── 8. patents (Dimensions) ──────────────────────────────────────────
    def stage_patents(self) -> None:
        if not self.dim.enabled:
            log.warning("Patents: no valid Dimensions API key — skipping.")
            self._checkpoint("patents", {"skipped": "no_api_key"})
            return

        _, by_namekey = self._author_index()

        patents: list[dict] = []
        author_patents: list[dict] = []
        by_year: dict[int, int] = defaultdict(int)
        inventor_counts: dict[str, int] = defaultdict(int)
        total_cited = 0

        for p in self.dim.iter_patents(self.cfg.dim_grid, self.cfg.year_from, self.cfg.year_to):
            cited = p.get("times_cited", 0) or 0
            total_cited += cited
            year = p.get("year")
            if year is not None:
                by_year[year] += 1
            inventors = [i for i in (p.get("inventor_names") or []) if i]
            for inv in inventors:
                inventor_counts[inv] += 1
            # match inventors to our authors (best-effort, by name)
            matched: set[str] = set()
            for key, aid in by_namekey.items():
                if aid in matched:
                    continue
                if any(name_match.inventor_matches(inv, key) for inv in inventors):
                    matched.add(aid)
                    author_patents.append({"author_id": aid, "patent_id": p["id"]})
            patents.append({
                "id": p["id"],
                "title": p.get("title"),
                "year": year,
                "times_cited": cited,
                "inventors": json.dumps(inventors),
                "assignees": json.dumps([a for a in (p.get("assignee_names") or []) if a]),
                "filing_status": p.get("filing_status"),
            })

        top_inventors = sorted(inventor_counts.items(), key=lambda kv: kv[1], reverse=True)[:20]

        self._replace(models.Patent, patents)
        self._replace(models.AuthorPatent, author_patents)
        self._replace(models.PatentByYear,
                      [{"year": y, "count": c} for y, c in sorted(by_year.items())])
        self._replace(models.PatentTopInventor,
                      [{"name": n, "count": c} for n, c in top_inventors])
        _upsert(self.s, models.PatentSummary, [{
            "id": 1,
            "total_patents": len(patents),
            "total_cited": total_cited,
            "unique_inventors": len(inventor_counts),
        }], ["total_patents", "total_cited", "unique_inventors"])
        self.s.commit()
        self._checkpoint("patents", {"patents": len(patents)})
        log.info("Patents: %s patents, %s inventors, %s citations, %s author-patent links",
                 len(patents), len(inventor_counts), total_cited, len(author_patents))

    # ── 9. ORCID backfill (last-resort) ──────────────────────────────────
    def stage_orcid_backfill(self) -> None:
        """Recover ORCID iDs that OpenAlex and Dimensions both missed, by
        searching ORCID's public API by name + UM affiliation. Runs regardless
        of the Dimensions key (it's an independent, official source)."""
        if not self.cfg.enable_orcid_search:
            log.info("ORCID backfill: disabled (ENABLE_ORCID_SEARCH=false)")
            self._checkpoint("orcid_backfill", {"skipped": "disabled"})
            return

        authors = (
            self.s.query(models.Author)
            .filter(models.Author.scholar_source.isnot(None),
                    models.Author.orcid.is_(None))
            .all()
        )
        found = upgraded = 0
        for a in authors:
            url = orcid_mod.search(a.name, self.http)
            if not url:
                continue
            updates = {"orcid": url}
            # Tier-1 Scholar resolution depends on ORCID; with a freshly found
            # iD we can upgrade authors stuck on a bare search link.
            if a.scholar_source == "search":
                s_url = scholar.from_orcid(url, self.http)
                if s_url:
                    updates.update(scholar_url=s_url, scholar_source="orcid")
                    upgraded += 1
            self.s.query(models.Author).filter(models.Author.id == a.id).update(updates)
            found += 1
        self.s.commit()
        self._checkpoint("orcid_backfill", {"found": found, "scholar_upgraded": upgraded})
        log.info("ORCID backfill: %s iDs recovered via ORCID search "
                 "(%s Scholar links upgraded)", found, upgraded)

    def _stamp_meta(self) -> None:
        _upsert(self.s, models.DatasetMeta, [{"source": "openalex"}], ["source"])
        if self.dim.enabled:
            _upsert(self.s, models.DatasetMeta, [{"source": "dimensions"}], ["source"])
        self.s.commit()
