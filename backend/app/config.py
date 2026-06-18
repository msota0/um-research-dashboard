"""Central configuration, loaded from environment / .env.

Every tunable lives here so moving from a laptop to the on-prem server is a
matter of editing `.env` — never code. Import `settings` anywhere you need a
value.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+psycopg://maheksota@localhost:5432/um_dashboard",
        alias="DATABASE_URL",
    )

    # ── Data sources ──────────────────────────────────────────────────────
    openalex_email: str = Field(default="you@olemiss.edu", alias="OPENALEX_EMAIL")
    dimensions_api_key: str = Field(default="", alias="DIMENSIONS_API_KEY")

    # ── Institution identity (Oxford campus only — NOT UMMC Jackson) ──────
    # Verified live against OpenAlex: UM Oxford = I368840534 / ror 02teq1165
    # (the old README's 02bdmhw89 / I145858726 now 404s). UMMC Jackson is the
    # separate I29606459 and is excluded.
    inst_openalex_id: str = Field(default="I368840534", alias="INST_OPENALEX_ID")
    inst_ror: str = Field(default="https://ror.org/02teq1165", alias="INST_ROR")
    inst_exclude_ids: str = Field(default="I29606459", alias="INST_EXCLUDE_IDS")
    dim_grid: str = Field(default="grid.251313.7", alias="DIM_GRID")

    # ── Year window ───────────────────────────────────────────────────────
    year_from: int = Field(default=2018, alias="YEAR_FROM")
    year_to: int = Field(default=2026, alias="YEAR_TO")

    # ── Ingestion controls ────────────────────────────────────────────────
    # 0/unset => no cap (full backfill, for the server). 50 => fast local dev.
    ingest_limit_authors: int = Field(default=0, alias="INGEST_LIMIT_AUTHORS")
    enable_scholarly: bool = Field(default=False, alias="ENABLE_SCHOLARLY")
    # ORCID public-API search to recover iDs OpenAlex/Dimensions didn't supply.
    # Official, ToS-clean API, so ON by default (unlike scraping-based scholarly).
    enable_orcid_search: bool = Field(default=True, alias="ENABLE_ORCID_SEARCH")

    # ── Serving ───────────────────────────────────────────────────────────
    frontend_origin: str = Field(
        default="http://localhost:3000", alias="FRONTEND_ORIGIN"
    )

    @property
    def ror_id(self) -> str:
        """Bare ROR id (no URL prefix), e.g. '02teq1165'."""
        return self.inst_ror.rstrip("/").split("/")[-1]

    @property
    def exclude_id_set(self) -> set[str]:
        """OpenAlex institution ids to exclude (e.g. UMMC Jackson)."""
        return {x.strip() for x in self.inst_exclude_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
