#!/usr/bin/env python3
"""
Daily keyword queue — RSS trending seeds + kwscraper A–Z harvest + FC ranking.

Usage:
  python keyword_automation.py --auto-trends
  python keyword_automation.py --seeds "thanksgiving 2026, election day 2026"
  python keyword_automation.py --auto-trends --write-new-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
DEFAULT_OUT = CACHE / "automation_queue.json"


def _rss_seeds(geo: str, limit: int) -> list[str]:
    from editor_pick import rank_trend_picks
    from trendspyg import download_google_trends_rss

    pack = download_google_trends_rss(geo=geo, normalize=True)
    trends = pack.get("trends") or []
    picks = rank_trend_picks(trends, limit=max(limit, 5), min_fit=20)
    if picks:
        return [(p.get("keyword") or "").strip() for p in picks if (p.get("keyword") or "").strip()][:limit]
    # Fallback: raw RSS if nothing passes FC fit filter
    out: list[str] = []
    for t in trends[: limit * 3]:
        kw = (t.get("keyword") if isinstance(t, dict) else str(t)).strip()
        if kw and kw.lower() not in {s.lower() for s in out}:
            out.append(kw)
        if len(out) >= limit:
            break
    return out


def run_automation(
    seeds: list[str],
    *,
    cache_dir: Path = CACHE,
    geo: str = "US",
    min_words: int = 3,
    refresh_slugs: bool = True,
    new_only: bool = False,
) -> dict:
    import motor_scan
    from content_prioritizer import prioritize_queries
    from published_slugs import PublishedSlugCache
    from site_intelligence import load_gsc_index
    from trending_service import TrendingService, fetch_trending_bundle

    def rss(g):
        from trendspyg import download_google_trends_rss

        return download_google_trends_rss(geo=g, normalize=True)

    bundle = fetch_trending_bundle(
        TrendingService(cache_dir),
        geo,
        mode="rss",
        hours=24,
        fetch_rss=rss,
        fetch_csv=None,
    )

    payload = motor_scan.run_motor_scan(
        seeds,
        geo=geo,
        related_service=_noop_related(),
        get_trendspy=lambda: None,
        get_trending_rss=rss,
        get_trending_csv=None,
        cache_dir=cache_dir,
        trending_bundle=bundle,
        scan_mode="alpha_harvest",
        min_words=min_words,
        run_interest=False,
        refresh_slugs=refresh_slugs,
        trending_mode="rss",
    )

    rows = payload.get("rows") or []
    slugs = PublishedSlugCache(cache_dir / "freshcalendars_slugs.json").load()
    gsc = load_gsc_index(cache_dir)

    if new_only:
        queries = [r["query"] for r in rows if not r.get("published_slug")]
    else:
        queries = [r["query"] for r in rows]

    skip, new = prioritize_queries(queries[:200], gsc_index=gsc, published_slugs=slugs)

    result = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "geo": geo,
        "seeds": seeds,
        "autocomplete_count": payload.get("motor_meta", {}).get("autocomplete_count", 0),
        "kwscraper_stats": payload.get("motor_meta", {}).get("autocomplete_stats"),
        "top_catch": [r for r in rows if r.get("tier") == "Catch now"][:15],
        "top_new": [{"query": d.query, "reason": d.reason} for d in new[:20]],
        "skip_count": len(skip),
    }
    return result


class _noop_related:
    """Related Explore disabled for unattended automation (no Chrome)."""

    def peek(self, *args, **kwargs):
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FC keyword automation (RSS + kwscraper A–Z)")
    p.add_argument("--auto-trends", action="store_true", help="Use top RSS trending as seeds")
    p.add_argument("--trend-limit", type=int, default=5, help="Max RSS seeds when --auto-trends")
    p.add_argument("--seeds", type=str, default="", help="Comma-separated seeds (with or without --auto-trends)")
    p.add_argument("--geo", type=str, default="US")
    p.add_argument("--min-words", type=int, default=3)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--write-new-only", action="store_true", help="Prioritize unpublished queries in summary")
    p.add_argument("--no-slug-refresh", action="store_true")
    args = p.parse_args(argv)

    seeds: list[str] = [s.strip() for s in args.seeds.split(",") if s.strip()]
    if args.auto_trends:
        seeds = list(dict.fromkeys([*_rss_seeds(args.geo, args.trend_limit), *seeds]))[: max(8, args.trend_limit)]

    if not seeds:
        p.error("Provide --seeds or --auto-trends")

    print(f"Seeds ({len(seeds)}): {', '.join(seeds[:8])}", file=sys.stderr)
    result = run_automation(
        seeds,
        geo=args.geo,
        min_words=args.min_words,
        refresh_slugs=not args.no_slug_refresh,
        new_only=args.write_new_only,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Autocomplete rows: {result['autocomplete_count']}, Catch now: {len(result['top_catch'])}")
    for item in result["top_new"][:8]:
        print(f"  NEW: {item['query'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
