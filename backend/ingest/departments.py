"""Parse UM-Oxford departments out of Dimensions ``raw_affiliation`` strings.

Dimensions embeds the department *before* the institution inside each author's
affiliation, e.g.:

    "Department of Chemistry and Biochemistry, The University of Mississippi,
     University, MS 38677, United States"

We keep only Oxford-campus UM affiliations (zip ``38677`` / city ``University,
MS``) — excluding UMMC Jackson and unrelated orgs like "Mississippi School for
Math and Science, Columbus" — and take the leading segment(s) before
"University of Mississippi" as the department, then normalize so spelling
variants group together.
"""
from __future__ import annotations

import html
import re

# Markers that identify an academic unit (department/school/etc.). Labs, programs,
# and minors are intentionally excluded — those are PI groups / sub-units, not
# departments, and were the bulk of the noisy long tail.
_DEPT_MARKERS = (
    "department",
    "dept",
    "school",
    "college",
    "division",
    "center",
    "centre",
    "institute",
)

# Segments that are job titles / addresses / people / other institutions — not a
# UM academic unit. If any appears in a segment, it is not treated as a department.
_NON_DEPT_MARKERS = (
    # titles / roles / people
    "professor",
    "chair",
    "dean",
    "provost",
    "president",
    "director",
    "corresponding",
    "adjunct",
    "visiting",
    "postdoctoral",
    "emeritus",
    "fellow",
    "student",
    "candidate",
    # stray address / sentence fragments
    "current address",
    "present address",
    "now at",
    "from the",
    "is with",
    "currently",
    "reviewer",
    "formerly",
    # other (non-UM) organizations that co-occur with a UM affiliation
    "agricultur",          # USDA / Agricultural Research Service (UM has no ag dept)
    "united states",
    "us department",
    "u.s. department",
    "shanghai",
)

# Anything matching these means the affiliation is NOT the Oxford campus.
_UM_NAME = "university of mississippi"
_OXFORD_MARKERS = ("38677", "university, ms")  # Oxford campus zip / city
_NON_OXFORD = (
    "medical center",
    "ummc",
    "jackson",
    "school for mathematics and science",
    "school for math and science",
)

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 &]+")
_AND = re.compile(r"\s*&\s*")
_LEADING_JUNK = re.compile(r"^[\d\W_]+")          # footnote numbers/markers: "4 ", "221 "
_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")  # trailing acronym: "… (ECE)"
# "Psychology Department" / "Modern Languages School" -> reorder for grouping.
_SUFFIX_UNIT = re.compile(
    r"^(.+?) (department|school|college|division|institute|center|centre)$"
)


def is_um_oxford(raw_affiliation: str) -> bool:
    """True if the affiliation string is the UM Oxford campus."""
    low = html.unescape(raw_affiliation).lower()
    if _UM_NAME not in low:
        return False
    if any(bad in low for bad in _NON_OXFORD):
        return False
    return any(mark in low for mark in _OXFORD_MARKERS)


# Cut a compound unit ("Department of Biology and Center for Water…") down to the
# first unit. Keeps "Chemistry and Biochemistry" (Biochemistry isn't a unit word).
_COMPOUND_CUT = re.compile(
    r"\s+and\s+(?:the\s+)?(?:center|centre|institute|division|college|school|"
    r"program|programme|minor|core|laboratory|department)\b.*$",
    flags=re.I,
)
_TRAILING_AT = re.compile(r"\s+at(?:\s+the)?$", flags=re.I)
_LEADING_FOOTNOTE = re.compile(r"^[a-z]\s+")  # stray footnote letter: "a Department…"


def extract_department(raw_affiliation: str) -> str | None:
    """Return the department display string, or None if not a UM-Oxford dept.

    Takes the comma-separated segments before "University of Mississippi",
    cleans footnote markers/HTML entities/titles, collapses compound units, and
    keeps the FIRST segment that looks like an academic unit. Returns None when no
    segment is a recognizable unit, so titles/fragments don't become departments.
    """
    if not raw_affiliation:
        return None
    raw_affiliation = html.unescape(raw_affiliation)
    if not is_um_oxford(raw_affiliation):
        return None

    low = raw_affiliation.lower()
    idx = low.find(_UM_NAME)
    head = raw_affiliation[:idx]

    cleaned: list[str] = []
    for s in re.split(r"[;,/]|\s-\s", head):
        s = _TRAILING_PAREN.sub("", s.strip())
        s = _LEADING_JUNK.sub("", s).strip()
        s = _LEADING_FOOTNOTE.sub("", s).strip()
        s = re.sub(r"^the\s+", "", s, flags=re.I).strip()
        s = _COMPOUND_CUT.sub("", s).strip()
        s = _TRAILING_AT.sub("", s).strip()
        if s and s.lower() != "the":
            cleaned.append(s)

    dept_segments = [s for s in cleaned if _looks_like_dept(s)]
    if not dept_segments:
        return None
    return dept_segments[0] or None


def normalize_department(name: str) -> str:
    """Canonical key: groups 'Dept. of Chemistry & Biochemistry', the full form,
    and 'Chemistry and Biochemistry Department' together."""
    n = html.unescape(name).lower()
    n = _LEADING_JUNK.sub("", n)
    n = _LEADING_FOOTNOTE.sub("", n)
    n = _TRAILING_PAREN.sub("", n)
    n = n.replace("dept.", "department").replace("dept ", "department ")
    n = _AND.sub(" and ", n)
    n = _PUNCT.sub(" ", n)
    n = _WS.sub(" ", n).strip()
    # Reorder "<x> department" -> "department of <x>" so suffix/prefix forms group.
    m = _SUFFIX_UNIT.match(n)
    if m:
        n = f"{m.group(2)} of {m.group(1)}"
    # Drop the leading unit word so "department of biology" and "biology" group,
    # and unify common word variants for better deduplication.
    n = re.sub(r"^(departments?|divisions?|schools?|colleges?|centers?|centres?|institutes?)\s+(?:of\s+)?", "", n)
    n = n.replace("centre", "center")
    n = n.replace("geologic ", "geological ").replace("biomelecular", "biomolecular")
    # Drop connector words so "center for x"/"center of x" and "x and y"/"x y" group.
    n = re.sub(r"\b(and|of|for|the)\b", " ", n)
    # Naive singularisation so "sciences"/"science", "products"/"product" group.
    n = " ".join(w[:-1] if len(w) > 4 and w.endswith("s") else w for w in n.split())
    n = _WS.sub(" ", n).strip()
    return n


def _looks_like_dept(segment: str) -> bool:
    low = segment.lower()
    if any(bad in low for bad in _NON_DEPT_MARKERS):
        return False
    return any(mark in low for mark in _DEPT_MARKERS)


def parse_excel_authors_field(value: str):
    """Parse the Excel 'Authors (Raw Affiliation)' field into (name, dept) pairs.

    Format: 'Last, First (affiliation); Last, First (affiliation); ...'. Used by
    tests and as a fallback; the live pipeline reads structured DSL author data.
    """
    out: list[tuple[str, str | None]] = []
    # Split on ');' boundaries while keeping each author's parenthetical intact.
    for chunk in re.split(r"\)\s*;\s*", value):
        m = re.match(r"\s*(.+?)\s*\((.+?)\)?\s*$", chunk)
        if not m:
            continue
        name, aff = m.group(1).strip(), m.group(2).strip()
        out.append((name, extract_department(aff)))
    return out
