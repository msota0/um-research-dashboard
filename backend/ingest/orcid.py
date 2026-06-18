"""Best-effort ORCID iD recovery for authors OpenAlex/Dimensions didn't supply.

OpenAlex is the primary source of ORCID iDs (``stage_authors``) and Dimensions
publication-author records backfill a few more (``stage_dimensions``). For the
rest we query ORCID's public ``expanded-search`` API by surname + affiliation.

This is intentionally cautious — a wrong iD on a named faculty page is worse
than a miss — so a hit is accepted only when it is the *single* Mississippi-
affiliated result whose name matches our conservative (surname, first-initial)
key (the same guard ``name_match`` uses for Dimensions records).
"""
from __future__ import annotations

import httpx

from . import name_match

_SEARCH = "https://pub.orcid.org/v3.0/expanded-search/"


def url_from_id(raw) -> str | None:
    """Normalise an ORCID value (bare id, URL, or list) to a canonical URL."""
    if isinstance(raw, list):  # Dimensions sometimes returns a list of orcids
        raw = raw[0] if raw else None
    if not raw or not isinstance(raw, str):
        return None
    oid = raw.rstrip("/").split("/")[-1].strip()
    return f"https://orcid.org/{oid}" if oid else None


def search(name: str, http: httpx.Client) -> str | None:
    """Return a canonical ORCID URL for *name* at UM, or None if not confident."""
    key = name_match.author_key(name)
    if not key:  # unresolved/ambiguous name (e.g. a bare OpenAlex id)
        return None
    surname, _ = key
    q = f'family-name:"{surname}" AND affiliation-org-name:"University of Mississippi"'
    try:
        resp = http.get(
            _SEARCH,
            params={"q": q, "rows": 50},
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("expanded-result") or []
    except (httpx.HTTPError, ValueError):
        return None

    hits: set[str] = set()
    for r in results:
        institutions = " ".join(r.get("institution-name") or []).lower()
        if "mississippi" not in institutions:
            continue
        cand = f"{r.get('given-names') or ''} {r.get('family-names') or ''}"
        if name_match.author_key(cand) == key and r.get("orcid-id"):
            hits.add(r["orcid-id"])
    # Accept only an unambiguous single match.
    return url_from_id(next(iter(hits))) if len(hits) == 1 else None
