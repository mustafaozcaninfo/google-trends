"""Short editorial brief from a scored opportunity row."""

from __future__ import annotations


def build_content_brief(row: dict) -> dict:
    q = (row.get("query") or "").strip()
    hint = row.get("headline_hint") or q.title()
    wc = int(row.get("word_count") or len(q.split()))
    bullets = [
        f"H1: {hint}",
        "Lead: US readers — dates, deadlines, and what changes this week.",
        "H2: Key dates (table or bullet timeline)",
        "H2: Who is affected / what to do",
        "H2: FAQ (People Also Ask style — 3–5 questions)",
    ]
    if row.get("trends_rising"):
        bullets.insert(2, "Hook: tie-in to rising Related query momentum.")
    if row.get("trends_volume_min", 0) >= 50_000:
        bullets.insert(1, "Note: high search volume — publish same day if possible.")
    return {
        "query": q,
        "headline": hint,
        "word_count_target": "900–1400" if wc >= 5 else "700–1100",
        "outline": bullets,
        "slug_hint": q.lower().replace("?", "").replace("'", ""),
    }
