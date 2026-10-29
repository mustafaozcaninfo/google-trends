"""Shared scan pipeline for dashboard and app.

Flow (FC News Radar):
  1. Trending — RSS + optional full CSV cache → display list + volume index for scoring.
  2. Seeds — user pick, editor pack, or top-N trending (capped).
  3. Autocomplete — suggestqueries probes (seed, space, a–z, how/what/…) → long-tail rows.
  4. Related — SQLite peek only (no Chrome unless user fetched Explore before).
  5. Interest — cache-first trendspyg, max 3 keywords, global throttle (429 guard).
  6. Score — autocomplete + related + trending volume + interest momentum − published slug.
  7. Output — tiers (Catch now … Skip), chart series, CSV/JSON export.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from google_autocomplete import AutocompleteService


def _discover_long_tail(ac: AutocompleteService, seeds: list[str], **kwargs) -> tuple[list[dict], dict]:
    """Compatible with legacy discover_long_tail that returned only rows."""
    out = ac.discover_long_tail(seeds, **kwargs)
    if isinstance(out, tuple) and len(out) == 2:
        rows, stats = out
        return list(rows or []), dict(stats or {})
    return list(out or []), {}


def _discover_modifier(ac: AutocompleteService, seeds: list[str], **kwargs) -> tuple[list[dict], dict]:
    out = ac.discover_modifier_content(seeds, **kwargs)
    if isinstance(out, tuple) and len(out) == 2:
        rows, stats = out
        return list(rows or []), dict(stats or {})
    return list(out or []), {}
from published_slugs import PublishedSlugCache
from long_tail_discover import PRINTABLE_ANCHOR_SEEDS, specificity_score
from signals import rank_autocomplete_rows
from interest_cache import InterestCache
from trending_service import TrendingService, fetch_trending_bundle
from site_intelligence import apply_site_intelligence, load_gsc_index
from future_demand import enrich_future_demand


def _trends_layer():
    import importlib
    import trends_layer as tl

    importlib.reload(tl)
    return tl


def run_motor_scan(
    seeds: list[str],
    *,
    geo: str = "US",
    related_service,
    get_trendspy,
    get_trending_rss,
    cache_dir: Path,
    trending_service: TrendingService | None = None,
    trending_mode: str = "auto",
    trending_hours: int = 24,
    refresh_trending_full: bool = False,
    trending_bundle: dict | None = None,
    get_trending_csv=None,
    depth: int = 1,
    max_children: int = 3,
    scan_mode: str = "deep",
    min_words: int = 3,
    run_interest: bool = False,
    interest_timeframe: str = "now 1-d",
    interest_backend: str = "auto",
    interest_chart_queries: int = 3,
    use_trending_as_seeds: bool = False,
    trending_seed_limit: int = 5,
    refresh_slugs: bool = False,
    related_timeframe: str = "today 3-m",
) -> dict:
    interval = 0.4 if scan_mode in ("deep", "deep_plus") else 0.8 if scan_mode == "printable" else 1.5
    ac = AutocompleteService(cache_dir / "autocomplete.sqlite3", min_interval=interval)
    hl, gl = "en", (geo or "US").strip().lower()

    svc = trending_service or TrendingService(cache_dir)
    tl = _trends_layer()
    if trending_bundle is not None:
        bundle = trending_bundle
    else:
        bundle = fetch_trending_bundle(
            svc,
            geo,
            mode=trending_mode if trending_mode in ("rss", "full", "auto") else "auto",
            hours=trending_hours,
            fetch_rss=get_trending_rss,
            fetch_csv=get_trending_csv,
            refresh_full=refresh_trending_full,
        )
    trend_list = bundle.get("trends") or []
    trend_index = bundle.get("index") or {}

    scan_seeds = list(seeds)
    if use_trending_as_seeds and trend_list:
        cap = min(max(0, int(trending_seed_limit)), 5)
        for t in trend_list[: max(1, cap)]:
            kw = (t.get("keyword") or t.get("trend") or "").strip()
            if kw and kw.lower() not in {s.lower() for s in scan_seeds}:
                scan_seeds.append(kw)

    ac_stats: dict = {}
    if scan_mode == "printable":
        modifier_seeds = list(dict.fromkeys([*scan_seeds, *PRINTABLE_ANCHOR_SEEDS]))
        ac_rows, ac_stats = _discover_modifier(
            ac,
            modifier_seeds,
            hl=hl,
            gl=gl,
            min_words=min(min_words, 3),
        )
    elif scan_mode == "quick":
        ac_rows = ac.expand(
            scan_seeds,
            hl=hl,
            gl=gl,
            depth=depth,
            max_children=max_children,
            min_words=min_words,
            filter_seeds=scan_seeds,
        )
    else:
        ac_rows, ac_stats = _discover_long_tail(
            ac,
            scan_seeds,
            hl=hl,
            gl=gl,
            alphabet=True,
            question_prefixes=True,
            tail_space=True,
            min_words=min_words,
        )
        bootstrap_floor = max(12, 4 * len(scan_seeds))
        if len(ac_rows) < bootstrap_floor:
            extra = ac.expand(
                scan_seeds,
                hl=hl,
                gl=gl,
                depth=1,
                max_children=5,
                min_words=min_words,
                filter_seeds=scan_seeds,
            )
            seen = {" ".join(r["query"].lower().split()) for r in ac_rows}
            added = 0
            for row in extra:
                key = " ".join(row["query"].lower().split())
                if key in seen:
                    continue
                row["source"] = "bootstrap:" + row.get("source", "autocomplete")
                ac_rows.append(row)
                seen.add(key)
                added += 1
            ac_stats["bootstrap_added"] = added
        if scan_mode == "deep_plus" and ac_rows:
            follow: list[str] = []
            by_seed: dict[str, list] = {}
            for row in ac_rows:
                by_seed.setdefault(row.get("seed", ""), []).append(row)
            for _, items in by_seed.items():
                items.sort(key=lambda r: (-r.get("relevance", 0), -specificity_score(r["query"])))
                follow.extend(r["query"] for r in items[:2])
            extra = ac.expand(
                follow,
                hl=hl,
                gl=gl,
                depth=1,
                max_children=2,
                min_words=min_words,
                filter_seeds=scan_seeds,
            )
            seen = {" ".join(r["query"].lower().split()) for r in ac_rows}
            for row in extra:
                key = " ".join(row["query"].lower().split())
                if key not in seen:
                    row["seed"] = row.get("seed") or row.get("parent", "")
                    row["source"] = "follow:" + row.get("source", "autocomplete")
                    ac_rows.append(row)
                    seen.add(key)

    top_queries = sorted(ac_rows, key=lambda r: specificity_score(r["query"]), reverse=True)
    top_for_related = [r["query"] for r in top_queries[:5]]

    related_obs = tl.load_related_cache(
        related_service, scan_seeds, top_for_related, geo, related_timeframe,
    )
    rising_n, top_n = tl.related_hits(related_obs)

    interest_map = {}
    interest_series: dict[str, list[dict]] = {}
    interest_error = ""
    chart_keys: list[str] = []
    if run_interest:
        chart_keys = list(dict.fromkeys(
            [s.strip() for s in scan_seeds[:1]]
            + [r["query"] for r in top_queries[: max(0, int(interest_chart_queries) - 1)]]
        ))[: max(1, int(interest_chart_queries))]
        interest_targets = list(chart_keys)
        from interest_gate import InterestGate

        interest_cache = InterestCache(cache_dir / "interest.sqlite3")
        gate = InterestGate(cache_dir / "interest_live_gate.json", min_interval_seconds=55.0)
        interest_map, interest_series, interest_error = tl.fetch_interest_map(
            get_trendspy,
            interest_targets,
            geo,
            interest_timeframe,
            include_series=True,
            cache=interest_cache,
            cache_dir=cache_dir,
            max_keywords=3,
            interest_backend=interest_backend,
            gate=gate,
        )
        # Keep chart payload small — only selected phrases
        chart_norm = {" ".join(q.lower().split()) for q in chart_keys}
        interest_series = {k: v for k, v in interest_series.items() if k in chart_norm}

    slug_cache = PublishedSlugCache(cache_dir / "freshcalendars_slugs.json")
    published = slug_cache.load(refresh=refresh_slugs)

    ranked = rank_autocomplete_rows(
        ac_rows,
        related_observations=related_obs,
        trending_list=trend_list,
        trend_index=trend_index,
        interest_by_query=interest_map,
        published_slugs=published,
    )

    gsc_index = load_gsc_index(cache_dir)
    if gsc_index:
        ranked = apply_site_intelligence(ranked, gsc_index)

    ranked = enrich_future_demand(ranked)

    return {
        "rows": ranked,
        "trending": trend_list,
        "trending_bundle": bundle,
        "interest_series": interest_series,
        "interest_chart_queries": chart_keys,
        "seeds": scan_seeds,
        "_scan_context": {
            "ac_rows": ac_rows,
            "related_obs": related_obs,
            "trend_list": trend_list,
            "trend_index": trend_index,
        },
        "motor_meta": {
            "scanned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "autocomplete_count": len(ac_rows),
            "published_count": len(published),
            "geo": geo,
            "interest_error": interest_error,
            "interest_timeframe": interest_timeframe,
            "interest_backend": interest_backend if run_interest else "",
            "interest_checked": len(interest_map),
            "related_cache_hits": len(related_obs),
            "related_rising_terms": rising_n,
            "related_top_terms": top_n,
            "scan_mode": scan_mode,
            "min_words": min_words,
            "trending_mode": bundle.get("mode"),
            "trending_primary": bundle.get("primary"),
            "trending_index_size": len(trend_index),
            "trending_errors": bundle.get("errors") or {},
            "autocomplete_stats": ac_stats,
            "gsc_queries_loaded": len(gsc_index) if gsc_index else 0,
            "pipeline": {
                "step1_seeds": len(seeds),
                "step1_seeds_with_roots": len(scan_seeds),
                "step2_autocomplete": len(ac_rows),
                "step3_trending_rss": len((bundle.get("rss") or {}).get("trends") or []),
                "step3_trending_full": len((bundle.get("full") or {}).get("trends") or []),
                "step3_trending_display": len(trend_list),
                "step3_related_cached": len(related_obs),
                "step3_interest_series": len(interest_map),
                "step3_interest_tf": interest_timeframe if run_interest else "",
                "step4_scored": len(ranked),
            },
        },
    }


def add_interest_to_payload(
    payload: dict,
    *,
    geo: str,
    cache_dir: Path,
    get_trendspy,
    interest_timeframe: str = "now 1-d",
    interest_backend: str = "auto",
    interest_chart_queries: int = 2,
) -> dict:
    """On-demand interest + optional re-score (no autocomplete re-fetch)."""
    from interest_gate import InterestGate

    ctx = payload.get("_scan_context") or {}
    ac_rows = ctx.get("ac_rows") or []
    if not ac_rows:
        ac_rows = [
            {
                "query": r["query"],
                "seed": r.get("seed", ""),
                "relevance": max(0, (r.get("score_breakdown") or {}).get("autocomplete", 0) * 10),
                "depth": 1,
                "source": r.get("discover_source", ""),
            }
            for r in payload.get("rows") or []
        ]

    seeds = payload.get("seeds") or []
    ranked_rows = sorted(
        [r for r in payload.get("rows") or [] if not r.get("published_slug")],
        key=lambda r: (-r.get("score", 0), -r.get("word_count", 0)),
    )
    chart_keys = list(dict.fromkeys(
        [s.strip() for s in seeds[:1]]
        + [r["query"] for r in ranked_rows[: max(0, int(interest_chart_queries) - 1)]]
    ))[: max(1, int(interest_chart_queries))]

    tl = _trends_layer()
    interest_cache = InterestCache(cache_dir / "interest.sqlite3")
    gate = InterestGate(cache_dir / "interest_live_gate.json", min_interval_seconds=55.0)
    interest_map, interest_series, interest_error = tl.fetch_interest_map(
        get_trendspy,
        chart_keys,
        geo,
        interest_timeframe,
        include_series=True,
        cache=interest_cache,
        cache_dir=cache_dir,
        max_keywords=3,
        interest_backend=interest_backend,
        gate=gate,
    )
    chart_norm = {" ".join(q.lower().split()) for q in chart_keys}
    interest_series = {k: v for k, v in interest_series.items() if k in chart_norm}

    slug_cache = PublishedSlugCache(cache_dir / "freshcalendars_slugs.json")
    published = slug_cache.load(refresh=False)
    ranked = rank_autocomplete_rows(
        ac_rows,
        related_observations=ctx.get("related_obs") or [],
        trending_list=ctx.get("trend_list") or payload.get("trending") or [],
        trend_index=ctx.get("trend_index") or (payload.get("trending_bundle") or {}).get("index") or {},
        interest_by_query=interest_map,
        published_slugs=published,
    )

    out = dict(payload)
    out["rows"] = ranked
    out["interest_series"] = interest_series
    out["interest_chart_queries"] = chart_keys
    meta = dict(out.get("motor_meta") or {})
    meta["interest_error"] = interest_error
    meta["interest_timeframe"] = interest_timeframe
    meta["interest_backend"] = interest_backend
    meta["interest_checked"] = len(interest_map)
    pipe = dict(meta.get("pipeline") or {})
    pipe["step3_interest_series"] = len(interest_map)
    pipe["step3_interest_tf"] = interest_timeframe
    meta["pipeline"] = pipe
    out["motor_meta"] = meta
    return out
