"""Tests for the Dimensions raw_affiliation department parser."""
from backend.ingest import departments as d

# A real example string from the user's Dimensions export.
EXAMPLE = (
    "Edgecomb, Sara X. (Department of Chemistry and Biochemistry, The University "
    "of Mississippi, University, MS 38677, United States); Ontiveros, Amber I. "
    "(School of Pharmacy, The University of Mississippi, University, MS 38677, "
    "United States); Parker, Margaret V. (Mississippi School for Math and "
    "Science, Columbus, MS 39701, United States); Tanner, Eden E.L. (Department "
    "of Chemistry and Biochemistry, The University of Mississippi, University, "
    "MS 38677, United States)"
)


def test_extract_department_from_um_oxford():
    aff = ("Department of Chemistry and Biochemistry, The University of "
           "Mississippi, University, MS 38677, United States")
    assert d.extract_department(aff) == "Department of Chemistry and Biochemistry"


def test_school_of_pharmacy():
    aff = "School of Pharmacy, The University of Mississippi, University, MS 38677, USA"
    assert d.extract_department(aff) == "School of Pharmacy"


def test_non_oxford_affiliations_excluded():
    # Columbus high school — not UM Oxford.
    assert d.extract_department(
        "Mississippi School for Math and Science, Columbus, MS 39701, United States"
    ) is None
    # UMMC Jackson must be excluded even though it says University of Mississippi.
    assert d.extract_department(
        "Department of Medicine, University of Mississippi Medical Center, "
        "Jackson, MS 39216, United States"
    ) is None


def test_department_less_um_affiliation_returns_none():
    # "(The) University of Mississippi" with no department must not crash.
    assert d.extract_department(
        "The University of Mississippi, University, MS 38677, United States"
    ) is None
    assert d.extract_department(
        "University of Mississippi, University, MS 38677, United States"
    ) is None


def test_leading_footnote_number_stripped():
    aff = ("4 Department of Geology and Geological Engineering, The University of "
           "Mississippi, University, MS 38677, United States")
    assert d.extract_department(aff) == "Department of Geology and Geological Engineering"


def test_trailing_acronym_and_first_unit_chosen():
    # Most-specific (department) chosen over the parent school; acronym dropped.
    aff = ("Department of Electrical and Computer Engineering (ECE), School of "
           "Engineering, The University of Mississippi, University, MS 38677, USA")
    assert d.extract_department(aff) == "Department of Electrical and Computer Engineering"


def test_title_fragment_is_not_a_department():
    # No academic-unit marker -> not a department.
    assert d.extract_department(
        "Associate Professor of Marketing, The University of Mississippi, "
        "University, MS 38677, United States"
    ) is None


def test_normalize_groups_variants():
    # The unit word is dropped from the key so spelling/entity variants group.
    a = d.normalize_department("Department of Chemistry and Biochemistry")
    b = d.normalize_department("Dept. of Chemistry & Biochemistry")
    c = d.normalize_department("Department of Chemistry &amp; Biochemistry")
    assert a == b == c == "chemistry biochemistry"


def test_normalize_groups_word_order_and_footnote():
    # "Psychology Department" and "Department of Psychology" must group.
    assert d.normalize_department("Psychology Department") == \
        d.normalize_department("Department of Psychology") == "psychology"
    # Leading footnote number/letter must not split the group.
    assert d.normalize_department("4 Department of Biology") == \
        d.normalize_department("a Department of Biology") == \
        d.normalize_department("Department of Biology") == "biology"
    # Missing "of" must still group.
    assert d.normalize_department("Department Biomolecular Sciences") == \
        d.normalize_department("Department of Biomolecular Sciences")


def test_parse_excel_authors_field():
    pairs = d.parse_excel_authors_field(EXAMPLE)
    names = [n for n, _ in pairs]
    depts = [dept for _, dept in pairs]
    assert "Edgecomb, Sara X." in names
    assert "Department of Chemistry and Biochemistry" in depts
    assert "School of Pharmacy" in depts
    # The Columbus high-school author parses to no UM-Oxford department.
    assert None in depts
