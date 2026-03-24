import time
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DIMENSIONS_AUTH_URL = "https://app.dimensions.ai/api/auth"
DIMENSIONS_DSL_URL  = "https://app.dimensions.ai/api/dsl/v2"
GRID_ID = "grid.251313.7"
TOKEN_LIFETIME = 23 * 3600  # 23 hours


class DimensionsClient:
    def __init__(self, api_key: str, cache_manager=None):
        self.api_key = api_key
        self.cache = cache_manager
        self._token: Optional[str] = None
        self._token_acquired_at: float = 0
        self.session = requests.Session()

    def _ensure_token(self):
        if self._token and (time.time() - self._token_acquired_at) < TOKEN_LIFETIME:
            return
        self._authenticate()

    def _authenticate(self):
        if not self.api_key:
            logger.warning("No Dimensions API key configured.")
            self._token = None
            return
        try:
            resp = requests.post(
                DIMENSIONS_AUTH_URL,
                json={"key": self.api_key},
                timeout=30,
            )
            resp.raise_for_status()
            self._token = resp.json().get("token")
            self._token_acquired_at = time.time()
            logger.info("Dimensions API authenticated successfully.")
        except Exception as e:
            logger.error(f"Dimensions authentication failed: {e}")
            self._token = None

    def _query(self, dsl: str, retries: int = 3) -> dict:
        """
        Send a DSL query. The v2 endpoint expects the query as plain text
        in the request body (Content-Type: text/plain works reliably).
        """
        self._ensure_token()
        if not self._token:
            raise RuntimeError("Dimensions API token unavailable (check API key).")
        delay = 2
        for attempt in range(retries):
            try:
                resp = self.session.post(
                    DIMENSIONS_DSL_URL,
                    data=dsl.encode("utf-8"),
                    headers={
                        "Authorization": f"JWT {self._token}",
                        "Content-Type":  "text/plain",
                    },
                    timeout=60,
                )
                if resp.status_code == 429:
                    wait = min(delay * 2, 60)
                    logger.warning(f"Dimensions rate limited, waiting {wait}s")
                    time.sleep(wait)
                    delay = wait
                    continue
                if resp.status_code == 401:
                    logger.warning("Dimensions 401 — re-authenticating")
                    self._authenticate()
                    continue
                if resp.status_code == 400:
                    # Log the body so we can see the exact DSL error
                    logger.error(
                        f"Dimensions 400 Bad Request.\n"
                        f"  DSL: {dsl[:300]}\n"
                        f"  Response: {resp.text[:400]}"
                    )
                    resp.raise_for_status()
                resp.raise_for_status()
                time.sleep(2)   # polite delay between calls
                return resp.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 30)
        return {}

    # ── institution lookup helper ────────────────────────────────────────────

    def find_institution_id(self, name: str = "University of Mississippi") -> list:
        """
        Look up how Dimensions identifies UM Oxford.
        Run this once interactively if GRID ID needs to be confirmed:
            from api.dimensions import DimensionsClient
            d = DimensionsClient("your_key")
            print(d.find_institution_id())
        """
        dsl = (
            f'search organizations where name = "{name}" '
            f'return organizations[id+name+city_name+country_name] limit 10'
        )
        try:
            data = self._query(dsl)
            return data.get("organizations", [])
        except Exception as e:
            logger.error(f"find_institution_id failed: {e}")
            return []

    # ── publications ─────────────────────────────────────────────────────────

    def get_publications_by_year(self) -> list:
        cache_key = f"dimensions:pubs_by_year:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search publications where research_orgs = "{GRID_ID}" '
            f'return year'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions pubs by year failed: {e}")
            return []

        # v2 facet response shape: {"year": {"data": [{"id": 2020, "count": 123}, ...]}}
        results = []
        year_facet = data.get("year") or {}
        items = year_facet.get("data") if isinstance(year_facet, dict) else year_facet
        if isinstance(items, list):
            for item in items:
                yr  = item.get("id") or item.get("key")
                cnt = item.get("count", 0)
                if yr:
                    results.append({"year": yr, "count": cnt})
        results.sort(key=lambda x: x["year"] if x["year"] else 0)
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results

    def get_publications(self) -> list:
        cache_key = f"dimensions:publications:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search publications where research_orgs = "{GRID_ID}" '
            f'return publications[id+title+year+times_cited+open_access+journal+doi+type] '
            f'limit 1000'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions publications failed: {e}")
            return []
        results = []
        for pub in data.get("publications", []):
            results.append({
                "id":           pub.get("id"),
                "title":        pub.get("title"),
                "year":         pub.get("year"),
                "times_cited":  pub.get("times_cited", 0),
                "open_access":  pub.get("open_access"),
                "journal":      pub.get("journal", {}).get("title") if isinstance(pub.get("journal"), dict) else None,
                "doi":          pub.get("doi"),
                "type":         pub.get("type"),
            })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    # ── grants ───────────────────────────────────────────────────────────────

    def get_grants(self) -> list:
        cache_key = f"dimensions:grants:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search grants where research_orgs = "{GRID_ID}" '
            f'return grants[id+title+start_date+end_date+funding_usd+funder_org_name+category_for] '
            f'limit 1000'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions grants failed: {e}")
            return []
        results = data.get("grants", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    # ── researchers ──────────────────────────────────────────────────────────

    def get_researchers(self) -> list:
        cache_key = f"dimensions:researchers:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search publications where research_orgs = "{GRID_ID}" '
            f'return researchers[id+first_name+last_name+orcid_id+total_grants+research_orgs] '
            f'limit 25'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions researchers failed: {e}")
            return []
        results = data.get("researchers", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    # ── clinical trials (subscription-gated) ─────────────────────────────────

    def get_clinical_trials(self) -> list:
        cache_key = f"dimensions:clinical_trials:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search clinical_trials where research_orgs = "{GRID_ID}" '
            f'return clinical_trials[id+title+current_status+date_inserted+phase+conditions] '
            f'limit 1000'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            # 400 here almost always means this source isn't in your subscription
            logger.warning(f"Dimensions clinical trials unavailable (check subscription): {e}")
            return []
        results = []
        for t in data.get("clinical_trials", []):
            results.append({
                "id":         t.get("id"),
                "title":      t.get("title"),
                "status":     t.get("current_status"),   # API field → frontend field
                "date":       t.get("date_inserted"),    # API field → frontend field
                "phase":      t.get("phase"),
                "conditions": t.get("conditions", []),
            })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    # ── patents ───────────────────────────────────────────────────────────────

    def get_patents(self) -> list:
        cache_key = f"dimensions:patents:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search patents where assignees = "{GRID_ID}" '
            f'return patents[id+title+date_filed+date_published+assignees] '
            f'limit 1000'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            # 400 here almost always means this source isn't in your subscription
            logger.warning(f"Dimensions patents unavailable (check subscription): {e}")
            return []
        results = []
        for p in data.get("patents", []):
            results.append({
                "id":          p.get("id"),
                "title":       p.get("title"),
                "filing_date": p.get("date_filed"),      # API field → frontend field
                "grant_date":  p.get("date_published"),  # API field → frontend field
                "assignees":   p.get("assignees", []),
            })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results

    # ── collaborating orgs ────────────────────────────────────────────────────

    def get_collaborating_orgs(self) -> list:
        cache_key = f"dimensions:collab_orgs:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = (
            f'search publications where research_orgs = "{GRID_ID}" '
            f'return research_orgs limit 50'
        )
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions collaborating orgs failed: {e}")
            return []
        results = []
        orgs = data.get("research_orgs") or {}
        items = orgs.get("data") if isinstance(orgs, dict) else orgs
        if isinstance(items, list):
            for org in items:
                if org.get("id") != GRID_ID:
                    results.append({
                        "name":  org.get("name", ""),
                        "id":    org.get("id", ""),
                        "count": org.get("count", 0),
                    })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results

    # ── citation sources (per-author) ─────────────────────────────────────────

    def get_author_citation_sources(self, author_id: str, dois: list) -> list:
        """
        For a list of DOIs belonging to one UM author, look them up in
        Dimensions and aggregate by source (journal/publisher) with OA status.

        Returns list of:
            {"source_name", "publisher", "citation_count", "is_oa", "oa_type"}
        sorted descending by citation_count.
        Never raises — always returns a list (empty on any failure).
        """
        if not dois:
            return []

        cache_key = f"dimensions:citation_sources:{author_id}"
        if self.cache:
            try:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached
            except Exception:
                pass

        agg: dict = {}
        OA_RANK = {"gold": 5, "diamond": 5, "green": 4,
                   "hybrid": 3, "bronze": 2, "closed": 1, "unknown": 0}

        # Clean DOIs — strip whitespace, remove any that look malformed
        clean_dois = []
        for d in dois:
            d = str(d).strip().replace("https://doi.org/", "")
            if d and len(d) > 3 and "/" in d:
                clean_dois.append(d)

        if not clean_dois:
            logger.warning(f"No valid DOIs for author {author_id}")
            return []

        BATCH = 5  # smaller batches are more reliable for DOI IN queries
        for i in range(0, len(clean_dois), BATCH):
            batch = clean_dois[i: i + BATCH]
            doi_clause = ", ".join(f'"{d}"' for d in batch)
            dsl = (
                f'search publications where doi in [{doi_clause}] '
                f'return publications[id+doi+journal+open_access+publisher] '
                f'limit 500'
            )
            try:
                logger.info(
                    f"citation_sources batch {i // BATCH + 1} "
                    f"({len(batch)} DOIs) for {author_id}"
                )
                data = self._query(dsl)
            except Exception as e:
                logger.warning(f"citation_sources batch {i // BATCH + 1} failed: {e}")
                continue

            if not isinstance(data, dict):
                continue

            for pub in data.get("publications", []):
                try:
                    journal = pub.get("journal") or {}
                    source_name = (
                        journal.get("title") if isinstance(journal, dict) else str(journal)
                    ) or pub.get("publisher") or "Unknown"

                    publisher = pub.get("publisher") or (
                        journal.get("publisher") if isinstance(journal, dict) else None
                    ) or ""

                    oa_info = pub.get("open_access") or {}
                    if isinstance(oa_info, str):
                        is_oa   = oa_info.lower() in ("true", "all oa", "gold", "green",
                                                       "hybrid", "bronze", "diamond")
                        oa_type = oa_info.lower() if is_oa else "closed"
                    else:
                        oa_type = (oa_info.get("type") or "unknown").lower()
                        is_oa   = oa_type not in ("closed", "unknown", "not_oa", "")

                    key = source_name.strip()
                    if not key:
                        continue

                    if key not in agg:
                        agg[key] = {
                            "source_name":    key,
                            "publisher":      publisher,
                            "citation_count": 0,
                            "is_oa":          is_oa,
                            "oa_type":        oa_type,
                        }
                    agg[key]["citation_count"] += 1

                    if OA_RANK.get(oa_type, 0) > OA_RANK.get(agg[key]["oa_type"], 0):
                        agg[key]["oa_type"] = oa_type
                        agg[key]["is_oa"]   = is_oa
                except Exception as e:
                    logger.debug(f"Skipping malformed pub record: {e}")
                    continue

        results = sorted(agg.values(), key=lambda x: -x["citation_count"])

        if self.cache:
            try:
                self.cache.set(cache_key, results, "dimensions", 604800)
            except Exception:
                pass

        return results

    def get_all_authors_citation_sources(
        self,
        authors: list,
        get_author_dois_fn,
    ) -> dict:
        """Batch version for seed.py. Returns {author_id: [source_rows]}."""
        result = {}
        for a in authors:
            aid = a["id"]
            cache_key = f"dimensions:citation_sources:{aid}"
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    result[aid] = cached
                    continue
            dois = get_author_dois_fn(aid)
            if not dois:
                result[aid] = []
                continue
            result[aid] = self.get_author_citation_sources(aid, dois)
            time.sleep(2)
        return result