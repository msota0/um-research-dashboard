import time
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DIMENSIONS_AUTH_URL = "https://app.dimensions.ai/api/auth"
DIMENSIONS_DSL_URL = "https://app.dimensions.ai/api/dsl/v2"
GRID_ID = "grid.266226.6"
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
                    data=dsl,
                    headers={
                        "Authorization": f"JWT {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
                if resp.status_code == 429:
                    logger.warning(f"Dimensions rate limited, waiting {delay}s")
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                if resp.status_code == 401:
                    self._authenticate()
                    continue
                resp.raise_for_status()
                time.sleep(2)
                return resp.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 30)
        return {}

    def get_publications_by_year(self) -> list:
        cache_key = f"dimensions:pubs_by_year:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search publications where research_orgs = "{GRID_ID}"
return year"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions pubs by year failed: {e}")
            return []
        results = []
        for item in data.get("year", {}).get("data", []):
            results.append({"year": item.get("id"), "count": item.get("count", 0)})
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
        dsl = f"""search publications where research_orgs = "{GRID_ID}"
return publications[id+title+year+times_cited+open_access+journal+doi+type]
limit 1000"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions publications failed: {e}")
            return []
        results = []
        for pub in data.get("publications", []):
            results.append({
                "id": pub.get("id"),
                "title": pub.get("title"),
                "year": pub.get("year"),
                "times_cited": pub.get("times_cited", 0),
                "open_access": pub.get("open_access"),
                "journal": pub.get("journal", {}).get("title") if pub.get("journal") else None,
                "doi": pub.get("doi"),
                "type": pub.get("type"),
            })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    def get_grants(self) -> list:
        cache_key = f"dimensions:grants:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search grants where research_orgs = "{GRID_ID}"
return grants[id+title+start_date+end_date+funding_usd+funder_org_name+category_for]
limit 1000"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions grants failed: {e}")
            return []
        results = data.get("grants", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    def get_researchers(self) -> list:
        cache_key = f"dimensions:researchers:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search publications where research_orgs = "{GRID_ID}"
return researchers[id+first_name+last_name+orcid_id+total_grants+research_orgs]
limit 25"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions researchers failed: {e}")
            return []
        results = data.get("researchers", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    def get_clinical_trials(self) -> list:
        cache_key = f"dimensions:clinical_trials:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search clinical_trials where research_orgs = "{GRID_ID}"
return clinical_trials[id+title+status+date+phase+conditions]
limit 1000"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions clinical trials failed: {e}")
            return []
        results = data.get("clinical_trials", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 86400)
        return results

    def get_patents(self) -> list:
        cache_key = f"dimensions:patents:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search patents where assignees = "{GRID_ID}"
return patents[id+title+filing_date+grant_date+assignees]
limit 1000"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions patents failed: {e}")
            return []
        results = data.get("patents", [])
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results

    def get_collaborating_orgs(self) -> list:
        cache_key = f"dimensions:collab_orgs:{GRID_ID}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        dsl = f"""search publications where research_orgs = "{GRID_ID}"
return research_orgs
limit 50"""
        try:
            data = self._query(dsl)
        except Exception as e:
            logger.error(f"Dimensions collaborating orgs failed: {e}")
            return []
        results = []
        for org in data.get("research_orgs", {}).get("data", []):
            if org.get("id") != GRID_ID:
                results.append({
                    "name": org.get("name", ""),
                    "id": org.get("id", ""),
                    "count": org.get("count", 0),
                })
        if self.cache:
            self.cache.set(cache_key, results, "dimensions", 604800)
        return results
