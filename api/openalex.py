# import time
# import requests
# import logging
# from typing import Optional

# logger = logging.getLogger(__name__)

# OPENALEX_BASE = "https://api.openalex.org"
# ROR_ID = "https://ror.org/02bdmhw89"
# FALLBACK_ID = "I368840534"


# class OpenAlexClient:
#     def __init__(self, email: str, cache_manager=None):
#         self.email = email
#         self.cache = cache_manager
#         self.institution_id: Optional[str] = None
#         self.session = requests.Session()
#         self.session.headers.update({"User-Agent": f"UM-Research-Dashboard/1.0 (mailto:{email})"})

#     def _params(self, extra: dict = None) -> dict:
#         p = {"mailto": self.email}
#         if extra:
#             p.update(extra)
#         return p

#     def _get(self, path: str, params: dict = None, retries: int = 3) -> dict:
#         url = f"{OPENALEX_BASE}{path}"
#         p = self._params(params)
#         delay = 2
#         for attempt in range(retries):
#             try:
#                 resp = self.session.get(url, params=p, timeout=30)
#                 if resp.status_code == 429:
#                     time.sleep(delay)
#                     delay *= 2
#                     continue
#                 resp.raise_for_status()
#                 time.sleep(0.5)
#                 return resp.json()
#             except requests.RequestException as e:
#                 if attempt == retries - 1:
#                     raise
#                 time.sleep(delay)
#                 delay *= 2
#         return {}

#     def verify_institution(self) -> str:
#         """Verify UM Oxford institution ID via ROR. Returns OpenAlex ID."""
#         try:
#             data = self._get("/institutions", {"search": "university of mississippi"})
#             results = data.get("results", [])
#             for inst in results:
#                 geo = inst.get("geo", {})
#                 name = inst.get("display_name", "")
#                 # Match Oxford campus specifically — exclude Medical Center (Jackson)
#                 if geo.get("city") == "Oxford" and "Medical" not in name:
#                     oa_id = inst["id"].split("/")[-1]
#                     logger.info(f"Verified UM Oxford OpenAlex ID: {oa_id}")
#                     self.institution_id = oa_id
#                     return oa_id
#         except Exception as e:
#             logger.warning(f"Institution verification failed: {e}")
#         logger.warning(f"Falling back to hardcoded ID: {FALLBACK_ID}")
#         self.institution_id = FALLBACK_ID
#         return FALLBACK_ID

#     def get_institution_overview(self) -> dict:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:institution:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get(f"/institutions/{inst_id}")
#         result = {
#             "works_count": data.get("works_count", 0),
#             "cited_by_count": data.get("cited_by_count", 0),
#             "h_index": data.get("summary_stats", {}).get("h_index", 0),
#             "i10_index": data.get("summary_stats", {}).get("i10_index", 0),
#             "counts_by_year": data.get("counts_by_year", [])[:10],
#             "image_url": data.get("image_url"),
#             "display_name": data.get("display_name"),
#         }
#         if self.cache:
#             self.cache.set(cache_key, result, "openalex", 86400)
#         return result

#     def get_publications_by_year(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:pubs_by_year:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "publication_year",
#             "per-page": "200",
#         })
#         results = []
#         current_year = time.gmtime().tm_year
#         cutoff = current_year - 20
#         for item in data.get("group_by", []):
#             year = item.get("key")
#             try:
#                 year_int = int(year)
#             except (ValueError, TypeError):
#                 continue
#             if year_int >= cutoff:
#                 results.append({"year": year_int, "count": item.get("count", 0)})
#         results.sort(key=lambda x: x["year"])
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_publications_by_field(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:pubs_by_field:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "primary_topic.field.id",
#             "per-page": "200",
#         })
#         results = []
#         for item in data.get("group_by", []):
#             name = item.get("key_display_name") or item.get("key", "Unknown")
#             if name and name != "Unknown":
#                 results.append({"field_name": name, "count": item.get("count", 0)})
#         results.sort(key=lambda x: x["count"], reverse=True)
#         results = results[:20]
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_open_access_stats(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:oa_stats:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "open_access.oa_status",
#         })
#         results = []
#         for item in data.get("group_by", []):
#             results.append({
#                 "oa_status": item.get("key", "unknown"),
#                 "count": item.get("count", 0),
#             })
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 86400)
#         return results

#     def get_publications_by_type(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:pubs_by_type:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "type",
#         })
#         results = []
#         for item in data.get("group_by", []):
#             results.append({
#                 "type": item.get("key_display_name") or item.get("key", "unknown"),
#                 "count": item.get("count", 0),
#             })
#         results.sort(key=lambda x: x["count"], reverse=True)
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_publications_list(self, page: int = 1, per_page: int = 25,
#                                pub_type: str = "", year_from: str = "", year_to: str = "") -> dict:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:pubs_list:{inst_id}:{page}:{per_page}:{pub_type}:{year_from}:{year_to}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         filters = [f"institutions.id:{inst_id}"]
#         if pub_type:
#             filters.append(f"type:{pub_type}")
#         if year_from:
#             filters.append(f"publication_year:>{int(year_from)-1}")
#         if year_to:
#             filters.append(f"publication_year:<{int(year_to)+1}")
#         params = {
#             "filter": ",".join(filters),
#             "per-page": str(per_page),
#             "page": str(page),
#             "select": "id,title,doi,publication_year,type,open_access,primary_location",
#         }
#         data = self._get("/works", params)
#         items = []
#         for w in data.get("results", []):
#             oa = w.get("open_access", {})
#             items.append({
#                 "id": w.get("id", "").split("/")[-1],
#                 "title": w.get("title", ""),
#                 "doi": w.get("doi"),
#                 "year": w.get("publication_year"),
#                 "type": w.get("type", ""),
#                 "oa_status": oa.get("oa_status", "unknown"),
#                 "is_oa": oa.get("is_oa", False),
#             })
#         result = {
#             "items": items,
#             "total": data.get("meta", {}).get("count", 0),
#             "page": page,
#             "per_page": per_page,
#         }
#         if self.cache:
#             self.cache.set(cache_key, result, "openalex", 86400)
#         return result

#     def get_top_authors(self, page: int = 1, per_page: int = 25, search: str = "") -> dict:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:top_authors:{inst_id}:{page}:{per_page}:{search}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         params = {
#             "filter": f"last_known_institutions.id:{inst_id}",
#             "sort": "works_count:desc",
#             "per-page": str(per_page),
#             "page": str(page),
#         }
#         if search:
#             params["search"] = search
#         data = self._get("/authors", params)
#         results = []
#         for a in data.get("results", []):
#             results.append({
#                 "id": a.get("id", "").split("/")[-1],
#                 "name": a.get("display_name", ""),
#                 "works_count": a.get("works_count", 0),
#                 "cited_by_count": a.get("cited_by_count", 0),
#                 "h_index": a.get("summary_stats", {}).get("h_index", 0),
#                 "orcid": a.get("orcid"),
#             })
#         total = data.get("meta", {}).get("count", len(results))
#         result = {"items": results, "total": total, "page": page, "per_page": per_page}
#         if self.cache:
#             self.cache.set(cache_key, result, "openalex", 86400)
#         return result

#     def get_author_works(self, author_id: str) -> list:
#         cache_key = f"openalex:author_works:{author_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"authorships.author.id:{author_id}",
#             "sort": "cited_by_count:desc",
#             "per-page": "5",
#             "select": "id,title,doi,publication_year,cited_by_count",
#         })
#         results = []
#         for w in data.get("results", []):
#             results.append({
#                 "title": w.get("title", ""),
#                 "doi": w.get("doi"),
#                 "year": w.get("publication_year"),
#                 "citations": w.get("cited_by_count", 0),
#             })
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 86400)
#         return results

#     def get_top_journals(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:top_journals:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "primary_location.source.id",
#             "sort": "count:desc",
#             "per-page": "20",
#         })
#         results = []
#         for item in data.get("group_by", [])[:20]:
#             name = item.get("key_display_name") or item.get("key", "Unknown")
#             if name and name != "Unknown":
#                 results.append({"name": name, "count": item.get("count", 0)})
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_collaborating_institutions(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:collab_institutions:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "authorships.institutions.id",
#             "per-page": "50",
#         })
#         results = []
#         for item in data.get("group_by", []):
#             name = item.get("key_display_name") or item.get("key", "")
#             if not name or item.get("key", "") == inst_id:
#                 continue
#             results.append({
#                 "name": name,
#                 "count": item.get("count", 0),
#                 "country": item.get("key_display_name", ""),
#             })
#         results.sort(key=lambda x: x["count"], reverse=True)
#         results = results[:20]
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_collaborating_countries(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:collab_countries:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "authorships.institutions.country_code",
#             "per-page": "100",
#         })
#         results = []
#         for item in data.get("group_by", []):
#             code = item.get("key", "")
#             if code and code != "US":
#                 results.append({
#                     "country": item.get("key_display_name") or code,
#                     "country_code": code,
#                     "count": item.get("count", 0),
#                 })
#         results.sort(key=lambda x: x["count"], reverse=True)
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

#     def get_oa_trend_by_year(self) -> list:
#         inst_id = self.institution_id or FALLBACK_ID
#         cache_key = f"openalex:oa_trend:{inst_id}"
#         if self.cache:
#             cached = self.cache.get(cache_key)
#             if cached:
#                 return cached
#         current_year = time.gmtime().tm_year
#         cutoff = current_year - 10
#         oa_data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id},is_oa:true",
#             "group_by": "publication_year",
#             "per-page": "200",
#         })
#         total_data = self._get("/works", {
#             "filter": f"institutions.id:{inst_id}",
#             "group_by": "publication_year",
#             "per-page": "200",
#         })
#         oa_by_year = {}
#         for item in oa_data.get("group_by", []):
#             try:
#                 yr = int(item["key"])
#                 if yr >= cutoff:
#                     oa_by_year[yr] = item.get("count", 0)
#             except (ValueError, TypeError, KeyError):
#                 pass
#         results = []
#         for item in total_data.get("group_by", []):
#             try:
#                 yr = int(item["key"])
#             except (ValueError, TypeError, KeyError):
#                 continue
#             if yr < cutoff:
#                 continue
#             total = item.get("count", 0)
#             oa = oa_by_year.get(yr, 0)
#             pct = round(oa / total * 100, 1) if total > 0 else 0
#             results.append({"year": yr, "oa_count": oa, "total": total, "oa_percentage": pct})
#         results.sort(key=lambda x: x["year"])
#         if self.cache:
#             self.cache.set(cache_key, results, "openalex", 604800)
#         return results

import time
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
ROR_ID = "https://ror.org/02bdmhw89"
FALLBACK_ID = "I368840534"


class OpenAlexClient:
    def __init__(self, email: str, cache_manager=None):
        self.email = email
        self.cache = cache_manager
        self.institution_id: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"UM-Research-Dashboard/1.0 (mailto:{email})"})

    def _params(self, extra: dict = None) -> dict:
        p = {"mailto": self.email}
        if extra:
            p.update(extra)
        return p

    def _get(self, path: str, params: dict = None, retries: int = 3) -> dict:
        url = f"{OPENALEX_BASE}{path}"
        p = self._params(params)
        delay = 2
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=p, timeout=30)
                if resp.status_code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                time.sleep(0.5)
                return resp.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2
        return {}

    def verify_institution(self) -> str:
        """Verify UM Oxford institution ID via ROR. Returns OpenAlex ID."""
        try:
            data = self._get("/institutions", {"search": "university of mississippi"})
            results = data.get("results", [])
            for inst in results:
                geo = inst.get("geo", {})
                name = inst.get("display_name", "")
                # Match Oxford campus specifically — exclude Medical Center (Jackson)
                if geo.get("city") == "Oxford" and "Medical" not in name:
                    oa_id = inst["id"].split("/")[-1]
                    logger.info(f"Verified UM Oxford OpenAlex ID: {oa_id}")
                    self.institution_id = oa_id
                    return oa_id
        except Exception as e:
            logger.warning(f"Institution verification failed: {e}")
        logger.warning(f"Falling back to hardcoded ID: {FALLBACK_ID}")
        self.institution_id = FALLBACK_ID
        return FALLBACK_ID

    def get_institution_overview(self) -> dict:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:institution:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get(f"/institutions/{inst_id}")
        result = {
            "works_count": data.get("works_count", 0),
            "cited_by_count": data.get("cited_by_count", 0),
            "h_index": data.get("summary_stats", {}).get("h_index", 0),
            "i10_index": data.get("summary_stats", {}).get("i10_index", 0),
            "counts_by_year": data.get("counts_by_year", [])[:10],
            "image_url": data.get("image_url"),
            "display_name": data.get("display_name"),
        }
        if self.cache:
            self.cache.set(cache_key, result, "openalex", 86400)
        return result

    def get_publications_by_year(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:pubs_by_year:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "publication_year",
            "per-page": "200",
        })
        results = []
        current_year = time.gmtime().tm_year
        cutoff = current_year - 20
        for item in data.get("group_by", []):
            year = item.get("key")
            try:
                year_int = int(year)
            except (ValueError, TypeError):
                continue
            if year_int >= cutoff:
                results.append({"year": year_int, "count": item.get("count", 0)})
        results.sort(key=lambda x: x["year"])
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_publications_by_field(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:pubs_by_field:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "primary_topic.field.id",
            "per-page": "200",
        })
        results = []
        for item in data.get("group_by", []):
            name = item.get("key_display_name") or item.get("key", "Unknown")
            if name and name != "Unknown":
                results.append({"field_name": name, "count": item.get("count", 0)})
        results.sort(key=lambda x: x["count"], reverse=True)
        results = results[:20]
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_open_access_stats(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:oa_stats:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "open_access.oa_status",
        })
        results = []
        for item in data.get("group_by", []):
            results.append({
                "oa_status": item.get("key", "unknown"),
                "count": item.get("count", 0),
            })
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 86400)
        return results

    def get_publications_by_type(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:pubs_by_type:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "type",
        })
        results = []
        for item in data.get("group_by", []):
            results.append({
                "type": item.get("key_display_name") or item.get("key", "unknown"),
                "count": item.get("count", 0),
            })
        results.sort(key=lambda x: x["count"], reverse=True)
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_publications_list(self, page: int = 1, per_page: int = 25,
                               pub_type: str = "", year_from: str = "", year_to: str = "") -> dict:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:pubs_list:{inst_id}:{page}:{per_page}:{pub_type}:{year_from}:{year_to}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        filters = [f"institutions.id:{inst_id}"]
        if pub_type:
            filters.append(f"type:{pub_type}")
        if year_from:
            filters.append(f"publication_year:>{int(year_from)-1}")
        if year_to:
            filters.append(f"publication_year:<{int(year_to)+1}")
        params = {
            "filter": ",".join(filters),
            "per-page": str(per_page),
            "page": str(page),
            "select": "id,title,doi,publication_year,type,open_access,primary_location",
        }
        data = self._get("/works", params)
        items = []
        for w in data.get("results", []):
            oa = w.get("open_access", {})
            items.append({
                "id": w.get("id", "").split("/")[-1],
                "title": w.get("title", ""),
                "doi": w.get("doi"),
                "year": w.get("publication_year"),
                "type": w.get("type", ""),
                "oa_status": oa.get("oa_status", "unknown"),
                "is_oa": oa.get("is_oa", False),
            })
        result = {
            "items": items,
            "total": data.get("meta", {}).get("count", 0),
            "page": page,
            "per_page": per_page,
        }
        if self.cache:
            self.cache.set(cache_key, result, "openalex", 86400)
        return result

    def get_top_authors(self, page: int = 1, per_page: int = 25, search: str = "") -> dict:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:top_authors:{inst_id}:{page}:{per_page}:{search}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        params = {
            "filter": f"affiliations.institution.id:{inst_id}",
            "sort": "works_count:desc",
            "per-page": str(per_page),
            "page": str(page),
        }
        if search:
            params["search"] = search
        data = self._get("/authors", params)
        results = []
        for a in data.get("results", []):
            results.append({
                "id": a.get("id", "").split("/")[-1],
                "name": a.get("display_name", ""),
                "works_count": a.get("works_count", 0),
                "cited_by_count": a.get("cited_by_count", 0),
                "h_index": a.get("summary_stats", {}).get("h_index", 0),
                "orcid": a.get("orcid"),
            })
        total = data.get("meta", {}).get("count", len(results))
        result = {"items": results, "total": total, "page": page, "per_page": per_page}
        if self.cache:
            self.cache.set(cache_key, result, "openalex", 86400)
        return result

    def get_author_works(self, author_id: str) -> list:
        cache_key = f"openalex:author_works:{author_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"authorships.author.id:{author_id}",
            "sort": "cited_by_count:desc",
            "per-page": "5",
            "select": "id,title,doi,publication_year,cited_by_count",
        })
        results = []
        for w in data.get("results", []):
            results.append({
                "title": w.get("title", ""),
                "doi": w.get("doi"),
                "year": w.get("publication_year"),
                "citations": w.get("cited_by_count", 0),
            })
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 86400)
        return results

    def get_top_journals(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:top_journals:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "primary_location.source.id",
            "sort": "count:desc",
            "per-page": "20",
        })
        results = []
        for item in data.get("group_by", [])[:20]:
            name = item.get("key_display_name") or item.get("key", "Unknown")
            if name and name != "Unknown":
                results.append({"name": name, "count": item.get("count", 0)})
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_collaborating_institutions(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:collab_institutions:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "authorships.institutions.id",
            "per-page": "50",
        })
        results = []
        for item in data.get("group_by", []):
            name = item.get("key_display_name") or item.get("key", "")
            if not name or item.get("key", "") == inst_id:
                continue
            results.append({
                "name": name,
                "count": item.get("count", 0),
                "country": item.get("key_display_name", ""),
            })
        results.sort(key=lambda x: x["count"], reverse=True)
        results = results[:20]
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_collaborating_countries(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:collab_countries:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "authorships.institutions.country_code",
            "per-page": "100",
        })
        results = []
        for item in data.get("group_by", []):
            code = item.get("key", "")
            if code and code != "US":
                results.append({
                    "country": item.get("key_display_name") or code,
                    "country_code": code,
                    "count": item.get("count", 0),
                })
        results.sort(key=lambda x: x["count"], reverse=True)
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results

    def get_oa_trend_by_year(self) -> list:
        inst_id = self.institution_id or FALLBACK_ID
        cache_key = f"openalex:oa_trend:{inst_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        current_year = time.gmtime().tm_year
        cutoff = current_year - 10
        oa_data = self._get("/works", {
            "filter": f"institutions.id:{inst_id},is_oa:true",
            "group_by": "publication_year",
            "per-page": "200",
        })
        total_data = self._get("/works", {
            "filter": f"institutions.id:{inst_id}",
            "group_by": "publication_year",
            "per-page": "200",
        })
        oa_by_year = {}
        for item in oa_data.get("group_by", []):
            try:
                yr = int(item["key"])
                if yr >= cutoff:
                    oa_by_year[yr] = item.get("count", 0)
            except (ValueError, TypeError, KeyError):
                pass
        results = []
        for item in total_data.get("group_by", []):
            try:
                yr = int(item["key"])
            except (ValueError, TypeError, KeyError):
                continue
            if yr < cutoff:
                continue
            total = item.get("count", 0)
            oa = oa_by_year.get(yr, 0)
            pct = round(oa / total * 100, 1) if total > 0 else 0
            results.append({"year": yr, "oa_count": oa, "total": total, "oa_percentage": pct})
        results.sort(key=lambda x: x["year"])
        if self.cache:
            self.cache.set(cache_key, results, "openalex", 604800)
        return results
    
    def get_author_dois(self, author_id: str, max_works: int = 200) -> list:
        """
        Return a list of DOIs for all works by this author that have a DOI.
        Used to feed into Dimensions citation-source lookup.
        Fetches up to max_works publications sorted by citation count desc.
        Cache TTL: 7 days.
        """
        cache_key = f"openalex:author_all_dois:{author_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        dois = []
        per_page = 100
        pages = max(1, max_works // per_page)

        for page in range(1, pages + 1):
            try:
                data = self._get("/works", {
                    "filter": f"authorships.author.id:{author_id}",
                    "sort": "cited_by_count:desc",
                    "per-page": str(per_page),
                    "page": str(page),
                    "select": "id,doi",
                })
            except Exception as e:
                logger.warning(f"get_author_dois page {page} failed ({author_id}): {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for w in results:
                doi = w.get("doi")
                if doi:
                    doi = doi.replace("https://doi.org/", "").strip()
                    if doi:
                        dois.append(doi)

            if len(results) < per_page:
                break

        if self.cache and dois:
            self.cache.set(cache_key, dois, "openalex", 604800)

        return dois