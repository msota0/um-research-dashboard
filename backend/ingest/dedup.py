"""Deduplication & quality rules.

The same real-world paper shows up as several OpenAlex records (preprint vs.
published vs. repository mirror), and repositories/indexes + raw datasets inflate
the journal/type charts. This module centralizes every rule so the policy is
auditable and easy for contributors to tune:

* ``normalize_doi`` / ``normalize_title`` — canonical keys.
* ``EXCLUDED_TYPES`` — work types that don't count as publications.
* ``REPOSITORY_SOURCE_PATTERNS`` — venues that aren't journals.
* ``classify_excluded`` — why (if at all) a work is excluded from headlines.
* ``canonical_rank`` — which of several duplicates wins.
* ``fuzzy_duplicate`` — title+year near-match for DOI-less records.

Nothing here deletes data; the pipeline only *flags* rows (``excluded_reason``,
``is_duplicate_of``) so counts filter cleanly and the raw data stays auditable.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

# Work types that are valid publications for headline counts.
COUNTED_TYPES = {
    "article",
    "review",
    "book",
    "book-chapter",
    "book-section",
    "conference-paper",
    "proceedings-article",
    "report",
    "dissertation",
}
# Types explicitly excluded from headline publication/journal counts.
EXCLUDED_TYPES = {
    "dataset",
    "peer-review",
    "erratum",
    "paratext",
    "editorial",
    "letter",
    "grant",
    "other",
}

# Sources that are repositories / indexes / preprint servers, NOT journals.
# Matched case-insensitively as substrings against the source display name.
REPOSITORY_SOURCE_PATTERNS = (
    "repository",
    "pnnl",
    "osti",
    "pubmed",
    "ssrn",
    "dataverse",
    "zenodo",
    "figshare",
    "biorxiv",
    "medrxiv",
    "arxiv",
    "research square",
    "preprints",
    "catalogue of life",
    "datacite",
    "ebooks",  # publisher ebook aggregators (e.g. "Elsevier eBooks")
)

_DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def normalize_doi(doi: str | None) -> str | None:
    """Lowercase, strip the URL prefix. Returns None for empty/missing."""
    if not doi:
        return None
    d = _DOI_PREFIX.sub("", doi.strip().lower())
    return d or None


def normalize_title(title: str | None) -> str | None:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy matching."""
    if not title:
        return None
    t = _PUNCT.sub(" ", title.strip().lower())
    t = _WS.sub(" ", t).strip()
    return t or None


def is_repository_source(source_name: str | None) -> bool:
    if not source_name:
        return False
    low = source_name.lower()
    return any(p in low for p in REPOSITORY_SOURCE_PATTERNS)


def classify_excluded(work_type: str | None, source_name: str | None) -> str | None:
    """Return an exclusion reason, or None if the work counts in headlines.

    Order matters: type first (datasets dominate the noise), then venue.
    """
    if work_type in EXCLUDED_TYPES:
        return f"type:{work_type}"
    if is_repository_source(source_name):
        return "repository"
    if work_type and work_type not in COUNTED_TYPES:
        return f"type:{work_type}"
    return None


def canonical_rank(work_type: str | None, source_name: str | None) -> int:
    """Higher = more canonical. Published journal article beats preprint/repo.

    Used to choose the survivor among records sharing a DOI / fuzzy title.
    """
    if is_repository_source(source_name):
        return 0
    if work_type in ("preprint",):
        return 1
    if work_type in ("article", "review"):
        return 3
    if work_type in COUNTED_TYPES:
        return 2
    return 1


def fuzzy_duplicate(title_norm_a: str, title_norm_b: str, threshold: int = 95) -> bool:
    """True if two normalized titles are near-identical (token-sort ratio)."""
    if not title_norm_a or not title_norm_b:
        return False
    return fuzz.token_sort_ratio(title_norm_a, title_norm_b) >= threshold
