"""
merge_citation_cache.py

Copies citation_sources data from the large cache (7058 authors) into
the small cache (1600 genuine UM authors) — only for authors that exist
in BOTH caches.

Usage:
    python merge_citation_cache.py --small path/to/1600/cache.db --large path/to/7058/cache.db

Example:
    python merge_citation_cache.py --small cache.db --large C:/path/to/old/cache.db

big file- desktop
small file- documents

"""

import sqlite3
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--small", required=True, help="Path to the 1600-author cache.db (your main one)")
parser.add_argument("--large", required=True, help="Path to the 7058-author cache.db (the old one)")
args = parser.parse_args()

# ── Step 1: get the 1600 genuine UM author IDs from the small cache ───────────
print(f"Reading UM author IDs from: {args.small}")
small_conn = sqlite3.connect(args.small)
small_conn.row_factory = sqlite3.Row

rows = small_conn.execute(
    "SELECT data FROM cache WHERE key LIKE 'openalex:top_authors:%'"
).fetchall()

um_author_ids = set()
for row in rows:
    try:
        data = json.loads(row["data"])
        for a in data.get("items", []):
            aid = a.get("id", "").strip()
            if aid:
                um_author_ids.add(aid)
    except Exception:
        continue

print(f"  {len(um_author_ids)} genuine UM authors found")

# ── Step 2: open the large cache and find citation data for those authors ──────
print(f"\nReading citation data from: {args.large}")
large_conn = sqlite3.connect(args.large)
large_conn.row_factory = sqlite3.Row

# Build the cache keys we want
wanted_keys = [f"dimensions:citation_sources:{aid}" for aid in um_author_ids]

# Check which ones exist in the large cache
found = []
for key in wanted_keys:
    row = large_conn.execute(
        "SELECT key, data, source, fetched_at, ttl FROM cache WHERE key = ?", (key,)
    ).fetchone()
    if row:
        found.append(dict(row))

print(f"  {len(found)} of {len(um_author_ids)} UM authors have citation data in large cache")

# ── Step 3: copy into the small cache (skip if already exists) ────────────────
print(f"\nMerging into: {args.small}")
copied   = 0
skipped  = 0
for entry in found:
    # Check if already in small cache
    existing = small_conn.execute(
        "SELECT key FROM cache WHERE key = ?", (entry["key"],)
    ).fetchone()

    if existing:
        skipped += 1
        continue

    small_conn.execute(
        "INSERT INTO cache (key, data, source, fetched_at, ttl) VALUES (?, ?, ?, ?, ?)",
        (entry["key"], entry["data"], entry["source"], entry["fetched_at"], entry["ttl"])
    )
    copied += 1

small_conn.commit()
small_conn.close()
large_conn.close()

print(f"\n  ✓ Copied:   {copied} citation entries")
print(f"  ⟳ Skipped:  {skipped} (already in small cache)")
print(f"  ✗ Missing:  {len(um_author_ids) - len(found)} authors had no citation data in large cache")
print(f"\nDone — {args.small} now has citation data for all matched UM authors.")