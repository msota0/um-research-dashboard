"""Dimensions Analytics (DSL) client: token auth + paged queries + backoff.

Used for department-wise data (parsed from author ``raw_affiliation``) and grant
totals. Mirrors the auth/backoff approach of the old ``backend/api/dimensions.py``
but is read-only and year-bounded.

Note: requires a valid ``DIMENSIONS_API_KEY``. The key leaked in the old repo
must be rotated first; until a valid key is set, the pipeline skips Dimensions
stages gracefully (departments/grants stay empty).
"""
from __future__ import annotations

import time
from typing import Iterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

AUTH_URL = "https://app.dimensions.ai/api/auth"
DSL_URL = "https://app.dimensions.ai/api/dsl"
PAGE = 1000  # DSL max limit per request


class RetryableDSL(Exception):
    pass


class DimensionsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._token: str | None = None
        self._token_at = 0.0
        self._http = httpx.Client(timeout=90.0)

    def close(self) -> None:
        self._http.close()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and "PUT_YOUR" not in self.api_key

    # ── auth ─────────────────────────────────────────────────────────────
    def _auth(self) -> str:
        # tokens last ~24h; refresh hourly to be safe
        if self._token and (time.monotonic() - self._token_at) < 3600:
            return self._token
        resp = self._http.post(AUTH_URL, json={"key": self.api_key})
        resp.raise_for_status()
        self._token = resp.json()["token"]
        self._token_at = time.monotonic()
        return self._token

    @retry(
        retry=retry_if_exception_type(RetryableDSL),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def query(self, dsl: str) -> dict:
        headers = {"Authorization": f"JWT {self._auth()}", "Content-Type": "text/plain"}
        resp = self._http.post(DSL_URL, data=dsl.encode("utf-8"), headers=headers)
        if resp.status_code == 401:  # token expired
            self._token = None
            raise RetryableDSL("401 — re-auth")
        if resp.status_code == 429:
            raise RetryableDSL("429 — rate limited")
        resp.raise_for_status()
        return resp.json()

    # ── paged record iteration ───────────────────────────────────────────
    def _iter(self, source: str, where: str, fields: str) -> Iterator[dict]:
        skip = 0
        while True:
            dsl = (
                f"search {source} where {where} "
                f"return {source}[{fields}] limit {PAGE} skip {skip}"
            )
            data = self.query(dsl)
            rows = data.get(source, [])
            yield from rows
            if len(rows) < PAGE:
                break
            skip += PAGE
            if skip >= 50000:  # DSL hard cap
                break

    def iter_publications(
        self, grid: str, year_from: int, year_to: int
    ) -> Iterator[dict]:
        """Publications with author + affiliation detail (for departments)."""
        where = f'research_orgs = "{grid}" and year in [{year_from}:{year_to}]'
        yield from self._iter(
            "publications", where, "id+doi+year+times_cited+authors"
        )

    def iter_grants(self, grid: str, year_from: int, year_to: int) -> Iterator[dict]:
        where = f'research_orgs = "{grid}" and active_year in [{year_from}:{year_to}]'
        yield from self._iter(
            "grants",
            where,
            "id+title+start_year+funding_usd+funder_org_name+investigators",
        )

    def iter_patents(self, grid: str, year_from: int, year_to: int) -> Iterator[dict]:
        """Patents with UM (``grid``) as an assignee."""
        where = f'assignees.id = "{grid}" and year in [{year_from}:{year_to}]'
        yield from self._iter(
            "patents",
            where,
            "id+title+year+times_cited+inventor_names+assignee_names+filing_status",
        )


def iter_raw_affiliations(publication: dict) -> Iterator[str]:
    """Yield every author raw-affiliation string from a DSL publication record.

    Defensive against DSL shape variation: ``authors[].affiliations[].raw_affiliation``
    may be a string or a list, and some records expose ``authors[].raw_affiliation``.
    """
    for author in publication.get("authors") or []:
        for aff in author.get("affiliations") or []:
            raw = aff.get("raw_affiliation")
            if isinstance(raw, list):
                yield from (r for r in raw if r)
            elif isinstance(raw, str) and raw:
                yield raw
        raw = author.get("raw_affiliation")
        if isinstance(raw, list):
            yield from (r for r in raw if r)
        elif isinstance(raw, str) and raw:
            yield raw
