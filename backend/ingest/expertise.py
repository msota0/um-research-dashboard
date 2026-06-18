"""Aggregate an author's expertise keywords for the modal.

Derived entirely from the OpenAlex author entity we already batch-fetch
(``topics`` and ``x_concepts``) plus optional self-reported ORCID keywords —
no extra per-author work fetches. Weights mirror the old ``researcher.py``:
topics 3.0, concepts 2.0, ORCID keywords 2.0. Returns rows ready for the
``author_expertise`` table.
"""
from __future__ import annotations

_STOP = {
    "method", "methods", "result", "results", "study", "studies", "data",
    "analysis", "research", "approach", "model", "models", "system", "systems",
    "effect", "effects", "use", "using", "based", "new", "novel", "review",
}


def aggregate(author_entity: dict, orcid_keywords: list[str] | None = None) -> list[dict]:
    scores: dict[str, dict] = {}

    def add(keyword: str, weight: float, ktype: str) -> None:
        kw = (keyword or "").strip()
        if not kw or kw.lower() in _STOP:
            return
        key = kw.lower()
        row = scores.setdefault(
            key, {"keyword": kw, "total_score": 0.0, "sources": set(), "type": ktype}
        )
        row["total_score"] += weight
        row["sources"].add(ktype)
        # Prefer the most specific type label (topic > concept > self_reported).
        if ktype == "topic" or (ktype == "concept" and row["type"] == "self_reported"):
            row["type"] = ktype

    for t in author_entity.get("topics", []) or []:
        add(t.get("display_name", ""), 3.0, "topic")
    for c in author_entity.get("x_concepts", []) or []:
        # x_concepts carry a 0-100 score; weight by it lightly.
        add(c.get("display_name", ""), 2.0 * (c.get("score", 50) / 100.0), "concept")
    for kw in orcid_keywords or []:
        add(kw, 2.0, "self_reported")

    rows = [
        {
            "keyword": r["keyword"],
            "total_score": round(r["total_score"], 3),
            "sources": sorted(r["sources"]),
            "type": r["type"],
        }
        for r in scores.values()
    ]
    rows.sort(key=lambda r: r["total_score"], reverse=True)
    return rows[:50]
