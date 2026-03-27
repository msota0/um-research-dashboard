import json
import time
import unicodedata
from typing import Any, Dict, List, Optional

import requests

OPENALEX_BASE = "https://api.openalex.org"
ROR_ID = "https://ror.org/02teq1165"
FALLBACK_ID = "I145858726"

# Replace with your email for OpenAlex polite pool usage
EMAIL = "research@olemiss.edu"

# The 13 visible names from your screenshot
TEST_NAMES = [
    "Shigeyuki Yokoyama",
    "Javed Butler",
    "George L. Bakris",
    "L. Cremaldi",
    "Ikhlas A. Khan",
    "Erik Hom",
    "Stephan Lang",
    "Thomas H. Mosley",
    "Javed Butler",           # duplicate intentionally preserved
    "Thomas Märshall",
    "Stephen O. Duke",
    "Paul D. Loprinzi",
    "Jeremy P. Loenneke",
]


class OpenAlexTester:
    def __init__(self, email: str):
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"UM-Oxford-Author-Tester/1.0 (mailto:{email})"
        })

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, retries: int = 3) -> Dict[str, Any]:
        url = f"{OPENALEX_BASE}{path}"
        final_params = {"mailto": self.email}
        if params:
            final_params.update(params)

        delay = 2
        last_error = None

        for attempt in range(retries):
            try:
                response = self.session.get(url, params=final_params, timeout=30)

                if response.status_code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                time.sleep(0.5)  # polite delay
                return response.json()

            except requests.RequestException as exc:
                last_error = exc
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"Request failed after retries: {last_error}")

    def resolve_um_oxford_institution(self) -> Dict[str, Any]:
        """
        Resolve University of Mississippi (Oxford campus) using the ROR first,
        then fall back to a strict OpenAlex institution search.
        """
        # Strategy 1: exact ROR lookup
        try:
            ror_short = ROR_ID.replace("https://ror.org/", "")
            data = self._get(f"/institutions/ror:{ror_short}")

            institution = {
                "openalex_id_full": data.get("id", ""),
                "openalex_id": data.get("id", "").split("/")[-1],
                "display_name": data.get("display_name", ""),
                "ror": (data.get("ids", {}) or {}).get("ror"),
                "geo": data.get("geo", {}) or {},
                "works_count": data.get("works_count", 0),
                "cited_by_count": data.get("cited_by_count", 0),
            }

            city = (institution["geo"].get("city") or "").strip().lower()
            if institution["openalex_id"] and city == "oxford":
                return {
                    "resolution_method": "ror_lookup",
                    "institution": institution,
                }
        except Exception as exc:
            print(f"[warn] ROR lookup failed: {exc}")

        # Strategy 2: strict text search fallback
        exclude_terms = (
            "medical",
            "school of medicine",
            "health science",
            "dental",
            "pharmacy",
            "nursing",
            "jackson",
        )

        data = self._get("/institutions", {
            "search": "university of mississippi",
            "filter": "country_code:US",
            "per-page": "25",
        })

        for inst in data.get("results", []):
            name = (inst.get("display_name") or "").lower()
            geo = inst.get("geo", {}) or {}
            ror = (inst.get("ids", {}) or {}).get("ror", "")

            city_match = (geo.get("city") or "").lower() == "oxford"
            country_match = geo.get("country_code") == "US"
            no_exclusions = not any(term in name for term in exclude_terms)
            ror_match = (ror == ROR_ID) if ror else True

            if city_match and country_match and no_exclusions and ror_match:
                return {
                    "resolution_method": "strict_search",
                    "institution": {
                        "openalex_id_full": inst.get("id", ""),
                        "openalex_id": inst.get("id", "").split("/")[-1],
                        "display_name": inst.get("display_name", ""),
                        "ror": ror,
                        "geo": geo,
                        "works_count": inst.get("works_count", 0),
                        "cited_by_count": inst.get("cited_by_count", 0),
                    }
                }

        return {
            "resolution_method": "fallback_id",
            "institution": {
                "openalex_id_full": f"https://openalex.org/{FALLBACK_ID}",
                "openalex_id": FALLBACK_ID,
                "display_name": "University of Mississippi (fallback)",
                "ror": ROR_ID,
                "geo": {"city": "Oxford", "country_code": "US"},
                "works_count": None,
                "cited_by_count": None,
            }
        }

    @staticmethod
    def normalize_name(name: str) -> str:
        if not name:
            return ""
        name = unicodedata.normalize("NFKD", name)
        name = "".join(ch for ch in name if not unicodedata.combining(ch))
        return " ".join(name.lower().split())

    @staticmethod
    def simplify_institutions(insts: Any) -> List[Dict[str, Any]]:
        if not isinstance(insts, list):
            return []

        rows = []
        for inst in insts:
            rows.append({
                "id": inst.get("id"),
                "openalex_id": (inst.get("id") or "").split("/")[-1] if inst.get("id") else "",
                "display_name": inst.get("display_name"),
                "ror": (inst.get("ids", {}) or {}).get("ror"),
                "type": inst.get("type"),
                "country_code": (inst.get("geo", {}) or {}).get("country_code"),
                "city": (inst.get("geo", {}) or {}).get("city"),
            })
        return rows

    @staticmethod
    def simplify_affiliations(affiliations: Any, limit: int = 15) -> List[Dict[str, Any]]:
        if not isinstance(affiliations, list):
            return []

        rows = []
        for aff in affiliations[:limit]:
            inst = aff.get("institution", {}) or {}
            rows.append({
                "years": aff.get("years", []),
                "institution_id": inst.get("id"),
                "institution_openalex_id": (inst.get("id") or "").split("/")[-1] if inst.get("id") else "",
                "institution_name": inst.get("display_name"),
                "institution_ror": (inst.get("ids", {}) or {}).get("ror"),
                "institution_type": inst.get("type"),
                "institution_country_code": (inst.get("geo", {}) or {}).get("country_code"),
                "institution_city": (inst.get("geo", {}) or {}).get("city"),
            })
        return rows

    def fetch_dashboard_style_authors(self, inst_id: str, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Reproduce the dashboard-style author filter:
        last_known_institutions.id:{inst_id},affiliations.institution.id:{inst_id}
        """
        data = self._get("/authors", {
            "filter": f"last_known_institutions.id:{inst_id},affiliations.institution.id:{inst_id}",
            "sort": "works_count:desc",
            "per-page": str(per_page),
            "page": "1",
            "select": (
                "id,display_name,works_count,cited_by_count,summary_stats,orcid,"
                "last_known_institutions,affiliations"
            ),
        })
        return data.get("results", [])

    def search_author_globally(self, name: str, per_page: int = 10) -> List[Dict[str, Any]]:
        data = self._get("/authors", {
            "search": name,
            "per-page": str(per_page),
            "select": (
                "id,display_name,works_count,cited_by_count,summary_stats,orcid,"
                "last_known_institutions,affiliations"
            ),
        })
        return data.get("results", [])

    def search_author_with_um_filter(self, name: str, inst_id: str, per_page: int = 10) -> List[Dict[str, Any]]:
        data = self._get("/authors", {
            "search": name,
            "filter": f"last_known_institutions.id:{inst_id},affiliations.institution.id:{inst_id}",
            "per-page": str(per_page),
            "select": (
                "id,display_name,works_count,cited_by_count,summary_stats,orcid,"
                "last_known_institutions,affiliations"
            ),
        })
        return data.get("results", [])

    def build_author_snapshot(self, author: Dict[str, Any], um_inst_id: str) -> Dict[str, Any]:
        last_known = self.simplify_institutions(author.get("last_known_institutions"))
        affiliations = self.simplify_affiliations(author.get("affiliations"))

        last_known_ids = [x["openalex_id"] for x in last_known if x.get("openalex_id")]
        affiliation_ids = [
            x["institution_openalex_id"]
            for x in affiliations
            if x.get("institution_openalex_id")
        ]

        return {
            "author_id_full": author.get("id", ""),
            "author_id": author.get("id", "").split("/")[-1],
            "display_name": author.get("display_name"),
            "normalized_display_name": self.normalize_name(author.get("display_name", "")),
            "works_count": author.get("works_count", 0),
            "cited_by_count": author.get("cited_by_count", 0),
            "h_index": (author.get("summary_stats") or {}).get("h_index", 0),
            "orcid": author.get("orcid"),
            "last_known_ids": last_known_ids,
            "affiliation_ids_sample": affiliation_ids,
            "matches_um_in_last_known": um_inst_id in last_known_ids,
            "matches_um_in_affiliations": um_inst_id in affiliation_ids,
            "last_known_institutions": last_known,
            "affiliations_sample": affiliations,
        }

    def pick_exact_name_matches(self, name: str, authors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        target = self.normalize_name(name)
        exact = []
        for author in authors:
            display_name = author.get("display_name", "")
            if self.normalize_name(display_name) == target:
                exact.append(author)
        return exact


def main() -> None:
    tester = OpenAlexTester(EMAIL)

    print("=" * 100)
    print("Resolving University of Mississippi (Oxford campus) institution")
    print("=" * 100)
    inst_info = tester.resolve_um_oxford_institution()
    um_inst = inst_info["institution"]
    um_inst_id = um_inst["openalex_id"]

    print(json.dumps(inst_info, indent=2, ensure_ascii=False))

    print("\n" + "=" * 100)
    print("Fetching dashboard-style author page (same filter logic)")
    print("=" * 100)
    dashboard_authors = tester.fetch_dashboard_style_authors(um_inst_id, per_page=100)

    dashboard_rows = []
    for idx, author in enumerate(dashboard_authors, start=1):
        dashboard_rows.append({
            "rank": idx,
            "author_id": author.get("id", "").split("/")[-1],
            "display_name": author.get("display_name"),
            "works_count": author.get("works_count", 0),
            "cited_by_count": author.get("cited_by_count", 0),
            "h_index": (author.get("summary_stats") or {}).get("h_index", 0),
            "orcid": author.get("orcid"),
        })

    print(json.dumps(dashboard_rows[:25], indent=2, ensure_ascii=False))

    print("\n" + "=" * 100)
    print("Testing the 13 names from the screenshot")
    print("=" * 100)

    final_report = {
        "institution_resolution": inst_info,
        "dashboard_page_1_top_25": dashboard_rows[:25],
        "test_cases": [],
    }

    for idx, name in enumerate(TEST_NAMES, start=1):
        print(f"\n[{idx}/{len(TEST_NAMES)}] Checking: {name}")

        # 1) Exact match inside dashboard-style page results
        dashboard_exact_matches = tester.pick_exact_name_matches(name, dashboard_authors)

        # 2) Search by name globally
        global_candidates = tester.search_author_globally(name, per_page=10)
        global_exact_matches = tester.pick_exact_name_matches(name, global_candidates)

        # 3) Search by name with UM filter
        um_candidates = tester.search_author_with_um_filter(name, um_inst_id, per_page=10)
        um_exact_matches = tester.pick_exact_name_matches(name, um_candidates)

        dashboard_snapshots = [
            tester.build_author_snapshot(author, um_inst_id)
            for author in dashboard_exact_matches
        ]
        global_snapshots = [
            tester.build_author_snapshot(author, um_inst_id)
            for author in global_exact_matches
        ]
        um_snapshots = [
            tester.build_author_snapshot(author, um_inst_id)
            for author in um_exact_matches
        ]

        # Quick summary flags
        appears_on_dashboard_page = len(dashboard_snapshots) > 0
        appears_in_global_search = len(global_snapshots) > 0
        appears_in_um_filtered_search = len(um_snapshots) > 0

        likely_um_by_last_known = any(x["matches_um_in_last_known"] for x in (
            dashboard_snapshots + global_snapshots + um_snapshots
        ))
        likely_um_by_affiliations = any(x["matches_um_in_affiliations"] for x in (
            dashboard_snapshots + global_snapshots + um_snapshots
        ))

        entry = {
            "input_name": name,
            "normalized_input_name": tester.normalize_name(name),
            "appears_on_dashboard_page": appears_on_dashboard_page,
            "appears_in_global_search": appears_in_global_search,
            "appears_in_um_filtered_search": appears_in_um_filtered_search,
            "likely_um_by_last_known": likely_um_by_last_known,
            "likely_um_by_affiliations": likely_um_by_affiliations,
            "dashboard_exact_matches": dashboard_snapshots,
            "global_exact_matches": global_snapshots,
            "um_filtered_exact_matches": um_snapshots,
        }

        final_report["test_cases"].append(entry)

        print(json.dumps({
            "input_name": name,
            "appears_on_dashboard_page": appears_on_dashboard_page,
            "appears_in_global_search": appears_in_global_search,
            "appears_in_um_filtered_search": appears_in_um_filtered_search,
            "likely_um_by_last_known": likely_um_by_last_known,
            "likely_um_by_affiliations": likely_um_by_affiliations,
            "dashboard_match_count": len(dashboard_snapshots),
            "global_match_count": len(global_snapshots),
            "um_filtered_match_count": len(um_snapshots),
        }, indent=2, ensure_ascii=False))

    output_path = "um_oxford_author_test_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 100)
    print(f"Detailed report written to: {output_path}")
    print("=" * 100)


if __name__ == "__main__":
    main()