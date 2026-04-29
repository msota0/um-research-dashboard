"""
seed.py — Pre-fetch all OpenAlex (and Dimensions if key present) data into cache.db.

Run once:
    python seed.py

Re-seed expired/general data:
    python seed.py --refresh

Skip expensive citation-source seeding:
    python seed.py --skip-citations

Only run citation-source seeding:
    python seed.py --citations-only

Faster citation-source seeding with controlled parallelism:
    python seed.py --citations-only --max-workers 3

This stores seeded data with a 365-day TTL so Flask can serve from cache
instead of hitting external APIs during normal dashboard use.
"""

import os
import time
import argparse
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")

TTL_PERMANENT = 365 * 24 * 3600   # 1 year
DEFAULT_GRID_ID = "grid.251313.7"

# Be gentle by default. Increase to 3–5 only if your Dimensions account allows it.
DEFAULT_MAX_WORKERS = int(os.getenv("SEED_MAX_WORKERS", "2"))

# ── import project modules ────────────────────────────────────────────────────
from backend.api.cache import CacheManager
from backend.api.openalex import OpenAlexClient
from backend.api.dimensions import DimensionsClient

cache = CacheManager(os.getenv("CACHE_DB_PATH", "cache.db"))
oa = OpenAlexClient(os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"), cache)
dim = DimensionsClient(os.getenv("DIMENSIONS_API_KEY", ""), cache)

# SQLite allows multiple readers but writes can conflict under threads.
# Use a small lock around cache writes/checks in worker-heavy paths.
cache_lock = Lock()


def step(label: str, fn, *args, **kwargs):
    """Run fn, log result, return value (or None on failure)."""
    log.info(f"  Fetching: {label} …")
    try:
        result = fn(*args, **kwargs)
        count = len(result) if isinstance(result, (list, dict)) else "ok"
        log.info(f"  ✓ {label} ({count})")
        return result
    except Exception as e:
        log.warning(f"  ✗ {label} — {e}")
        return None


def _sqlite_exec(sql: str, params: tuple = ()):
    with sqlite3.connect(os.getenv("CACHE_DB_PATH", "cache.db")) as conn:
        conn.execute(sql, params)
        conn.commit()


def override_ttl(iid: str):
    """After seeding, extend all cache entries for this institution to TTL_PERMANENT."""
    with sqlite3.connect(os.getenv("CACHE_DB_PATH", "cache.db")) as conn:
        conn.execute(
            "UPDATE cache SET ttl = ? WHERE key LIKE ?",
            (TTL_PERMANENT, f"%{iid}%"),
        )
        conn.execute(
            "UPDATE cache SET ttl = ? WHERE key LIKE ?",
            (TTL_PERMANENT, "%dimensions%"),
        )
        conn.execute(
            "UPDATE cache SET ttl = ? WHERE key LIKE ?",
            (TTL_PERMANENT, "%expertise%"),
        )
        conn.commit()
    log.info("  All seeded entries extended to 365-day TTL.")


def seed_openalex(iid: str):
    log.info("── OpenAlex ─────────────────────────────────────────")

    keys = [
        f"openalex:institution:{iid}",
        f"openalex:pubs_by_year:{iid}",
        f"openalex:pubs_by_field:{iid}",
        f"openalex:oa_stats:{iid}",
        f"openalex:pubs_by_type:{iid}",
        f"openalex:top_journals:{iid}",
        f"openalex:collab_institutions:{iid}",
        f"openalex:collab_countries:{iid}",
        f"openalex:oa_trend:{iid}",
    ]

    for k in keys:
        cache.invalidate(k)

    _sqlite_exec("DELETE FROM cache WHERE key LIKE '%top_authors%'")
    log.info("  Cleared all top_authors cache entries.")

    step("institution overview",         oa.get_institution_overview)
    step("publications by year",         oa.get_publications_by_year)
    step("publications by field",        oa.get_publications_by_field)
    step("open access stats",            oa.get_open_access_stats)
    step("publications by type",         oa.get_publications_by_type)
    step("top journals",                 oa.get_top_journals)
    step("collaborating institutions",   oa.get_collaborating_institutions)
    step("collaborating countries",      oa.get_collaborating_countries)
    step("OA trend by year",             oa.get_oa_trend_by_year)

    # get_top_authors builds and caches the full author list internally.
    log.info("  Fetching authors page 1 / building full author cache …")
    try:
        oa.get_top_authors(page=1, per_page=25)
        log.info("  ✓ authors cache ready")
    except Exception as e:
        log.warning(f"  ✗ authors page 1 — {e}")

    log.info("  Fetching publication list pages 1-3 …")
    for page in range(1, 4):
        cache_key = f"openalex:pubs_list:{iid}:{page}:25:::"
        cache.invalidate(cache_key)
        try:
            oa.get_publications_list(page=page, per_page=25)
            log.info(f"  ✓ publications list page {page}")
        except Exception as e:
            log.warning(f"  ✗ publications list page {page} — {e}")
        time.sleep(0.25)

    log.info("  OpenAlex seeding complete.\n")


def seed_dimensions():
    api_key = os.getenv("DIMENSIONS_API_KEY", "")
    if not api_key:
        log.info("── Dimensions AI ─── (skipped — no DIMENSIONS_API_KEY in .env)")
        return

    log.info("── Dimensions AI ────────────────────────────────────")

    grid_id = DEFAULT_GRID_ID
    dim_keys = [
        f"dimensions:pubs_by_year:{grid_id}",
        f"dimensions:publications:{grid_id}",
        f"dimensions:grants:{grid_id}",
        f"dimensions:researchers:{grid_id}",
        f"dimensions:clinical_trials:{grid_id}",
        f"dimensions:patents:{grid_id}",
        f"dimensions:collab_orgs:{grid_id}",
        # clear old wrong GRID ID entries if present
        "dimensions:pubs_by_year:grid.266226.6",
        "dimensions:publications:grid.266226.6",
        "dimensions:grants:grid.266226.6",
        "dimensions:researchers:grid.266226.6",
        "dimensions:clinical_trials:grid.266226.6",
        "dimensions:patents:grid.266226.6",
        "dimensions:collab_orgs:grid.266226.6",
    ]

    for k in dim_keys:
        cache.invalidate(k)

    step("publications by year",  dim.get_publications_by_year)
    step("grants",                dim.get_grants)
    step("clinical trials",       dim.get_clinical_trials)
    step("patents",               dim.get_patents)
    step("researchers",           dim.get_researchers)
    step("collaborating orgs",    dim.get_collaborating_orgs)

    log.info("  Dimensions seeding complete.\n")


def _fetch_all_authors(per_page: int = 100, limit: int | None = None) -> list:
    """
    Paginate through ALL UM Oxford authors from OpenAlex.
    Returns a flat list of author dicts.
    """
    all_authors = []
    page = 1
    total = None

    while True:
        try:
            result = oa.get_top_authors(page=page, per_page=per_page)
            items = result.get("items", []) if isinstance(result, dict) else []

            if total is None:
                total = result.get("total", 0) if isinstance(result, dict) else 0
                log.info(f"  Total UM Oxford authors in OpenAlex: {total}")

            if not items:
                break

            all_authors.extend(items)

            if limit:
                all_authors = all_authors[:limit]
                log.info(f"  Fetched page {page} ({len(all_authors)}/{limit} limit)")
                if len(all_authors) >= limit:
                    break
            else:
                log.info(f"  Fetched page {page} ({len(all_authors)}/{total} authors)")
                if len(all_authors) >= total:
                    break

            page += 1
            time.sleep(0.25)

        except Exception as e:
            log.warning(f"  Failed fetching authors page {page}: {e}")
            break

    return all_authors


def _process_one_author(author: dict, force: bool = False) -> tuple[str, str, int, str]:
    """
    Worker function for citation-source seeding.

    Returns:
        (status, author_id, source_count, author_name)

    status values:
        success | skipped_cached | skipped_no_dois | failed
    """
    aid = author.get("id", "")
    name = author.get("name", aid)

    if not aid:
        return ("failed", "", 0, name)

    cache_key = f"dimensions:citation_sources:{aid}"

    if not force:
        with cache_lock:
            existing = cache.get(cache_key)
        if existing is not None:
            return ("skipped_cached", aid, len(existing), name)

    try:
        dois = oa.get_author_dois(aid)
    except Exception as e:
        log.warning(f"    ✗ DOI fetch failed for {name}: {e}")
        return ("failed", aid, 0, name)

    if not dois:
        with cache_lock:
            cache.set(cache_key, [], "dimensions", TTL_PERMANENT)
        return ("skipped_no_dois", aid, 0, name)

    try:
        sources = dim.get_author_citation_sources(aid, dois)
        with cache_lock:
            cache.set(cache_key, sources, "dimensions", TTL_PERMANENT)
        return ("success", aid, len(sources), name)
    except Exception as e:
        log.warning(f"    ✗ Dimensions failed for {name}: {e}")
        return ("failed", aid, 0, name)


def _collect_cached_citation_sources(authors: list, iid: str) -> dict:
    """
    Build one frontend-friendly cache object:
        dimensions:citation_sources_all:{iid}

    This lets /api/citation-sources/all return quickly without scanning many keys.
    """
    all_sources = {}

    for author in authors:
        aid = author.get("id", "")
        if not aid:
            continue

        data = cache.get(f"dimensions:citation_sources:{aid}")
        if data is not None:
            all_sources[aid] = data

    cache.set(
        f"dimensions:citation_sources_all:{iid}",
        all_sources,
        "dimensions",
        TTL_PERMANENT,
    )

    return all_sources


def seed_citation_sources(
    iid: str,
    max_workers: int = DEFAULT_MAX_WORKERS,
    limit_authors: int | None = None,
    force: bool = False,
):
    """
    Pre-warm citation source data for UM Oxford authors.

    Faster than the old version because:
      - authors are processed concurrently with a small worker pool
      - cached authors are skipped immediately
      - no fixed sleep is added after every author
      - one aggregate cache key is written for the frontend

    Keep max_workers low. Dimensions can rate-limit heavily, and DimensionsClient
    still has its own 429 retry/backoff behavior.
    """
    api_key = os.getenv("DIMENSIONS_API_KEY", "")
    if not api_key:
        log.info("── Citation Sources ─── (skipped — no DIMENSIONS_API_KEY)")
        return

    max_workers = max(1, int(max_workers))

    log.info("── Citation Sources ─────────────────────────────────")
    log.info("  Fetching UM Oxford authors from OpenAlex …")

    authors = _fetch_all_authors(per_page=100, limit=limit_authors)

    if not authors:
        log.warning("  No authors returned — skipping citation sources")
        return

    log.info(f"\n  {len(authors)} authors to process.")
    log.info(f"  Max workers: {max_workers}")
    log.info(f"  Force refresh citations: {force}")
    log.info("  Cached authors will be skipped unless --force-citations is used.\n")

    success = 0
    skipped_cached = 0
    skipped_no_dois = 0
    failed = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_one_author, author, force): author
            for author in authors
        }

        for future in as_completed(futures):
            completed += 1

            try:
                status, aid, count, name = future.result()
            except Exception as e:
                failed += 1
                log.warning(f"  [{completed:4d}/{len(authors)}] ✗ worker crashed — {e}")
                continue

            if status == "success":
                success += 1
                log.info(f"  [{completed:4d}/{len(authors)}] ✓ {name} ({count} sources)")
            elif status == "skipped_cached":
                skipped_cached += 1
                log.info(f"  [{completed:4d}/{len(authors)}] ⟳ {name} ({count} cached)")
            elif status == "skipped_no_dois":
                skipped_no_dois += 1
                log.info(f"  [{completed:4d}/{len(authors)}] · {name} (no DOIs)")
            else:
                failed += 1
                log.info(f"  [{completed:4d}/{len(authors)}] ✗ {name}")

            if completed % 25 == 0:
                log.info(
                    f"\n  ── Checkpoint: {completed}/{len(authors)} complete | "
                    f"{success} seeded, {skipped_cached} cached, "
                    f"{skipped_no_dois} no DOI, {failed} failed ──\n"
                )

    log.info("\n  Building aggregate citation-source cache for frontend …")
    all_sources = _collect_cached_citation_sources(authors, iid)

    log.info(f"  ✓ dimensions:citation_sources_all:{iid} ({len(all_sources)} authors)")

    log.info(f"\n  Citation sources complete:")
    log.info(f"    ✓ Seeded:          {success}")
    log.info(f"    ⟳ Already cached:  {skipped_cached}")
    log.info(f"    · No DOI:          {skipped_no_dois}")
    log.info(f"    ✗ Failed:          {failed}")
    log.info(f"    Total processed:   {len(authors)}\n")


def main():
    parser = argparse.ArgumentParser(description="Seed cache.db from OpenAlex + Dimensions AI")
    parser.add_argument("--refresh", action="store_true", help="Clear expired entries before seeding")
    parser.add_argument("--skip-citations", action="store_true", help="Skip citation sources seeding")
    parser.add_argument("--citations-only", action="store_true", help="Only run citation sources seeding")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Parallel workers for citation-source seeding. Start with 2 or 3.",
    )
    parser.add_argument(
        "--limit-authors",
        type=int,
        default=None,
        help="Process only the first N authors. Useful for testing.",
    )
    parser.add_argument(
        "--force-citations",
        action="store_true",
        help="Recompute citation sources even when cached.",
    )
    args = parser.parse_args()

    log.info("═══════════════════════════════════════════════")
    log.info("  UM Research Dashboard — Data Seeder")
    log.info("═══════════════════════════════════════════════\n")

    if args.refresh:
        cache.clear_expired()
        log.info("Cleared expired cache entries.\n")

    log.info("── Institution verification ──────────────────────────")
    iid = oa.verify_institution()
    log.info(f"  Institution ID: {iid}\n")

    if not args.citations_only:
        seed_openalex(iid)
        seed_dimensions()

    if args.citations_only or not args.skip_citations:
        seed_citation_sources(
            iid=iid,
            max_workers=args.max_workers,
            limit_authors=args.limit_authors,
            force=args.force_citations,
        )
    else:
        log.info("── Citation Sources ─── (skipped via --skip-citations flag)")

    override_ttl(iid)

    status = cache.status()
    log.info("═══════════════════════════════════════════════")
    log.info(f"  Done!  {status['total_entries']} entries in cache.db")
    log.info(f"  DB size: {status['size_bytes'] / 1024:.1f} KB")
    log.info("═══════════════════════════════════════════════")
    log.info("")
    log.info("  Start the app:  flask run")
    log.info("  Frontend:       cd frontend && npm run dev")


if __name__ == "__main__":
    main()
