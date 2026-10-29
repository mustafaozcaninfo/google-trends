"""Forward-looking search demand — dates after today, seasonal lift, trend momentum."""

from __future__ import annotations

import re
from datetime import date, datetime

from long_tail import words
from editor_pick import calendar_fit_score

# US-relevant anchors (Oct 2026 → next 12–18 months)
UPCOMING_EVENT_SEEDS = (
    "thanksgiving 2026",
    "black friday 2026",
    "cyber monday 2026",
    "christmas 2026",
    "new year 2027",
    "tax deadline 2027",
    "daylight saving time 2026",
    "medicare open enrollment 2026",
    "election day 2026",
    "sample ballot 2026",
    "school winter break 2026",
    "spring break 2027 schools",
    "ramadan 2027",
    "easter 2027",
    "super bowl 2027 date",
    "printable calendar 2027",
    "bank holidays 2027",
    "federal holidays 2027",
    "social security payment schedule 2026",
    "irs refund schedule 2026",
)

_FUTURE_YEAR = re.compile(r"\b(202[6-9]|203[0-2])\b")
_COUNTDOWN = re.compile(
    r"\b(how long until|how many days until|countdown|days until|weeks until|"
    r"when is|what date|what day|what time|schedule|deadline|last day|last date)\b",
    re.I,
)
_PAST_LEAK = re.compile(
    r"\b(yesterday|last night|box score|highlights|final score|vs\.|"
    r"2024|2023|2022|2021|2020)\b",
    re.I,
)
_SEASONAL_MONTHS = {
    10: ("halloween", "open enrollment", "medicare"),
    11: ("thanksgiving", "black friday", "cyber monday"),
    12: ("christmas", "holiday shipping", "new year"),
    1: ("new year", "tax", "mlk"),
    2: ("super bowl", "presidents day", "tax"),
    3: ("spring break", "daylight saving", "easter"),
    4: ("tax deadline", "easter"),
}


def future_demand_score(query: str, *, today: date | None = None) -> tuple[int, list[str]]:
    """0–100: likelihood query gains searches from today forward."""
    today = today or date.today()
    q = query.strip()
    ql = q.lower()
    pts = 0
    reasons: list[str] = []

    years = [int(y) for y in _FUTURE_YEAR.findall(q)]
    if years:
        max_y = max(years)
        if max_y >= today.year:
            pts += 25
            reasons.append(f"yıl {max_y}")
        if max_y > today.year:
            pts += 12
            reasons.append("gelecek yıl")
        if max_y >= today.year + 2:
            pts -= 40
            reasons.append("çok ileri yıl")

    if _COUNTDOWN.search(q):
        pts += 22
        reasons.append("when/until/deadline")

    if _PAST_LEAK.search(q):
        pts -= 35
        reasons.append("geçmiş/maç gürültüsü")

    fc = calendar_fit_score(q)
    pts += min(fc // 3, 18)
    if fc >= 45:
        reasons.append("FC fit")

    for m, tokens in _SEASONAL_MONTHS.items():
        diff = (m - today.month) % 12
        if diff <= 3 and any(t in ql for t in tokens):
            pts += 15
            reasons.append(f"sezon +{diff}ay")
            break

    if any(w in ql for w in ("printable", "pdf", "calendar", "schedule", "dates")):
        pts += 10
        reasons.append("planlama niyeti")

    pts = max(0, min(100, pts))
    return pts, reasons


def enrich_future_demand(rows: list[dict], *, today: date | None = None) -> list[dict]:
    """Attach future_demand to every row; sort with forward demand first."""
    today = today or date.today()
    out: list[dict] = []
    for row in rows:
        q = row.get("query") or ""
        fd, reasons = future_demand_score(q, today=today)
        out.append({**row, "future_demand": fd, "future_reasons": reasons})
    return sorted(
        out,
        key=lambda r: (-r.get("future_demand", 0), -r.get("site_boost", 0), -r.get("score", 0)),
    )


def default_forward_seeds(today: date | None = None) -> list[str]:
    today = today or date.today()
    seeds = list(UPCOMING_EVENT_SEEDS)
    # Month-aware prepend
    extra: list[str] = []
    for m, tokens in _SEASONAL_MONTHS.items():
        diff = (m - today.month) % 12
        if diff <= 2:
            for t in tokens[:2]:
                extra.append(f"{t} {today.year if m >= today.month else today.year + 1}")
    return list(dict.fromkeys([*extra, *seeds]))[:20]
