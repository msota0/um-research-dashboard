import time
import requests
import logging
import sqlite3
import json
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
                    logger.error(
                        f"Dimensions 400 Bad Request.\n"
                        f"  DSL: {dsl[:300]}\n"
                        f"  Response: {resp.text[:400]}"
                    )
                    resp.raise_for_status()
                resp.raise_for_status()
                time.sleep(2)
                return resp.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 30)
        return {}

    # ── institution lookup ────────────────────────────────────────────────────

    def find_institution_id(self, name: str = "University of Mississippi") -> list:
        dsl = (
            f'search organizations where name = "{name}" '
            f'return organizations[id+name+city_name+country_name] limit 10'
        )
        try:
            return self._query(dsl).get("organizations", [])
        except Exception as e:
            logger.error(f"find_institution_id failed: {e}")
            return []

    # ── publications ──────────────────────────────────────────────────────────

    def get_publications_by_year(self) -> list:
        cache_key = f"dimensions:pubs_by_year:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f'search publications where research_orgs = "{GRID_ID}" return year'
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions pubs by year failed: {e}")
            return []
        results = []
        year_facet = data.get("year") or {}
        items = year_facet.get("data") if isinstance(year_facet, dict) else []
        for item in (items or []):
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
                "id":          pub.get("id"),
                "title":       pub.get("title"),
                "year":        pub.get("year"),
                "times_cited": pub.get("times_cited", 0),
                "open_access": pub.get("open_access"),
                "journal":     pub.get("journal", {}).get("title") if isinstance(pub.get("journal"), dict) else None,
                "doi":         pub.get("doi"),
                "type":        pub.get("type"),
            })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    # ── grants ────────────────────────────────────────────────────────────────

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

    # ── researchers ───────────────────────────────────────────────────────────

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

    # ── clinical trials ───────────────────────────────────────────────────────

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
            logger.warning(f"Dimensions clinical trials failed: {e}")
            return []
        results = []
        for t in data.get("clinical_trials", []):
            results.append({
                "id":         t.get("id"),
                "title":      t.get("title"),
                "status":     t.get("current_status"),
                "date":       t.get("date_inserted"),
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
            logger.warning(f"Dimensions patents failed: {e}")
            return []
        results = []
        for p in data.get("patents", []):
            results.append({
                "id":          p.get("id"),
                "title":       p.get("title"),
                "filing_date": p.get("date_filed"),
                "grant_date":  p.get("date_published"),
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
        orgs  = data.get("research_orgs") or {}
        items = orgs.get("data") if isinstance(orgs, dict) else orgs
        for org in (items or []):
            if org.get("id") != GRID_ID:
                results.append({
                    "name":  org.get("name", ""),
                    "id":    org.get("id", ""),
                    "count": org.get("count", 0),
                })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results

    # ── citation sources (outgoing: what this author cites) ───────────────────

    def get_author_citation_sources(self, author_id: str, dois: list) -> list:
        """
        OUTGOING CITATIONS: aggregate the journals/publishers that a UM Oxford
        author cites across all their publications.

        Flow:
          1. Fetch author's pubs with reference_ids (via researcher ID or DOI lookup)
          2. Collect all reference_ids → deduplicate
          3. Batch-fetch those referenced pubs → get journal + OA info
          4. Aggregate by source name → count + OA status

        open_access from Dimensions is a LIST e.g. ['oa_all', 'green'] or ['closed'].
        Bare DOIs confirmed working; https://doi.org/ prefix returns 0 results.

        Returns: [{"source_name", "publisher", "citation_count", "is_oa", "oa_type"}]
        Never raises.
        """
        cache_key = f"dimensions:citation_sources:{author_id}"
        if self.cache:
            try:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached
            except Exception:
                pass

        OA_RANK = {"gold": 5, "diamond": 5, "green": 4,
                   "hybrid": 3, "bronze": 2, "closed": 1, "unknown": 0}

        def _parse_oa(oa_field) -> tuple:
            if not oa_field:
                return False, "unknown"
            if isinstance(oa_field, str):
                oa_list = [oa_field.lower()]
            elif isinstance(oa_field, list):
                oa_list = [str(x).lower() for x in oa_field]
            else:
                return False, "unknown"
            specific = [x for x in oa_list if x not in ("oa_all", "oa_any")]
            if not specific:
                return True, "green"
            oa_type = specific[0]
            is_oa = oa_type not in ("closed", "not_oa", "unknown")
            return is_oa, oa_type

        def _absorb_into(agg: dict, publications: list):
            for pub in publications:
                try:
                    journal = pub.get("journal") or {}
                    source_name = (
                        journal.get("title") if isinstance(journal, dict) else str(journal)
                    ) or pub.get("publisher") or "Unknown"
                    publisher = pub.get("publisher") or (
                        journal.get("publisher") if isinstance(journal, dict) else None
                    ) or ""
                    is_oa, oa_type = _parse_oa(pub.get("open_access"))
                    key = source_name.strip()
                    if not key or key == "Unknown":
                        continue
                    if key not in agg:
                        agg[key] = {"source_name": key, "publisher": publisher,
                                    "citation_count": 0, "is_oa": is_oa, "oa_type": oa_type}
                    agg[key]["citation_count"] += 1
                    if OA_RANK.get(oa_type, 0) > OA_RANK.get(agg[key]["oa_type"], 0):
                        agg[key]["oa_type"] = oa_type
                        agg[key]["is_oa"]   = is_oa
                except Exception:
                    continue

        # ── Step 1: get author's pubs with reference_ids ──────────────────────
        author_pubs = []

        dim_researcher_id = self._find_dimensions_researcher_id(author_id)
        if dim_researcher_id:
            try:
                logger.info(f"Fetching pubs via researcher ID {dim_researcher_id}")
                dsl = (
                    f'search publications where researchers.id = "{dim_researcher_id}" '
                    f'return publications[id+doi+reference_ids] limit 1000'
                )
                data = self._query(dsl)
                author_pubs = data.get("publications", []) if isinstance(data, dict) else []
                logger.info(f"Researcher lookup: {len(author_pubs)} pubs")
            except Exception as e:
                logger.warning(f"Researcher ID lookup failed: {e}")

        if not author_pubs and dois:
            clean_dois = []
            for d in dois:
                bare = str(d).strip().replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                if bare and "/" in bare and len(bare) > 5:
                    clean_dois.append(bare)
            BATCH = 10
            for i in range(0, min(len(clean_dois), 200), BATCH):
                batch = clean_dois[i: i + BATCH]
                doi_clause = ", ".join(f'"{d}"' for d in batch)
                dsl = (
                    f'search publications where doi in [{doi_clause}] '
                    f'return publications[id+doi+reference_ids] limit 1000'
                )
                try:
                    data = self._query(dsl)
                    author_pubs.extend(data.get("publications", []) if isinstance(data, dict) else [])
                except Exception as e:
                    logger.warning(f"DOI batch {i // BATCH + 1} failed: {e}")

        if not author_pubs:
            logger.warning(f"No publications found for author {author_id}")
            return []

        # ── Step 2: collect all reference_ids ────────────────────────────────
        all_ref_ids = []
        for pub in author_pubs:
            all_ref_ids.extend(pub.get("reference_ids") or [])
        all_ref_ids = list(dict.fromkeys(all_ref_ids))
        logger.info(f"{len(author_pubs)} pubs → {len(all_ref_ids)} unique references for {author_id}")

        if not all_ref_ids:
            logger.warning(f"No reference_ids found for {author_id}")
            return []

        # ── Step 3: fetch the referenced pubs for journal/OA info ─────────────
        agg: dict = {}
        REF_BATCH = 50
        for i in range(0, len(all_ref_ids), REF_BATCH):
            batch = all_ref_ids[i: i + REF_BATCH]
            id_clause = ", ".join(f'"{r}"' for r in batch)
            dsl = (
                f'search publications where id in [{id_clause}] '
                f'return publications[id+journal+open_access+publisher] limit 1000'
            )
            try:
                logger.info(f"Refs batch {i // REF_BATCH + 1} ({len(batch)} refs)")
                data = self._query(dsl)
                _absorb_into(agg, data.get("publications", []) if isinstance(data, dict) else [])
            except Exception as e:
                logger.warning(f"Refs batch {i // REF_BATCH + 1} failed: {e}")

        results = sorted(agg.values(), key=lambda x: -x["citation_count"])
        logger.info(f"citation_sources for {author_id}: {len(results)} unique sources")

        if self.cache:
            try:
                self.cache.set(cache_key, results, "dimensions", 604800)
            except Exception:
                pass

        return results

    def _find_dimensions_researcher_id(self, openalex_author_id: str) -> str:
        """
        Match OpenAlex author → Dimensions researcher ID via ORCID.
        Looks through cached top_authors entries for the author's ORCID,
        then matches against the cached Dimensions researchers list.
        """
        if not self.cache:
            return ""
        try:
            conn = sqlite3.connect(self.cache.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT data FROM cache WHERE key LIKE 'openalex:top_authors:%' LIMIT 20"
            ).fetchall()
            conn.close()

            orcid = None
            for row in rows:
                try:
                    data = json.loads(row["data"])
                    items = data.get("items", []) if isinstance(data, dict) else []
                    for author in items:
                        if author.get("id") == openalex_author_id:
                            raw = author.get("orcid", "") or ""
                            orcid = raw.replace("https://orcid.org/", "").strip()
                            break
                    if orcid:
                        break
                except Exception:
                    continue

            if not orcid:
                return ""

            dim_researchers = self.cache.get(f"dimensions:researchers:{GRID_ID}") or []
            for r in dim_researchers:
                r_orcid = (r.get("orcid_id") or "").replace("https://orcid.org/", "").strip()
                if r_orcid and r_orcid == orcid:
                    logger.info(f"ORCID match {orcid} → {r.get('id')}")
                    return r.get("id", "")
        except Exception as e:
            logger.debug(f"_find_dimensions_researcher_id failed: {e}")
        return ""

    def get_all_authors_citation_sources(self, authors: list, get_author_dois_fn) -> dict:
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
            result[aid] = self.get_author_citation_sources(aid, dois)
            time.sleep(2)
        return result