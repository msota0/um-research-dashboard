"""Ingestion CLI.

    # Local dev (fast sample — caps authors/works):
    python -m backend.ingest.run backfill --limit-authors 50

    # Server (full backfill — leave the cap at 0 / unset):
    python -m backend.ingest.run backfill

    # Nightly refresh (only works updated since the last run):
    python -m backend.ingest.run incremental

If ``--limit-authors`` is omitted it falls back to ``INGEST_LIMIT_AUTHORS`` in
the environment (0 = full backfill).
"""
from __future__ import annotations

import argparse
import logging

from backend.app.config import settings
from backend.app.db import session_scope
from backend.ingest.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="UM dashboard ingestion")
    parser.add_argument("mode", choices=["backfill", "incremental"])
    parser.add_argument(
        "--limit-authors", type=int, default=None,
        help="Cap authors/works for local dev. Default: INGEST_LIMIT_AUTHORS env.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    limit = args.limit_authors if args.limit_authors is not None else settings.ingest_limit_authors

    with session_scope() as session:
        pipe = Pipeline(session, settings)
        try:
            if args.mode == "backfill":
                pipe.run(limit_authors=limit)
            else:
                # Incremental currently re-runs the (idempotent) pipeline; the
                # permanent venue cache means only new references are fetched.
                # A future optimization adds OpenAlex from_updated_date filtering.
                pipe.run(limit_authors=limit)
        finally:
            pipe.close()


if __name__ == "__main__":
    main()
