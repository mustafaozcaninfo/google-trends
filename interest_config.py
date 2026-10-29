"""Google Trends interest_over_time windows (trendspy / Explore date strings)."""

from __future__ import annotations

# Order: freshest first, 7-day last (long-tail context).
INTEREST_TIMEFRAME_CHOICES: list[tuple[str, str]] = [
    ("now 4-H", "Son 4 saat — en taze"),
    ("now 1-d", "Son 24 saat"),
    ("now 7-d", "Son 7 gün — uzun boyut"),
]

INTEREST_TIMEFRAME_IDS = [c[0] for c in INTEREST_TIMEFRAME_CHOICES]
DEFAULT_INTEREST_TIMEFRAME = "now 1-d"

INTEREST_BACKEND_CHOICES: list[tuple[str, str]] = [
    ("auto", "Otomatik — önbellek, sonra trendspyg (önerilen)"),
    ("cache_only", "Sadece önbellek — 429 yok, canlı çağrı yok"),
    ("live", "Canlı trendspy — riskli, test için"),
]

DEFAULT_INTEREST_BACKEND = "auto"


def interest_label(timeframe: str) -> str:
    for tid, label in INTEREST_TIMEFRAME_CHOICES:
        if tid == timeframe:
            return label
    return timeframe
