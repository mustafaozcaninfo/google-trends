"""Rank trending topics for Fresh Calendars News (calendar / civic / dates fit)."""

from __future__ import annotations

import re

from motors import MOTOR_ROOTS

_CALENDAR_RE = re.compile(
    r"\b("
    r"calendar|holiday|thanksgiving|halloween|christmas|easter|memorial|labor day|"
    r"daylight saving|time change|school|break|enrollment|deadline|schedule|date|dates|"
    r"when is|what day|election|vote|ballot|primary|tax|medicare|social security|"
    r"shipping|black friday|cyber monday|2026|2027|observed|federal|post office|usps"
    r")\b",
    re.I,
)

_LOW_FIT_RE = re.compile(
    r"\b(nba|nfl|vs |game|score|playoff|trade|album|lyrics|net worth|affair|cheating)\b",
    re.I,
)

_ROOT_WORDS = {w.lower() for words in MOTOR_ROOTS.values() for w in words}


def calendar_fit_score(keyword: str) -> int:
    """0–100 editorial fit for freshcalendars.com/news long-tail."""
    k = keyword.strip()
    if not k:
        return 0
    score = 0
    if _CALENDAR_RE.search(k):
        score += 45
    tokens = set(k.lower().split())
    if tokens & _ROOT_WORDS:
        score += 25
    if re.search(r"\b20(2[4-9]|3[0-9])\b", k):
        score += 12
    if _LOW_FIT_RE.search(k):
        score -= 35
    if len(k.split()) >= 4:
        score += 8
    return max(0, min(100, score))


def rank_trend_picks(trends: list[dict], *, limit: int = 8, min_fit: int = 20) -> list[dict]:
    """Trend rows enriched with ``calendar_fit`` for landing recommendations."""
    scored: list[dict] = []
    for t in trends:
        kw = (t.get("keyword") or "").strip()
        if not kw:
            continue
        fit = calendar_fit_score(kw)
        if fit < min_fit:
            continue
        row = dict(t)
        row["calendar_fit"] = fit
        vol = int(t.get("volume_min") or 0)
        row["pick_score"] = fit + min(vol // 10_000, 40)
        scored.append(row)
    scored.sort(key=lambda r: (-r["pick_score"], -int(r.get("volume_min") or 0)))
    return scored[:limit]
