# University of Mississippi Research Dashboard (v2)

Research-analytics dashboard for the University of Mississippi **Oxford** campus,
sourced from [OpenAlex](https://openalex.org) (free) and
[Dimensions AI](https://www.dimensions.ai) (subscription / DSL API).

This is a ground-up rebuild of the original Flask + SQLite app:

| | Old | **v2** |
|---|---|---|
| Store | SQLite cache | **Postgres** (canonical, deduplicated) |
| Backend | Flask, live API calls per request | **FastAPI**, serves precomputed rows |
| Ingestion | per-author, serial (hours/days) | **bulk + batch + cached, resumable** (minutes–<1h) |
| Years | 2000–2026 | **2018–2026** |
| Data quality | raw (preprints/repos/datasets inflate counts) | **dedup pipeline** removes them |
| Authors | ranked by publications, full metrics in list | **random order, neutral fields only**; metrics in modal |
| Departments | — | **from Dimensions DSL** (`raw_affiliation` parsing) |
| Charts | duplicate representations | **one chart + one table per metric** |

## Architecture

```
frontend/            Next.js 14 + React + TypeScript (charts: Chart.js, d3-geo)
backend/
  app/               FastAPI — READ-ONLY queries against Postgres
    config.py        all settings from .env (DB, API keys, institution ids, years)
    models.py        SQLAlchemy schema (canonical works + precomputed aggregates)
    routers/         one module per tab area
  ingest/            the ETL pipeline (writes Postgres; never serves requests)
    openalex_client  bulk works, author batches, referenced-work venue resolution
    dimensions_client DSL auth + paged queries
    dedup.py         DOI/fuzzy dedup + repository/type exclusion rules
    departments.py   raw_affiliation -> UM-Oxford department parsing
    scholar.py       ORCID -> scholarly -> search-link (cached)
    pipeline.py      orchestration, checkpoints, idempotent upserts
    run.py           CLI: backfill | incremental
  alembic/           migrations
  tests/             dedup + department-parser tests
deploy/              systemd unit + timer templates
```

The API never calls OpenAlex/Dimensions at request time — the **ingestion
pipeline** precomputes everything into Postgres, so the dashboard is fast and
never rate-limited by a user click.

## Quick start — run with the shipped data (no data collection)

The repo ships a pre-collected snapshot of the database at
`seed/um_dashboard.sql.gz`, so you can run the dashboard **without ingesting
anything** — no Dimensions key, no OpenAlex calls, no backfill.

**You need:** Python 3.11+, Node 18+, Postgres 16
([Postgres.app](https://postgresapp.com) on macOS). **You do _not_ need** any API
keys.

```bash
# 1. Create the database and restore the shipped snapshot (schema + data).
#    No `alembic upgrade` needed — the dump already contains the schema.
createdb um_dashboard
gunzip -c seed/um_dashboard.sql.gz | psql um_dashboard

# 2. Point the app at your database.
#    Replace YOURUSER with your Postgres user (your macOS username on Postgres.app).
echo 'DATABASE_URL=postgresql+psycopg://YOURUSER@localhost:5432/um_dashboard' > .env

# 3. Backend (read-only API — never calls external services).
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 5000

# 4. Frontend (second terminal).
cd frontend && npm install && npm run dev      # http://localhost:3000
```

To refresh the snapshot later, re-run `pg_dump` and overwrite the seed file:
`pg_dump <DATABASE_URL> --no-owner --no-privileges | gzip > seed/um_dashboard.sql.gz`.

---

## Prerequisites (full setup — only if you want to re-collect the data yourself)

- Python 3.11+, Node 18+
- Postgres 16 (local: [Postgres.app](https://postgresapp.com))
- A **Dimensions DSL API key** for departments & grants (OpenAlex needs only an email).
  ⚠️ The key committed to the *old* public repo is compromised — **rotate it**.

## Local setup (re-collect from scratch)

```bash
# 1. Config
cp .env.example .env          # then edit: DATABASE_URL, OPENALEX_EMAIL, DIMENSIONS_API_KEY
                              # keep INGEST_LIMIT_AUTHORS=50 locally for fast runs

# 2. Python env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Database
createdb um_dashboard
alembic upgrade head

# 4. Ingest a 50-author sample (minutes)
python -m backend.ingest.run backfill --limit-authors 50

# 5. Run API + frontend (two terminals)
uvicorn backend.app.main:app --host 127.0.0.1 --port 5000
cd frontend && npm install && npm run dev      # http://localhost:3000
```

> **macOS note:** the AirPlay Receiver squats on `localhost:5000` over IPv6.
> The dev proxy therefore targets `127.0.0.1:5000` (see `frontend/next.config.mjs`).
> Either keep that, or disable AirPlay Receiver in System Settings → General → AirDrop & Handoff.

## Deploying to the on-prem server

Moving from laptop to server changes **`.env` only** — no code edits.

```bash
# On the server
git clone <repo> /opt/um-research-dashboard && cd /opt/um-research-dashboard
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # set the server DATABASE_URL, real keys,
                              # and INGEST_LIMIT_AUTHORS=0  (full backfill)
.venv/bin/alembic upgrade head

# Full backfill (runs unattended — laptop not required):
.venv/bin/python -m backend.ingest.run backfill        # or: systemctl start um-dashboard-ingest

# Services: API + nightly refresh
sudo cp deploy/*.service deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now um-dashboard-api
sudo systemctl enable --now um-dashboard-ingest.timer

cd frontend && npm install && npm run build && npm run start   # behind nginx
```

The backfill is **resumable**: every write is an idempotent upsert, and resolved
reference venues are cached permanently, so a killed run re-runs cheaply and
never double-counts.

## Institution identity

| | Value | Note |
|---|---|---|
| OpenAlex | `I368840534` | verified `geo.city == Oxford` at ingest |
| ROR | `02teq1165` | (old README's `02bdmhw89` / `I145858726` now 404s) |
| Dimensions GRID | `grid.251313.7` | |
| Excluded | `I29606459` | UMMC Jackson — different campus |

## Tests

```bash
pytest backend/tests        # dedup rules + department parser
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how the pieces fit and how to extend them.
