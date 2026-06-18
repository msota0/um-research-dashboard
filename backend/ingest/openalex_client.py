"""OpenAlex HTTP client: polite-pool, cursor pagination, batch fetch, backoff.

Sync on purpose — the ingestion pipeline is a checkpointed sequential job, and
sync code keeps resume logic and rate-limiting trivial to reason about. At the
polite-pool ceiling (~10 req/s) the whole institution backfill is well under an
hour, so concurrency buys little here and costs clarity.
"""
from __future__ import annotations

import time
from typing import Iterator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE = "https://api.openalex.org"
# OpenAlex allows up to 100 ids in an OR (`|`) filter; 50 is a safe, fast batch.
BATCH = 50


class RetryableHTTP(Exception):
    """Raised on 429/5xx so tenacity retries with backoff."""


class OpenAlexClient:
    def __init__(self, email: str, min_interval: float = 0.11):
        self.email = email
        self.min_interval = min_interval  # ~9 req/s, under the 10/s polite ceiling
        self._last = 0.0
        self._http = httpx.Client(
            timeout=60.0,
            headers={"User-Agent": f"UM-Research-Dashboard/2.0 (mailto:{email})"},
        )

    def close(self) -> None:
        self._http.close()

    # ── low-level GET with politeness + retry ────────────────────────────
    @retry(
        retry=retry_if_exception_type(RetryableHTTP),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, path: str, params: dict) -> dict:
        # simple client-side rate limit
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        params = {**params, "mailto": self.email}
        resp = self._http.get(f"{BASE}{path}", params=params)
        self._last = time.monotonic()
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableHTTP(f"{resp.status_code} on {path}")
        resp.raise_for_status()
        return resp.json()

    # ── institution resolution & verification ────────────────────────────
    def get_institution(self, openalex_id: str) -> dict:
        """Fetch an institution and assert it is the Oxford campus."""
        data = self._get(f"/institutions/{openalex_id}", {})
        geo = data.get("geo") or {}
        if (geo.get("city") or "").lower() != "oxford":
            raise ValueError(
                f"Institution {openalex_id} is '{data.get('display_name')}' in "
                f"{geo.get('city')} — refusing (expected Oxford)."
            )
        return data

    # ── bulk works (cursor pagination) ───────────────────────────────────
    def iter_works(
        self,
        institution_id: str,
        year_from: int,
        year_to: int,
        select: str | None = None,
        per_page: int = 200,
    ) -> Iterator[dict]:
        """Yield every UM work in [year_from, year_to] via cursor paging."""
        cursor = "*"
        flt = (
            f"authorships.institutions.id:{institution_id},"
            f"publication_year:{year_from}-{year_to}"
        )
        while cursor:
            params = {"filter": flt, "per-page": per_page, "cursor": cursor}
            if select:
                params["select"] = select
            data = self._get("/works", params)
            for w in data.get("results", []):
                yield w
            cursor = (data.get("meta") or {}).get("next_cursor")

    def works_group_by(
        self, institution_id: str, year_from: int, year_to: int, dimension: str
    ) -> list[dict]:
        """Return OpenAlex group_by buckets for an aggregation dimension."""
        flt = (
            f"authorships.institutions.id:{institution_id},"
            f"publication_year:{year_from}-{year_to}"
        )
        data = self._get("/works", {"filter": flt, "group_by": dimension})
        return data.get("group_by", [])

    # ── batch entity fetch by id (authors, referenced works) ─────────────
    def fetch_by_ids(
        self, entity: str, ids: list[str], select: str | None = None
    ) -> Iterator[dict]:
        """Fetch entities (`works`/`authors`) by OpenAlex id in OR-filter batches."""
        for i in range(0, len(ids), BATCH):
            chunk = [_bare_id(x) for x in ids[i : i + BATCH]]
            params = {
                "filter": "openalex_id:" + "|".join(chunk),
                "per-page": BATCH,
            }
            if select:
                params["select"] = select
            data = self._get(f"/{entity}", params)
            yield from data.get("results", [])


def _bare_id(openalex_id: str) -> str:
    """Normalize 'https://openalex.org/W123' -> 'W123'."""
    return openalex_id.rstrip("/").split("/")[-1]
