"""
seed_missing_citations.py

Fetches Dimensions citation source data for UM authors that are in the
small cache but have no citation data in either cache.

Run: python seed_missing_citations.py --db "C:/Users/msota/Documents/cache.db"
"""

import sqlite3
import json
import os
import time
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed_missing")

parser = argparse.ArgumentParser()
parser.add_argument("--db", required=True, help="Path to the small (1600-author) cache.db")
args = parser.parse_args()

from backend.api.cache import CacheManager
from backend.api.openalex import OpenAlexClient
from backend.api.dimensions import DimensionsClient

# Point cache manager at the specified db file
cache = CacheManager(args.db)
oa    = OpenAlexClient(os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"), cache)
dim   = DimensionsClient(os.getenv("DIMENSIONS_API_KEY", ""), cache)

TTL_PERMANENT = 365 * 24 * 3600

# ── Step 1: get all UM author IDs from the small cache ───────────────────────
log.info(f"Reading UM authors from {args.db} ...")
conn = sqlite3.connect(args.db)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT data FROM cache WHERE key LIKE 'openalex:top_authors:%'"
).fetchall()
conn.close()

um_authors = {}
for row in rows:
    try:
        data = json.loads(row["data"])
        for a in data.get("items", []):
            aid = a.get("id", "").strip()
            if aid:
                um_authors[aid] = a.get("name", aid)
    except Exception:
        continue

log.info(f"  {len(um_authors)} total UM authors in cache")

# ── Step 2: find which ones are missing citation data ────────────────────────
missing = []
for aid, name in um_authors.items():
    existing = cache.get(f"dimensions:citation_sources:{aid}")
    if existing is None:
        missing.append((aid, name))

log.info(f"  {len(missing)} authors are missing citation data")

if not missing:
    log.info("Nothing to do — all authors already have citation data.")
    exit(0)

# ── Step 3: fetch for each missing author ─────────────────────────────────────
log.info(f"\nFetching citation data for {len(missing)} authors ...\n")

success = 0
skipped = 0
failed  = 0

for idx, (aid, name) in enumerate(missing, 1):
    log.info(f"  [{idx:3d}/{len(missing)}] {name}")

    # Get DOIs from OpenAlex
    try:
        dois = oa.get_author_dois(aid)
    except Exception as e:
        log.warning(f"    ✗ DOI fetch failed: {e}")
        failed += 1
        continue

    if not dois:
        log.info(f"    (no DOIs — caching empty)")
        cache.set(f"dimensions:citation_sources:{aid}", [], "dimensions", TTL_PERMANENT)
        skipped += 1
        continue

    log.info(f"    {len(dois)} DOIs → Dimensions ...")

    # Fetch citation sources
    try:
        sources = dim.get_author_citation_sources(aid, dois)
        log.info(f"    ✓ {len(sources)} unique sources")
        success += 1
    except Exception as e:
        log.warning(f"    ✗ Dimensions failed: {e}")
        failed += 1

    time.sleep(3)  # Dimensions rate limit

log.info(f"""
  Done!
    ✓ Seeded:  {success}
    ⟳ Skipped: {skipped} (no DOIs)
    ✗ Failed:  {failed}
""")