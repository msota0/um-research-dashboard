"""Tests for the dedup/quality rules — the logic that de-skews the dashboard."""
from backend.ingest import dedup


def test_normalize_doi_strips_prefix_and_lowercases():
    assert dedup.normalize_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert dedup.normalize_doi("http://dx.doi.org/10.2/X") == "10.2/x"
    assert dedup.normalize_doi("10.3/y") == "10.3/y"
    assert dedup.normalize_doi(None) is None
    assert dedup.normalize_doi("") is None


def test_normalize_title():
    assert dedup.normalize_title("  The  Effect: A Study! ") == "the effect a study"
    assert dedup.normalize_title(None) is None


def test_dataset_type_is_excluded():
    # The 2026 PNNL spike was ~20k datasets — must not count.
    assert dedup.classify_excluded("dataset", "Some Journal") == "type:dataset"


def test_repository_source_is_excluded():
    assert dedup.classify_excluded(
        "article", "DOE Pacific Northwest National Laboratory (PNNL) Repository"
    ) == "repository"
    assert dedup.classify_excluded("article", "SSRN Electronic Journal") == "repository"
    assert dedup.classify_excluded("article", "PubMed") == "repository"


def test_real_article_counts():
    assert dedup.classify_excluded("article", "Physical Review Letters") is None
    assert dedup.classify_excluded("review", "Nature Reviews") is None
    assert dedup.classify_excluded("book-chapter", "Springer Handbook") is None


def test_uncounted_type_excluded():
    assert dedup.classify_excluded("editorial", "Some Journal") == "type:editorial"
    assert dedup.classify_excluded("preprint", "Some Journal") == "type:preprint"


def test_canonical_rank_prefers_published_over_repository_and_preprint():
    article = dedup.canonical_rank("article", "Physical Review Letters")
    preprint = dedup.canonical_rank("preprint", None)  # a preprint, non-repo venue
    repo = dedup.canonical_rank("article", "PNNL Repository")
    assert article > preprint > repo


def test_fuzzy_duplicate_matches_near_identical_titles():
    a = dedup.normalize_title("Observation of Gravitational Waves from a Binary Black Hole Merger")
    b = dedup.normalize_title("Observation of gravitational waves from a binary black-hole merger")
    assert dedup.fuzzy_duplicate(a, b)
    c = dedup.normalize_title("A completely different paper about chemistry")
    assert not dedup.fuzzy_duplicate(a, c)
