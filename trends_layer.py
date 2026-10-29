"""Google Trends API layer (trendspy + trendspyg RSS) for the radar pipeline."""

from __future__ import annotations

def fetch_trending_list(get_trending_rss, geo: str) -> list[dict]:
    data = get_trending_rss(geo)
    return data.get("trends", []) if isinstance(data, dict) else (data or [])


def fetch_trending_bundle(trending_service, geo: str, **kwargs) -> dict:
    """Backward-compatible alias — prefer ``trending_service.fetch_trending_bundle``."""
    from trending_service import fetch_trending_bundle as _bundle

    return _bundle(trending_service, geo, **kwargs)


def series_to_points(df, keyword: str) -> list[dict]:
    if df is None or df.empty or keyword not in df.columns:
        return []
    points = []
    for ts, val in df[keyword].dropna().items():
        points.append({"t": str(ts), "v": float(val)})
    return points


def _dataframe_to_cache(df) -> dict:
    import pandas as pd

    if df is None or df.empty:
        return {"columns": [], "index": [], "data": []}
    cols = [c for c in df.columns if c != "isPartial"]
    return {
        "columns": cols,
        "index": [str(i) for i in df.index],
        "data": {
            c: [None if pd.isna(v) else float(v) for v in df[c].tolist()]
            for c in cols
        },
    }


def _cache_to_dataframe(payload: dict):
    import pandas as pd

    cols = payload.get("columns") or []
    if not cols:
        return pd.DataFrame()
    data = payload.get("data") or {}
    idx = pd.to_datetime(payload.get("index") or [])
    return pd.DataFrame({c: data.get(c, []) for c in cols}, index=idx)


def fetch_interest_map(
    get_trendspy,
    queries: list[str],
    geo: str,
    timeframe: str = "now 1-d",
    *,
    include_series: bool = False,
    cache: "InterestCache | None" = None,
    cache_dir: Path | None = None,
    max_keywords: int = 3,
    interest_backend: str = "auto",
    gate: "InterestGate | None" = None,
) -> tuple[dict, dict[str, list[dict]], str]:
    """
    Cache-first interest. Live calls: trendspyg (disk cache + auto/http), trendspy last.
    ``cache_only`` never hits Google — serves SQLite / trendspyg disk hits only.
    """
    from pathlib import Path as _Path

    from interest_gate import InterestGate
    from interest_provider import fetch_keyword_interest_trendspy, fetch_keyword_interest_trendspyg
    from signals import TrendInterestSnapshot, interest_momentum

    out: dict[str, TrendInterestSnapshot] = {}
    series: dict[str, list[dict]] = {}
    errors: list[str] = []
    backend = (interest_backend or "auto").strip().lower()
    if backend not in ("auto", "cache_only", "live"):
        backend = "auto"

    unique = list(dict.fromkeys(q.strip() for q in queries if q.strip()))[: max(1, max_keywords)]
    cdir = cache_dir or _Path(".cache")
    live_budget = 0 if backend == "cache_only" else 1
    client = get_trendspy() if backend in ("auto", "live") else None

    for kw in unique:
        batch = [kw]
        df = None
        if cache is not None:
            hit = cache.get(geo, timeframe, batch)
            if hit:
                df = _cache_to_dataframe(hit)

        if df is None and backend != "cache_only":
            allow_live = gate.allow_live() if gate else True
            if live_budget > 0 and allow_live:
                df, err = fetch_keyword_interest_trendspyg(
                    kw, geo=geo, timeframe=timeframe, cache_dir=cdir, allow_live=True,
                )
                if err == "cache_miss_throttled":
                    errors.append(f"throttle:{kw}")
                elif err.startswith("rate_limit"):
                    errors.append("429_trendspyg")
                elif err:
                    errors.append(err)
                if df is not None:
                    live_budget -= 1
                    if gate:
                        gate.mark_live()
                    if cache is not None:
                        cache.set(geo, timeframe, batch, _dataframe_to_cache(df))

            if df is None and backend == "live" and client is not None and (gate.allow_live() if gate else True):
                df, err = fetch_keyword_interest_trendspy(client, kw, geo=geo, timeframe=timeframe)
                if err == "rate_limit":
                    errors.append("429_trendspy")
                elif err and err not in ("empty",):
                    errors.append(err)
                if df is not None:
                    if gate:
                        gate.mark_live()
                    if cache is not None:
                        cache.set(geo, timeframe, batch, _dataframe_to_cache(df))

        if df is None:
            continue
        key = " ".join(kw.lower().split())
        snap = interest_momentum(df, kw)
        if snap:
            out[key] = snap
        if include_series:
            pts = series_to_points(df, kw)
            if pts:
                series[key] = pts

    error = ""
    if not out and errors:
        if any("429" in e for e in errors):
            wait = gate.seconds_until_allowed() if gate else 55
            error = (
                f"Google interest geçici kapalı (429). Önbellekte veri yok. "
                f"~{wait}s sonra tekrar dene veya Interest modunu 'Sadece önbellek' yapın — "
                f"trending hacim skoru yine çalışır."
            )
        elif any(e.startswith("throttle") for e in errors):
            wait = gate.seconds_until_allowed() if gate else 55
            error = f"Canlı interest aralığı: ~{wait}s sonra (aynı seed önbellekten gelebilir)."
        else:
            error = "; ".join(errors[:2])

    return out, series, error


def load_related_cache(related_service, seeds: list[str], extra_queries: list[str], geo: str, timeframe: str) -> list[dict]:
    """Peek Related Top/Rising from SQLite — no live Chrome unless user ran Explore before."""
    obs = []
    checked: set[str] = set()
    for term in list(seeds) + list(extra_queries):
        term = term.strip()
        if not term or term.lower() in checked:
            continue
        checked.add(term.lower())
        peek = related_service.peek(term, geo, timeframe)
        if peek and peek.data:
            obs.append({
                "seed": term,
                "data": peek.data,
                "fetched_at": peek.fetched_at,
                "stale": peek.stale,
            })
    return obs


def related_hits(related_obs: list[dict]) -> tuple[int, int]:
    from signals import index_rising

    idx = index_rising(related_obs)
    rising = sum(1 for v in idx.values() if v.get("rising"))
    top = sum(1 for v in idx.values() if v.get("top"))
    return rising, top
