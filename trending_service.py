"""Unified Google Trends 'Trending' sources: fast RSS + cached full CSV list."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from trendspyg.utils import _parse_traffic_to_min

TrendingSource = Literal["rss", "full", "auto"]
FetchCsv = Callable[..., list[dict]]
FetchRss = Callable[..., Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cache_path(cache_dir: Path, geo: str, hours: int) -> Path:
    safe_geo = (geo or "US").strip().upper()
    return cache_dir / f"trending_full_{safe_geo}_{hours}h.json"


def normalize_rss_trends(envelope: Any) -> list[dict]:
    """Accept trendspyg normalize envelope or raw list."""
    if isinstance(envelope, dict):
        trends = envelope.get("trends") or []
        fetched = envelope.get("fetched_at") or _utc_now_iso()
        origin = envelope.get("source") or "rss"
    else:
        trends = envelope or []
        fetched = _utc_now_iso()
        origin = "rss"
    out: list[dict] = []
    for t in trends:
        kw = (t.get("keyword") or t.get("trend") or "").strip()
        if not kw:
            continue
        vol_text = (t.get("volume_text") or t.get("traffic") or t.get("approx_traffic") or "").strip()
        vol_min = int(t.get("volume_min") or t.get("traffic_min") or 0)
        if not vol_min and vol_text:
            vol_min = _parse_traffic_to_min(vol_text)
        out.append({
            "keyword": kw,
            "rank": int(t.get("rank") or 0),
            "volume_text": vol_text,
            "volume_min": vol_min,
            "started_at": t.get("started_at") or t.get("published") or "",
            "explore_url": t.get("explore_url") or t.get("explore_link") or "",
            "related_queries": list(t.get("related_queries") or []),
            "origin": "rss",
        })
    return out


def normalize_csv_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for rank, row in enumerate(rows, start=1):
        kw = (row.get("Trends") or row.get("keyword") or "").strip()
        if not kw:
            continue
        vol_text = (row.get("Search volume") or row.get("volume_text") or "").strip()
        breakdown = (row.get("Trend breakdown") or "").strip()
        related = [q.strip() for q in breakdown.split(",") if q.strip()]
        out.append({
            "keyword": kw,
            "rank": rank,
            "volume_text": vol_text,
            "volume_min": _parse_traffic_to_min(vol_text),
            "started_at": row.get("Started") or "",
            "explore_url": row.get("Explore link") or "",
            "related_queries": related,
            "origin": "csv",
        })
    return out


def sort_by_volume(trends: list[dict]) -> list[dict]:
    ordered = sorted(
        trends,
        key=lambda t: (-int(t.get("volume_min") or 0), int(t.get("rank") or 9999)),
    )
    for i, t in enumerate(ordered, start=1):
        t["rank"] = i
    return ordered


class TrendingService:
    """RSS (always light) + optional full CSV snapshot on disk (Chrome)."""

    def __init__(self, cache_dir: Path, *, full_ttl_seconds: int = 2700):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.full_ttl_seconds = full_ttl_seconds

    def load_full_cache(self, geo: str, hours: int) -> dict | None:
        path = _cache_path(self.cache_dir, geo, hours)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        fetched = data.get("fetched_at") or ""
        if not fetched:
            return None
        try:
            ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
        except ValueError:
            age = self.full_ttl_seconds + 1
        data["cache_age_seconds"] = int(age)
        data["stale"] = age > self.full_ttl_seconds
        return data

    def save_full_cache(self, geo: str, hours: int, trends: list[dict], *, error: str = "") -> dict:
        payload = {
            "geo": geo,
            "hours": hours,
            "source": "csv",
            "fetched_at": _utc_now_iso(),
            "count": len(trends),
            "trends": trends,
            "error": error,
        }
        path = _cache_path(self.cache_dir, geo, hours)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["stale"] = False
        payload["cache_age_seconds"] = 0
        return payload

    def fetch_rss(self, geo: str, fetch_rss: FetchRss) -> dict:
        try:
            raw = fetch_rss(geo)
            trends = normalize_rss_trends(raw)
            return {
                "geo": geo,
                "source": "rss",
                "fetched_at": _utc_now_iso(),
                "count": len(trends),
                "trends": trends,
                "error": "",
            }
        except Exception as exc:
            return {
                "geo": geo,
                "source": "rss",
                "fetched_at": _utc_now_iso(),
                "count": 0,
                "trends": [],
                "error": str(exc),
            }

    def fetch_full(
        self,
        geo: str,
        hours: int,
        fetch_csv: FetchCsv,
        *,
        refresh: bool = False,
    ) -> dict:
        if not refresh:
            cached = self.load_full_cache(geo, hours)
            if cached and not cached.get("stale") and cached.get("trends"):
                cached["from_cache"] = True
                return cached
        try:
            rows = fetch_csv(geo=geo, hours=hours, output_format="dict", headless=True)
            trends = sort_by_volume(normalize_csv_rows(rows or []))
            payload = self.save_full_cache(geo, hours, trends)
            payload["from_cache"] = False
            return payload
        except Exception as exc:
            cached = self.load_full_cache(geo, hours)
            if cached and cached.get("trends"):
                cached["error"] = str(exc)
                cached["from_cache"] = True
                return cached
            return {
                "geo": geo,
                "hours": hours,
                "source": "csv",
                "fetched_at": _utc_now_iso(),
                "count": 0,
                "trends": [],
                "error": str(exc),
                "from_cache": False,
            }

    def resolve(
        self,
        geo: str,
        *,
        mode: TrendingSource = "auto",
        hours: int = 24,
        fetch_rss: FetchRss,
        fetch_csv: FetchCsv | None = None,
        refresh_full: bool = False,
    ) -> dict:
        """
        Returns envelope with primary ``trends`` for UI + ``index`` for scoring.
        ``auto`` = full cache if fresh else RSS for display; scoring merges both when possible.
        """
        rss_pack = self.fetch_rss(geo, fetch_rss)
        full_pack: dict | None = None
        if fetch_csv is not None:
            if mode == "full":
                full_pack = self.fetch_full(geo, hours, fetch_csv, refresh=refresh_full)
            elif mode == "auto":
                if refresh_full:
                    full_pack = self.fetch_full(geo, hours, fetch_csv, refresh=True)
                else:
                    cached = self.load_full_cache(geo, hours)
                    if cached and cached.get("trends"):
                        cached["from_cache"] = True
                        full_pack = cached

        if mode == "rss" or not full_pack or not full_pack.get("trends"):
            primary = rss_pack
            primary_name = "rss"
        elif mode == "full":
            primary = full_pack
            primary_name = "full"
        else:
            if full_pack.get("trends") and not full_pack.get("stale"):
                primary = full_pack
                primary_name = "full"
            else:
                primary = rss_pack
                primary_name = "rss"

        rss_trends = rss_pack.get("trends") or []
        full_trends = (full_pack.get("trends") if full_pack else []) or []
        # Scoring always merges RSS + full cache when available (even if UI shows RSS).
        if not full_trends and mode == "auto":
            cached = self.load_full_cache(geo, hours)
            if cached and cached.get("trends"):
                full_trends = cached["trends"]
        index = build_trend_index(rss_trends, full_trends)
        return {
            "geo": geo,
            "hours": hours,
            "mode": mode,
            "primary": primary_name,
            "fetched_at": primary.get("fetched_at"),
            "trends": primary.get("trends") or [],
            "rss": rss_pack,
            "full": full_pack,
            "index": index,
            "errors": {
                "rss": rss_pack.get("error") or "",
                "full": (full_pack or {}).get("error") or "",
            },
        }


def build_trend_index(rss_trends: list[dict], full_trends: list[dict]) -> dict[str, dict]:
    """Normalized keyword → best volume + flags for RSS / full list."""
    idx: dict[str, dict] = {}

    def ingest(items: list[dict], flag: str) -> None:
        for t in items:
            kw = (t.get("keyword") or "").strip()
            if not kw:
                continue
            key = " ".join(kw.lower().split())
            entry = idx.setdefault(
                key,
                {
                    "keyword": kw,
                    "volume_min": 0,
                    "volume_text": "",
                    "in_rss": False,
                    "in_full": False,
                    "related_queries": [],
                },
            )
            entry[flag] = True
            vol = int(t.get("volume_min") or 0)
            if vol >= entry["volume_min"]:
                entry["volume_min"] = vol
                entry["volume_text"] = t.get("volume_text") or entry["volume_text"]
            rel = t.get("related_queries") or []
            if len(rel) > len(entry["related_queries"]):
                entry["related_queries"] = rel[:40]

    ingest(rss_trends, "in_rss")
    ingest(full_trends, "in_full")
    return idx


def fetch_trending_bundle(trending_service: TrendingService, geo: str, **kwargs) -> dict:
    """Resolve RSS/full/auto envelope (used by dashboard + motor_scan)."""
    return trending_service.resolve(geo, **kwargs)


def lookup_trend(query: str, index: dict[str, dict]) -> dict | None:
    key = " ".join(query.lower().split())
    if key in index:
        return index[key]
    for tk, entry in index.items():
        if len(key) >= 5 and (key in tk or tk in key):
            return entry
    key_tokens = set(key.split())
    if len(key_tokens) < 2:
        return None
    best: dict | None = None
    best_overlap = 0
    for tk, entry in index.items():
        overlap = len(key_tokens & set(tk.split()))
        if overlap >= 2 and overlap > best_overlap:
            best_overlap = overlap
            best = entry
    return best
