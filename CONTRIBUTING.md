# Contributing

The project is split into small, single-responsibility modules so changes stay
local and reviewable. Here's where things live and how to extend them.

## The three layers

1. **Ingestion** (`backend/ingest/`) — pulls from OpenAlex/Dimensions, applies
   quality rules, writes Postgres. The only layer that talks to external APIs.
2. **Schema** (`backend/app/models.py`) — the canonical, deduplicated store +
   precomputed aggregate tables.
3. **Serving** (`backend/app/routers/`) — read-only FastAPI endpoints. The
   frontend (`frontend/`) consumes them via the typed client `frontend/lib/api.ts`.

Data flows one way: **ingest → Postgres → API → frontend**. Endpoints never call
external APIs or aggregate on the fly; if a chart needs new data, add a stage
that precomputes it.

## Common changes

| I want to… | Edit |
|---|---|
| Change which work types/venues count | `backend/ingest/dedup.py` (`COUNTED_TYPES`, `EXCLUDED_TYPES`, `REPOSITORY_SOURCE_PATTERNS`) |
| Tune duplicate matching | `backend/ingest/dedup.py` (`fuzzy_duplicate` threshold) |
| Adjust department parsing/normalization | `backend/ingest/departments.py` |
| Change the year window or institution ids | `.env` (`YEAR_FROM/TO`, `INST_*`, `DIM_GRID`) |
| Add a new metric/table | add model in `models.py` → `alembic revision --autogenerate` → compute it in a `pipeline.py` stage → expose in a router → add to `api.ts` + a tab |
| Add/modify an endpoint | `backend/app/routers/*.py` (keep the `envelope()` response shape) |
| Add/modify a tab or chart | `frontend/app/components/tabs/*.tsx`, register in `page.tsx` + `Header.tsx` |

## Conventions

- **Secrets** live only in `.env` (gitignored). `.env.example` holds placeholders.
- **Migrations**: never hand-edit applied migrations; create a new one with
  `alembic revision --autogenerate -m "..."` and review it.
- **Idempotency**: ingestion writes are upserts keyed by stable ids. Keep it that
  way so re-runs/resumes never double-count.
- **Author privacy/neutrality**: the authors *list* endpoint and any author
  listing must expose only neutral fields (name, ORCID, Scholar, field). Keep
  competitive metrics (counts, citations, h-index) in the per-author *detail*
  endpoint / modal only.
- Run `pytest backend/tests` and `cd frontend && npx tsc --noEmit` before a PR.

## Notes / TODO

- `incremental` currently re-runs the full (idempotent, cache-accelerated)
  pipeline. A future optimization adds OpenAlex `from_updated_date` filtering to
  fetch only changed works.
- Google Scholar scraping (`scholar.py`, `ENABLE_SCHOLARLY`) is off by default and
  fragile; ORCID is the reliable source and the search link the guaranteed fallback.
