"""Best-effort name matching between OpenAlex authors and Dimensions records.

Dimensions grants/patents carry NO ORCID, so linking them to our OpenAlex authors
relies on names. We use a conservative key — (surname, first-initial) — and, for
patents whose inventor strings have inconsistent token order, a token-bag fallback.

This is intentionally cautious: a wrong attribution on a named faculty page is worse
than a miss, so we require the full surname to match plus a first-initial hit.
"""
from __future__ import annotations

import re

_STOP = {"jr", "sr", "ii", "iii", "iv", "v", "phd", "md", "dr"}


def _tokens(s: str | None) -> list[str]:
    return [t for t in re.split(r"[^a-z]+", (s or "").lower()) if t and t not in _STOP]


def author_key(name: str | None) -> tuple[str, str] | None:
    """OpenAlex display name 'Jeremy P. Loenneke' -> ('loenneke', 'j').

    Returns None for unresolved names (e.g. bare OpenAlex ids 'A5103326514').
    """
    toks = _tokens(name)
    # Drop a bare-id token like 'a5103326514'.
    toks = [t for t in toks if not re.fullmatch(r"a\d{6,}", t)]
    if len(toks) < 2:
        return None
    surname = toks[-1]
    first_initial = toks[0][0]
    if len(surname) < 3:
        return None
    return surname, first_initial


def investigator_key(first_name: str | None, last_name: str | None) -> tuple[str, str] | None:
    """Dimensions grant investigator has explicit first/last name."""
    last = _tokens(last_name)
    first = _tokens(first_name)
    if not last or not first or len(last[-1]) < 3:
        return None
    return last[-1], first[0][0]


def inventor_matches(inventor: str, key: tuple[str, str]) -> bool:
    """Patent inventor strings have inconsistent order ('ELSOHLY MAHMOUD A' vs
    'TIMOTHY J HUBIN'). Match if the surname appears as a token AND some other
    token starts with the author's first initial."""
    surname, first_initial = key
    toks = _tokens(inventor)
    if surname not in toks:
        return False
    return any(t[0] == first_initial for t in toks if t != surname)
