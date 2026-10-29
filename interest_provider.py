"""Interest over time — cache-first, trendspyg auto/http, trendspy fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

InterestBackend = Literal["auto", "cache_only", "live"]

TRENDSPYG_DB_NAME = "trendspyg_explore.db"


def points_to_dataframe(points: list[dict], keyword: str):
    import pandas as pd

    if not points:
        return pd.DataFrame()
    idx = pd.to_datetime([p.get("date") for p in points], utc=True, errors="coerce")
    vals = [float(p.get("value") or 0) for p in points]
    return pd.DataFrame({keyword: vals}, index=idx)


def fetch_keyword_interest_trendspyg(
    keyword: str,
    *,
    geo: str,
    timeframe: str,
    cache_dir: Path,
    allow_live: bool,
) -> tuple[object | None, str]:
    """Returns (dataframe or None, error message)."""
    if not allow_live:
        return None, "cache_miss_throttled"

    from trendspyg.explore import download_google_trends_interest_over_time
    from trendspyg.exceptions import RateLimitError

    db_path = str(cache_dir / TRENDSPYG_DB_NAME)
    try:
        points = download_google_trends_interest_over_time(
            keyword.strip(),
            geo=geo,
            timeframe=timeframe,
            output_format="dict",
            cache="disk",
            cookies="disk",
            engine="auto",
            db_path=db_path,
            headless=True,
            max_retries=2,
            retry_wait=6.0,
        )
        if not isinstance(points, list):
            return None, "unexpected_trendspyg_response"
        df = points_to_dataframe(points, keyword)
        return (df if not df.empty else None), ""
    except RateLimitError as exc:
        return None, f"rate_limit:{exc}"
    except Exception as exc:
        err = str(exc)
        if "429" in err or "sorry/index" in err.lower():
            return None, "rate_limit"
        return None, err


def fetch_keyword_interest_trendspy(client, keyword: str, *, geo: str, timeframe: str):
    try:
        df = client.interest_over_time([keyword], timeframe=timeframe, geo=geo)
        if df is None or df.empty or keyword not in df.columns:
            return None, "empty"
        return df, ""
    except Exception as exc:
        err = str(exc)
        if "429" in err or "sorry/index" in err.lower():
            return None, "rate_limit"
        return None, err
