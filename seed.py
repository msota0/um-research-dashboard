"""
seed.py — Pre-fetch all OpenAlex (and Dimensions if key present) data into cache.db.

Run once:
    python seed.py

Re-seed (clears old data first):
    python seed.py --refresh

This stores everything with a 365-day TTL so Flask never needs to hit
the external APIs during normal operation.
"""

import os
import sys
import time
import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")

TTL_PERMANENT = 365 * 24 * 3600   # 1 year

# ── import project modules ────────────────────────────────────────────────────
from api.cache import CacheManager
from api.openalex import OpenAlexClient, FALLBACK_ID
from api.dimensions import DimensionsClient

cache  = CacheManager(os.getenv("CACHE_DB_PATH", "cache.db"))
oa     = OpenAlexClient(os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"), cache)
dim    = DimensionsClient(os.getenv("DIMENSIONS_API_KEY", ""), cache)


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


def override_ttl(iid: str):
    """After seeding, extend all cache entries for this institution to TTL_PERMANENT."""
    import sqlite3
    with sqlite3.connect(os.getenv("CACHE_DB_PATH", "cache.db")) as conn:
        conn.execute(
            "UPDATE cache SET ttl = ? WHERE key LIKE ?",
            (TTL_PERMANENT, f"%{iid}%"),
        )
        conn.execute(
            "UPDATE cache SET ttl = ? WHERE key LIKE ?",
            (TTL_PERMANENT, "%dimensions%"),
        )
        conn.commit()
    log.info("  All seeded entries extended to 365-day TTL.")


def seed_openalex(iid: str):
    log.info("── OpenAlex ─────────────────────────────────────────")

    # Force-invalidate existing cache so we re-fetch fresh data
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

    # Invalidate ALL top_authors entries (new format includes page/per_page/search)
    import sqlite3
    with sqlite3.connect(os.getenv("CACHE_DB_PATH", "cache.db")) as conn:
        conn.execute("DELETE FROM cache WHERE key LIKE '%top_authors%'")
        conn.commit()
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

    # Seed first page of authors (subsequent pages load on demand)
    log.info("  Fetching authors page 1 …")
    try:
        oa.get_top_authors(page=1, per_page=25)
        log.info("  ✓ authors page 1")
    except Exception as e:
        log.warning(f"  ✗ authors page 1 — {e}")

    # Seed first 3 pages of publication list
    log.info("  Fetching publication list pages 1-3 …")
    for page in range(1, 4):
        cache_key = f"openalex:pubs_list:{iid}:{page}:25:::"
        cache.invalidate(cache_key)
        try:
            oa.get_publications_list(page=page, per_page=25)
            log.info(f"  ✓ publications list page {page}")
        except Exception as e:
            log.warning(f"  ✗ publications list page {page} — {e}")
        time.sleep(0.5)

    log.info("  OpenAlex seeding complete.\n")


def seed_dimensions():
    api_key = os.getenv("DIMENSIONS_API_KEY", "")
    if not api_key:
        log.info("── Dimensions AI ─── (skipped — no DIMENSIONS_API_KEY in .env)")
        return

    log.info("── Dimensions AI ────────────────────────────────────")

    GRID_ID = "grid.251313.7"
    dim_keys = [
        f"dimensions:pubs_by_year:{GRID_ID}",
        f"dimensions:publications:{GRID_ID}",
        f"dimensions:grants:{GRID_ID}",
        f"dimensions:researchers:{GRID_ID}",
        f"dimensions:clinical_trials:{GRID_ID}",
        f"dimensions:patents:{GRID_ID}",
        f"dimensions:collab_orgs:{GRID_ID}",
        # also clear old wrong GRID ID entries if present
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


def _fetch_all_authors(per_page: int = 100) -> list:
    """
    Paginate through ALL UM Oxford authors from OpenAlex.
    Uses last_known_institutions filter so only current UM authors are returned.
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
            log.info(f"  Fetched page {page} ({len(all_authors)}/{total} authors)")

            if len(all_authors) >= total:
                break

            page += 1
            time.sleep(0.5)  # polite delay between OpenAlex pages

        except Exception as e:
            log.warning(f"  Failed fetching authors page {page}: {e}")
            break

    return all_authors


def seed_citation_sources():
    """
    Pre-warm citation source data for ALL UM Oxford authors.

    Paginates through the full OpenAlex author list (not just top 50),
    fetches each author's DOIs, then queries Dimensions for their
    outgoing citation sources. Skips authors already in cache.

    This is the most time-consuming step — allow 1-3 hours for a full
    institution depending on author count and Dimensions rate limits.
    Use --citations-only to run just this step after initial seeding.
    """
    api_key = os.getenv("DIMENSIONS_API_KEY", "")
    if not api_key:
        log.info("── Citation Sources ─── (skipped — no DIMENSIONS_API_KEY)")
        return

    log.info("── Citation Sources ─────────────────────────────────")
    log.info("  Fetching ALL UM Oxford authors from OpenAlex (paginated) …")

    authors = _fetch_all_authors(per_page=100)

    if not authors:
        log.warning("  No authors returned — skipping citation sources")
        return

    log.info(f"\n  {len(authors)} total authors to process.")
    log.info("  Authors already cached will be skipped.")
    log.info("  Estimated time: ~5-10 seconds per author (Dimensions rate limit)\n")

    success = 0
    skipped = 0
    failed  = 0

    for idx, author in enumerate(authors, 1):
        aid  = author.get("id", "")
        name = author.get("name", aid)

        if not aid:
            continue

        # Skip if already cached and non-empty
        cache_key = f"dimensions:citation_sources:{aid}"
        existing = cache.get(cache_key)
        if existing is not None:
            log.info(f"  [{idx:4d}/{len(authors)}] ⟳ {name} ({len(existing)} sources cached, skipping)")
            skipped += 1
            continue

        log.info(f"  [{idx:4d}/{len(authors)}] {name}")

        # Step 1: get DOIs from OpenAlex
        try:
            dois = oa.get_author_dois(aid)
        except Exception as e:
            log.warning(f"    ✗ DOI fetch failed: {e}")
            failed += 1
            continue

        if not dois:
            log.info(f"    (no DOIs — skipping)")
            # Cache empty result so we don't retry on next seed run
            cache.set(cache_key, [], "dimensions", TTL_PERMANENT)
            skipped += 1
            continue

        log.info(f"    {len(dois)} DOIs → Dimensions …")

        # Step 2: get outgoing citation sources from Dimensions
        try:
            sources = dim.get_author_citation_sources(aid, dois)
            log.info(f"    ✓ {len(sources)} unique sources")
            success += 1
        except Exception as e:
            log.warning(f"    ✗ Dimensions failed: {e}")
            failed += 1

        # Dimensions rate limit: 30 req/min — be conservative
        time.sleep(3)

        # Progress checkpoint every 25 authors
        if idx % 25 == 0:
            log.info(f"\n  ── Checkpoint: {success} done, {skipped} skipped, {failed} failed ──\n")

    log.info(f"\n  Citation sources complete:")
    log.info(f"    ✓ Seeded:  {success}")
    log.info(f"    ⟳ Skipped: {skipped} (already cached)")
    log.info(f"    ✗ Failed:  {failed}")
    log.info(f"    Total:     {len(authors)}\n")


def main():
    parser = argparse.ArgumentParser(description="Seed cache.db from OpenAlex + Dimensions AI")
    parser.add_argument("--refresh",        action="store_true", help="Clear expired entries before seeding")
    parser.add_argument("--skip-citations", action="store_true", help="Skip citation sources seeding (faster)")
    parser.add_argument("--citations-only", action="store_true", help="Only run citation sources seeding (skip OpenAlex + Dimensions general data)")
    args = parser.parse_args()

    log.info("═══════════════════════════════════════════════")
    log.info("  UM Research Dashboard — Data Seeder")
    log.info("═══════════════════════════════════════════════\n")

    if args.refresh:
        cache.clear_expired()
        log.info("Cleared expired cache entries.\n")

    # Verify / resolve institution ID
    log.info("── Institution verification ──────────────────────────")
    iid = oa.verify_institution()
    log.info(f"  Institution ID: {iid}\n")

    if not args.citations_only:
        seed_openalex(iid)
        seed_dimensions()

    if args.citations_only or not args.skip_citations:
        seed_citation_sources()
    else:
        log.info("── Citation Sources ─── (skipped via --skip-citations flag)")

    # Extend all seeded keys to 1-year TTL
    override_ttl(iid)

    # Summary
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