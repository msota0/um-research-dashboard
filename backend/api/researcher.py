"""
researcher.py — Expertise keyword aggregation from OpenAlex + ORCID.

Sources and weights:
  - OpenAlex author topics   (score × 3.0)  — most reliable, pre-computed by OA
  - OpenAlex author concepts (score × 2.0)  — broader subject areas
  - OpenAlex work keywords   (frequency)    — extracted from top 50 publications
  - ORCID profile keywords   (fixed 2.0)    — self-reported, high signal
"""

import time
import logging
from collections import defaultdict
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ORCID_BASE   = "https://pub.orcid.org/v3.0"
OA_BASE      = "https://api.openalex.org"

# Level-0 OpenAlex concepts are too broad ("Science", "Medicine") — skip them
_OA_SKIP_LEVEL = 0

# Words too generic to be useful as expertise keywords
_STOP = {
    'a','an','the','and','or','but','in','on','at','to','for','of','with','by',
    'from','as','is','was','are','were','be','been','have','has','had','do',
    'does','did','will','would','could','should','may','might','can','this',
    'that','these','those','it','its','we','our','their','study','effect',
    'effects','analysis','approach','method','methods','results','data','paper',
    'novel','case','use','high','low','large','small','new','based','using',
    'two','three','first','second','between','within','under','over','review',
    'introduction','conclusion','abstract',
}


class ResearcherProfiler:
    def __init__(self, email: str, cache_manager=None):
        self.email = email
        self.cache = cache_manager
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"UM-Research-Dashboard/1.0 (mailto:{email})",
            "Accept": "application/json",
        })

    # ── internal helpers ───────────────────────────────────────────────────────

    def _oa(self, path: str, params: dict = None) -> dict:
        p = {"mailto": self.email}
        if params:
            p.update(params)
        r = self.session.get(f"{OA_BASE}{path}", params=p, timeout=30)
        r.raise_for_status()
        time.sleep(0.5)
        return r.json()

    def _orcid(self, path: str) -> dict:
        r = self.session.get(f"{ORCID_BASE}/{path}", timeout=20)
        r.raise_for_status()
        return r.json()

    def _cached(self, key: str):
        return self.cache.get(key) if self.cache else None

    def _store(self, key: str, data, source: str, ttl: int = 86400 * 7):
        if self.cache:
            self.cache.set(key, data, source, ttl)

    # ── source 1: OpenAlex author topics + concepts ────────────────────────────

    def get_openalex_author_keywords(self, author_id: str) -> list:
        """Topics and concepts from the /authors/{id} endpoint."""
        cache_key = f"expertise:oa_author:{author_id}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._oa(f"/authors/{author_id}")
        except Exception as e:
            logger.warning(f"OA author fetch failed ({author_id}): {e}")
            return []

        out = []

        # topics — OpenAlex author topics use `count` (not `score`).
        # Normalise by the highest-count topic so scores are 0→1, then weight × 3.
        topics = data.get("topics", [])
        if topics:
            max_count = max(float(t.get("count") or 1) for t in topics)
            for t in topics:
                name = (t.get("display_name") or "").strip()
                # prefer explicit score (0-1) if available, otherwise normalise count
                raw_score = t.get("score")
                if raw_score is not None:
                    score = float(raw_score)
                else:
                    score = float(t.get("count") or 0) / max_count
                if name:
                    out.append({"keyword": name, "score": round(score * 3.0, 4),
                                "source": "openalex_topics", "type": "topic"})

        # x_concepts — scored 0→1 (no reliable `level` field in current API).
        # Keep all; broad level-0 concepts (e.g. "Computer Science") still useful.
        for c in data.get("x_concepts", []):
            name  = (c.get("display_name") or "").strip()
            score = float(c.get("score") or 0)
            if name:
                out.append({"keyword": name, "score": round(score * 2.0, 4),
                            "source": "openalex_concepts", "type": "concept"})

        if out:
            self._store(cache_key, out, "openalex")
        return out

    # ── source 2: keyword/topic frequency across publications ──────────────────

    def get_openalex_work_keywords(self, author_id: str) -> list:
        """
        Fetch author's top-cited works and aggregate keyword/topic frequency.
        Uses explicit work.keywords[] and work.topics[].
        """
        cache_key = f"expertise:oa_works:{author_id}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._oa("/works", {
                "filter": f"authorships.author.id:{author_id}",
                "sort": "cited_by_count:desc",
                "per-page": "50",
                "select": "id,title,keywords,topics",
            })
        except Exception as e:
            logger.warning(f"OA works fetch failed ({author_id}): {e}")
            return []

        freq: dict[str, float] = defaultdict(float)

        for work in data.get("results", []):
            # explicit keywords list
            for kw in work.get("keywords", []):
                name = (kw.get("display_name") if isinstance(kw, dict) else str(kw)).strip()
                if name and name.lower() not in _STOP:
                    freq[name] += 1.0

            # topic mentions weighted by score
            for topic in work.get("topics", []):
                name  = (topic.get("display_name") or "").strip()
                score = float(topic.get("score") or 0.5)
                if name:
                    freq[name] += score

        out = [
            {"keyword": k, "score": round(v, 4),
             "source": "openalex_works", "type": "extracted"}
            for k, v in freq.items() if v > 0.1
        ]
        out.sort(key=lambda x: -x["score"])

        self._store(cache_key, out, "openalex")
        return out

    # ── source 3: ORCID profile keywords ──────────────────────────────────────

    def get_orcid_keywords(self, orcid_id: str) -> list:
        """
        Self-reported keywords from ORCID public record.
        Tries /keywords endpoint and falls back to /person.
        No auth needed for public profiles.
        """
        if not orcid_id:
            return []

        orcid = orcid_id.replace("https://orcid.org/", "").strip().strip("/")
        if not orcid:
            return []

        cache_key = f"expertise:orcid:{orcid}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        seen: set[str] = set()
        out = []

        def _add(content: str):
            c = content.strip()
            if c and c.lower() not in seen:
                seen.add(c.lower())
                out.append({"keyword": c, "score": 2.0,
                            "source": "orcid", "type": "self_reported"})

        # /keywords
        try:
            data = self._orcid(f"{orcid}/keywords")
            for kw in data.get("keyword", []):
                _add(kw.get("content", ""))
        except Exception as e:
            logger.debug(f"ORCID /keywords failed ({orcid}): {e}")

        # /person (sometimes has extra keywords)
        try:
            person = self._orcid(f"{orcid}/person")
            for kw in (person.get("keywords") or {}).get("keyword", []):
                _add(kw.get("content", ""))
        except Exception as e:
            logger.debug(f"ORCID /person failed ({orcid}): {e}")

        self._store(cache_key, out, "orcid")
        return out

    # ── aggregation ────────────────────────────────────────────────────────────

    def aggregate_expertise(self, author_id: str,
                             orcid_id: Optional[str] = None,
                             force_refresh: bool = False) -> list:
        """
        Merge all sources, deduplicate (case-insensitive), rank by total score.
        Returns up to 50 keywords: [{keyword, total_score, sources, type}]
        """
        cache_key = f"expertise:aggregated:{author_id}"
        if not force_refresh:
            cached = self._cached(cache_key)
            if cached is not None:
                return cached

        all_kws = []
        all_kws.extend(self.get_openalex_author_keywords(author_id))
        all_kws.extend(self.get_openalex_work_keywords(author_id))
        if orcid_id:
            all_kws.extend(self.get_orcid_keywords(orcid_id))

        merged: dict[str, dict] = {}
        for kw in all_kws:
            key = kw["keyword"].lower().strip()
            if not key or len(key) < 3:
                continue
            if key in merged:
                merged[key]["total_score"] = round(
                    merged[key]["total_score"] + kw["score"], 4)
                if kw["source"] not in merged[key]["sources"]:
                    merged[key]["sources"].append(kw["source"])
                # prefer more specific type label
                if kw["type"] in ("topic", "self_reported"):
                    merged[key]["type"] = kw["type"]
            else:
                merged[key] = {
                    "keyword":     kw["keyword"],
                    "total_score": round(kw["score"], 4),
                    "sources":     [kw["source"]],
                    "type":        kw["type"],
                }

        result = sorted(merged.values(), key=lambda x: -x["total_score"])[:50]

        if result:
            self._store(cache_key, result, "both", 86400 * 7)
        return result
