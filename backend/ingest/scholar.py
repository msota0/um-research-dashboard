"""Resolve a Google Scholar link per author, best-to-worst, cached once.

Google Scholar has no API. We therefore layer sources and store the result so
each author is resolved exactly once:

1. ORCID ``researcher-urls`` — official, ToS-clean; many researchers self-list
   their Scholar profile there.
2. ``scholarly`` scraping — best-effort, server-only, OFF by default
   (``ENABLE_SCHOLARLY``), rate-limited, match-verified by Mississippi. Fragile
   (Google blocks scraping) so it only ever *upgrades* a result.
3. A Google Scholar *search* link for the name — always works as a fallback.

Returns ``(url, source)`` where source ∈ {orcid, scholarly, search}.
"""
from __future__ import annotations

import re
import time
from urllib.parse import quote_plus

import httpx

_SCHOLAR_HOST = "scholar.google.com"


def search_link(name: str) -> str:
    q = quote_plus(f"{name} University of Mississippi")
    return f"https://scholar.google.com/scholar?q={q}"


def from_orcid(orcid: str | None, http: httpx.Client) -> str | None:
    """Look for a Scholar URL in the author's ORCID researcher-urls."""
    if not orcid:
        return None
    oid = orcid.rstrip("/").split("/")[-1]
    try:
        resp = http.get(
            f"https://pub.orcid.org/v3.0/{oid}/researcher-urls",
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        if resp.status_code != 200:
            return None
        for u in resp.json().get("researcher-url", []):
            url = ((u.get("url") or {}).get("value") or "").strip()
            if _SCHOLAR_HOST in url:
                return url
    except httpx.HTTPError:
        return None
    return None


def from_scholarly(name: str) -> str | None:
    """Best-effort scrape. Verifies the profile mentions Mississippi."""
    try:
        from scholarly import scholarly  # imported lazily; heavy + optional
    except ImportError:
        return None
    try:
        for _ in range(1):  # only inspect the top hit
            author = next(scholarly.search_author(f"{name} University of Mississippi"))
            affil = (author.get("affiliation") or "").lower()
            if "mississippi" in affil and author.get("scholar_id"):
                time.sleep(2.0)  # be gentle
                return f"https://scholar.google.com/citations?user={author['scholar_id']}"
    except Exception:
        return None
    return None


def resolve(
    name: str, orcid: str | None, http: httpx.Client, enable_scholarly: bool
) -> tuple[str, str]:
    url = from_orcid(orcid, http)
    if url:
        return url, "orcid"
    if enable_scholarly:
        url = from_scholarly(name)
        if url:
            return url, "scholarly"
    return search_link(name), "search"
