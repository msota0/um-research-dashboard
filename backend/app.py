import os
import logging
import time
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from backend.api.cache import CacheManager
from backend.api.openalex import OpenAlexClient
from backend.api.dimensions import DimensionsClient
from backend.api.researcher import ResearcherProfiler

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── initialise services ──────────────────────────────────────────────────────
CACHE_DB = os.getenv("CACHE_DB_PATH", "cache.db")
cache = CacheManager(CACHE_DB)
cache.clear_expired()

openalex = OpenAlexClient(
    email=os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"),
    cache_manager=cache,
)
dimensions = DimensionsClient(
    api_key=os.getenv("DIMENSIONS_API_KEY", ""),
    cache_manager=cache,
)
researcher = ResearcherProfiler(
    email=os.getenv("OPENALEX_EMAIL", "research@olemiss.edu"),
    cache_manager=cache,
)

# Verify institution at startup
INSTITUTION_ID = openalex.verify_institution()
logger.info(f"Using OpenAlex institution ID: {INSTITUTION_ID}")


# ── helpers ──────────────────────────────────────────────────────────────────
def _resp(data, source: str, cached: bool = False):
    return jsonify({
        "data": data,
        "source": source,
        "cached": cached,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "institution_id": INSTITUTION_ID,
    })


def _refresh_requested():
    return request.args.get("refresh", "0") == "1"


def _maybe_invalidate(key: str):
    if _refresh_requested():
        cache.invalidate(key)


# ── routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/institution/overview")
def institution_overview():
    key = f"openalex:institution:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_institution_overview()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"institution_overview error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/publications/by-year")
def pubs_by_year():
    year_from = request.args.get("year_from")
    year_to = request.args.get("year_to")
    key_oa = f"openalex:pubs_by_year:{INSTITUTION_ID}"
    _maybe_invalidate(key_oa)
    source_error = None
    oa_data = []
    dim_data = []
    try:
        oa_data = openalex.get_publications_by_year()
    except Exception as e:
        logger.error(f"OpenAlex pubs_by_year error: {e}")
        source_error = "openalex"
    try:
        dim_data = dimensions.get_publications_by_year()
    except Exception as e:
        logger.error(f"Dimensions pubs_by_year error: {e}")
    if year_from:
        oa_data = [x for x in oa_data if x["year"] >= int(year_from)]
        dim_data = [x for x in dim_data if int(x["year"]) >= int(year_from)]

    if year_to:
        oa_data = [x for x in oa_data if x["year"] <= int(year_to)]
        dim_data = [x for x in dim_data if int(x["year"]) <= int(year_to)]
    result = {"openalex": oa_data, "dimensions": dim_data}
    if source_error:
        result["source_error"] = source_error
    return _resp(result, "both")


@app.route("/api/publications/by-field")
def pubs_by_field():
    key = f"openalex:pubs_by_field:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_publications_by_field()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"pubs_by_field error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/publications/open-access")
def pubs_open_access():
    key = f"openalex:oa_stats:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_open_access_stats()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"pubs_open_access error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/publications/by-type")
def pubs_by_type():
    key = f"openalex:pubs_by_type:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_publications_by_type()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"pubs_by_type error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/publications/list")
def pubs_list():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    pub_type = request.args.get("type", "")
    year_from = request.args.get("year_from", "")
    year_to = request.args.get("year_to", "")
    try:
        data = openalex.get_publications_list(page, per_page, pub_type, year_from, year_to)
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"pubs_list error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/authors/top")
def authors_top():
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    search   = request.args.get("search", "")
    key = f"openalex:top_authors_full:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_top_authors(page=page, per_page=per_page, search=search)
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"authors_top error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/authors/<author_id>/works")
def author_works(author_id):
    try:
        data = openalex.get_author_works(author_id)
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"author_works error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/authors/<author_id>/expertise")
def author_expertise(author_id):
    orcid = request.args.get("orcid", "")
    _maybe_invalidate(f"expertise:aggregated:{author_id}")
    try:
        data = researcher.aggregate_expertise(
            author_id,
            orcid_id=orcid or None,
            force_refresh=_refresh_requested(),
        )
        return _resp(data, "both")
    except Exception as e:
        logger.error(f"author_expertise error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/journals/top")
def journals_top():
    key = f"openalex:top_journals:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_top_journals()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"journals_top error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/collaborations/institutions")
def collab_institutions():
    key = f"openalex:collab_institutions:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_collaborating_institutions()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"collab_institutions error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/collaborations/countries")
def collab_countries():
    key = f"openalex:collab_countries:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_collaborating_countries()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"collab_countries error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500


@app.route("/api/grants/summary")
def grants_summary():
    _maybe_invalidate(f"dimensions:grants:grid.266226.6")
    try:
        grants = dimensions.get_grants()
        total_funding = sum(g.get("funding_usd") or 0 for g in grants)
        by_funder: dict = {}
        by_year: dict = {}
        for g in grants:
            funder = g.get("funder_org_name") or "Unknown"
            by_funder[funder] = by_funder.get(funder, {"count": 0, "total_usd": 0})
            by_funder[funder]["count"] += 1
            by_funder[funder]["total_usd"] += g.get("funding_usd") or 0
            yr = (g.get("start_date") or "")[:4]
            if yr.isdigit():
                by_year[yr] = by_year.get(yr, {"count": 0, "total_usd": 0})
                by_year[yr]["count"] += 1
                by_year[yr]["total_usd"] += g.get("funding_usd") or 0
        funder_list = [{"name": k, **v} for k, v in by_funder.items()]
        funder_list.sort(key=lambda x: x["total_usd"], reverse=True)
        data = {
            "total_grants": len(grants),
            "total_funding_usd": total_funding,
            "by_funder": funder_list[:10],
        }
        return _resp(data, "dimensions")
    except Exception as e:
        logger.error(f"grants_summary error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/grants/list")
def grants_list():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    try:
        grants = dimensions.get_grants()
        total = len(grants)
        start = (page - 1) * per_page
        items = grants[start: start + per_page]
        return _resp({"items": items, "total": total, "page": page, "per_page": per_page}, "dimensions")
    except Exception as e:
        logger.error(f"grants_list error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/grants/by-year")
def grants_by_year():
    try:
        grants = dimensions.get_grants()
        by_year: dict = {}
        for g in grants:
            yr = (g.get("start_date") or "")[:4]
            if yr.isdigit():
                rec = by_year.setdefault(yr, {"year": yr, "count": 0, "total_usd": 0})
                rec["count"] += 1
                rec["total_usd"] += g.get("funding_usd") or 0
        results = sorted(by_year.values(), key=lambda x: x["year"])
        return _resp(results, "dimensions")
    except Exception as e:
        logger.error(f"grants_by_year error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/trials/summary")
def trials_summary():
    _maybe_invalidate(f"dimensions:clinical_trials:grid.266226.6")
    try:
        trials = dimensions.get_clinical_trials()
        active = sum(1 for t in trials if (t.get("status") or "").lower() in ("active", "recruiting", "enrolling"))
        completed = sum(1 for t in trials if (t.get("status") or "").lower() == "completed")
        recruiting = sum(1 for t in trials if (t.get("status") or "").lower() == "recruiting")
        phases: dict = {}
        for t in trials:
            ph = t.get("phase") or "N/A"
            phases[ph] = phases.get(ph, 0) + 1
        phase_list = [{"phase": k, "count": v} for k, v in phases.items()]
        data = {
            "total": len(trials),
            "active_count": active,
            "completed_count": completed,
            "recruiting_count": recruiting,
            "by_phase": phase_list,
        }
        return _resp(data, "dimensions")
    except Exception as e:
        logger.error(f"trials_summary error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/trials/list")
def trials_list():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    search = request.args.get("search", "").lower()
    try:
        trials = dimensions.get_clinical_trials()
        if search:
            trials = [t for t in trials if search in (t.get("title") or "").lower()]
        total = len(trials)
        start = (page - 1) * per_page
        items = trials[start: start + per_page]
        return _resp({"items": items, "total": total, "page": page, "per_page": per_page}, "dimensions")
    except Exception as e:
        logger.error(f"trials_list error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/patents/by-year")
def patents_by_year():
    _maybe_invalidate(f"dimensions:patents:grid.266226.6")
    try:
        patents = dimensions.get_patents()
        by_year: dict = {}
        for p in patents:
            yr = (p.get("filing_date") or "")[:4]
            if yr.isdigit():
                by_year[yr] = by_year.get(yr, 0) + 1
        results = [{"year": k, "count": v} for k, v in sorted(by_year.items())]
        return _resp(results, "dimensions")
    except Exception as e:
        logger.error(f"patents_by_year error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/patents/list")
def patents_list():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    try:
        patents = dimensions.get_patents()
        total = len(patents)
        start = (page - 1) * per_page
        items = patents[start: start + per_page]
        return _resp({"items": items, "total": total, "page": page, "per_page": per_page}, "dimensions")
    except Exception as e:
        logger.error(f"patents_list error: {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


@app.route("/api/open-access/trend")
def oa_trend():
    key = f"openalex:oa_trend:{INSTITUTION_ID}"
    _maybe_invalidate(key)
    try:
        data = openalex.get_oa_trend_by_year()
        return _resp(data, "openalex")
    except Exception as e:
        logger.error(f"oa_trend error: {e}")
        return jsonify({"error": str(e), "source_error": "openalex"}), 500
    

# ── ADD THIS ROUTE TO app.py ──────────────────────────────────────────────────
# Place it alongside the other @app.route("/api/authors/...") routes.
# It calls a new method on the DimensionsClient: get_author_citation_sources()

@app.route("/api/authors/<author_id>/citation-sources")
def author_citation_sources(author_id: str):
    """
    For a single UM Oxford author (identified by their OpenAlex author_id),
    fetch all their publications via Dimensions, then aggregate the sources
    (journals/publishers) that those publications were cited by — i.e. which
    outlets cite this author's work, and how many times, and whether that
    outlet is open-access.

    Flow:
      1. Resolve author's DOIs from OpenAlex (already cached by get_author_works)
      2. For each DOI, query Dimensions for the citing publications' source info
      3. Aggregate by source name → {count, is_oa, publisher}
      4. Return sorted list of sources with citation counts

    Cache key: dimensions:citation_sources:{author_id}
    TTL: 7 days (604800 seconds) — this is expensive to compute
    """
    _maybe_invalidate(f"dimensions:citation_sources:{author_id}")
    try:
        # Step 1: get author's DOIs from OpenAlex (use a wider fetch than the
        # modal's top-5; we want all works that have DOIs for Dimensions lookup)
        oa_key = f"openalex:author_all_dois:{author_id}"
        dois = cache.get(oa_key)
        if not dois:
            dois = openalex.get_author_dois(author_id)          # new OA method
            cache.set(oa_key, dois, "openalex", 604800)

        if not dois:
            return _resp([], "dimensions")

        # Step 2 + 3: Dimensions aggregation
        data = dimensions.get_author_citation_sources(author_id, dois)
        return _resp(data, "dimensions")
    except Exception as e:
        logger.error(f"author_citation_sources error ({author_id}): {e}")
        return jsonify({"error": str(e), "source_error": "dimensions"}), 500


# ── ADD THIS ROUTE TO app.py ──────────────────────────────────────────────────
# Batch endpoint: called once when the CitationSources tab first mounts.
# Returns citation-source data for ALL UM authors in one go (from cache).
# The frontend calls this first; if an author is missing it falls back to
# the per-author endpoint above.

@app.route("/api/citation-sources/all")
def citation_sources_all():
    """
    Returns pre-computed citation-source profiles for all UM Oxford authors.
    This is populated by seed.py. If not yet seeded, returns empty dict and
    the frontend falls back to loading authors one at a time.
    """
    cache_key = f"dimensions:citation_sources_all:{INSTITUTION_ID}"
    _maybe_invalidate(cache_key)
    cached = cache.get(cache_key)
    if cached:
        return _resp(cached, "dimensions", cached=True)
    # Not seeded yet — return empty so frontend degrades gracefully
    return _resp({}, "dimensions", cached=False)


@app.route("/api/cache-status")
def cache_status():
    return jsonify(cache.status())


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") != "production")