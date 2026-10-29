"""Fuse Google autocomplete + Trends signals for editorial opportunities."""
from __future__ import annotations

from dataclasses import dataclass

from long_tail import classify, words
from long_tail_discover import is_long_tail_candidate, specificity_score
from published_slugs import match_published
from trending_service import lookup_trend


@dataclass
class TrendInterestSnapshot:
    keyword: str
    latest: float
    average: float
    momentum: float  # latest / average when average > 0


def interest_momentum(df, keyword: str) -> TrendInterestSnapshot | None:
    if df is None or df.empty or keyword not in df.columns:
        return None
    series = df[keyword].dropna()
    if len(series) < 2:
        return None
    latest = float(series.iloc[-1])
    average = float(series.iloc[:-1].mean()) if len(series) > 1 else float(series.mean())
    if average <= 0:
        momentum = latest
    else:
        momentum = latest / average
    return TrendInterestSnapshot(keyword, latest, average, momentum)


def index_rising(related_rows: list[dict]) -> dict[str, dict]:
    """Map normalized query → rising/top evidence from cached Related observations."""
    out: dict[str, dict] = {}
    for obs in related_rows:
        data = obs.get("data") or {}
        seed = obs.get("seed", "")
        for part in ("top", "rising"):
            for item in data.get(part, []):
                q = (item.get("query") or "").strip()
                if not q:
                    continue
                key = " ".join(q.lower().split())
                entry = out.setdefault(key, {"rising": False, "top": False, "seeds": set(), "values": []})
                entry[part] = True
                entry["seeds"].add(seed)
                val = item.get("formatted_value") or str(item.get("value", ""))
                entry["values"].append(f"{part}:{val}")
    return out


def index_trending(trends: list[dict]) -> set[str]:
    keys = set()
    for t in trends:
        kw = (t.get("keyword") or t.get("trend") or "").strip().lower()
        if kw:
            keys.add(kw)
    return keys


def trending_match_points(trend_hit: dict | None) -> tuple[int, dict]:
    """Score boost from RSS and/or full-list volume."""
    if not trend_hit:
        return 0, {"trending_rss": 0, "trending_volume": 0}
    parts = {"trending_rss": 0, "trending_volume": 0}
    if trend_hit.get("in_rss"):
        parts["trending_rss"] = 22
    vol = int(trend_hit.get("volume_min") or 0)
    if vol >= 500_000:
        parts["trending_volume"] = 28
    elif vol >= 100_000:
        parts["trending_volume"] = 22
    elif vol >= 50_000:
        parts["trending_volume"] = 16
    elif vol >= 10_000:
        parts["trending_volume"] = 10
    elif vol >= 1_000:
        parts["trending_volume"] = 6
    elif vol >= 200 and trend_hit.get("in_rss"):
        parts["trending_volume"] = 4
    return parts["trending_rss"] + parts["trending_volume"], parts


def fuzzy_trending_key_match(query_key: str, trending_keys: set[str]) -> bool:
    """Token overlap only — avoid bare substring false positives."""
    q_tokens = set(query_key.split())
    if not q_tokens:
        return False
    for t in trending_keys:
        if len(t) <= 4:
            continue
        t_tokens = set(t.split())
        if not t_tokens:
            continue
        overlap = q_tokens & t_tokens
        if len(overlap) >= 2:
            return True
        if q_tokens <= t_tokens or t_tokens <= q_tokens:
            return True
        if len(overlap) == 1:
            token = next(iter(overlap))
            if len(token) >= 6 and len(q_tokens) >= 3:
                return True
    return False


def lookup_related(key: str, related_index: dict[str, dict]) -> dict:
    """Exact match, then token-subset fuzzy match for Related Top/Rising."""
    if key in related_index:
        return related_index[key]
    key_tokens = set(key.split())
    best = {}
    best_overlap = 0
    for rk, entry in related_index.items():
        rt = set(rk.split())
        overlap = len(key_tokens & rt)
        if overlap >= 3 and overlap > best_overlap:
            best_overlap = overlap
            best = entry
    return best


def score_opportunity(
    query: str,
    *,
    relevance: int = 0,
    depth: int = 1,
    discover_source: str = "",
    related_index: dict[str, dict],
    trending_keys: set[str],
    trend_index: dict[str, dict] | None = None,
    interest: TrendInterestSnapshot | None,
    published_slugs: set[str],
    seed: str = "",
) -> dict:
    key = " ".join(query.lower().split())
    rel = lookup_related(key, related_index)
    rising = rel.get("rising", False)
    top = rel.get("top", False)
    trend_hit = lookup_trend(query, trend_index) if trend_index else None
    on_trending = bool(trend_hit) or fuzzy_trending_key_match(key, trending_keys)
    trend_pts, trend_parts = trending_match_points(trend_hit if trend_hit else None)
    if on_trending and not trend_pts:
        trend_pts = 18
        trend_parts = {"trending_rss": 18, "trending_volume": 0}

    breakdown = {
        "autocomplete": min(relevance // 10, 40),
        "related": 35 if rising else (20 if top else 0),
        "trending_rss": trend_parts.get("trending_rss", 0),
        "trending_volume": trend_parts.get("trending_volume", 0),
        "interest": 0,
        "long_tail": 0,
        "discover": 0,
        "published_penalty": 0,
    }

    score = breakdown["autocomplete"] + breakdown["related"] + trend_pts

    if interest:
        if interest.momentum >= 1.5:
            breakdown["interest"] += 20
        elif interest.momentum >= 1.15:
            breakdown["interest"] += 10
        breakdown["interest"] += min(int(interest.latest // 5), 15)
        score += breakdown["interest"]

    wc = len(words(query))
    breakdown["long_tail"] += min(max(wc - 2, 0) * 2, 10)
    if depth == 1:
        breakdown["long_tail"] += 5
    spec = specificity_score(query)
    breakdown["long_tail"] += min(spec // 3, 18)
    if wc >= 5 and is_long_tail_candidate(query, min_words=5):
        breakdown["long_tail"] += 8
    if discover_source.startswith("a:"):
        breakdown["discover"] += 4
    if discover_source.startswith("q:"):
        breakdown["discover"] += 6
    score += breakdown["long_tail"] + breakdown["discover"]

    published = match_published(query, published_slugs)
    if published:
        breakdown["published_penalty"] = -50
        score = max(0, score + breakdown["published_penalty"])

    signals = []
    if relevance:
        signals.append(f"autocomplete rel {relevance}")
    if discover_source:
        signals.append(f"discover {discover_source}")
    signals.append(f"specificity {spec}")
    if rising:
        signals.append("trends rising")
    if top:
        signals.append("trends top")
    if on_trending:
        if trend_hit and trend_hit.get("in_full"):
            signals.append(f"trending full vol {trend_hit.get('volume_text') or trend_hit.get('volume_min')}")
        elif trend_hit and trend_hit.get("in_rss"):
            signals.append("trending now rss")
        else:
            signals.append("trending match")
    if interest:
        signals.append(f"interest momentum {interest.momentum:.2f} (last {interest.latest:.0f})")
    if published:
        signals.append(f"already published ~{published}")

    vol_min = int(trend_hit.get("volume_min") or 0) if trend_hit else 0
    tier = opportunity_tier(
        score=min(score, 100),
        rising=rising,
        on_trending=on_trending,
        published=bool(published),
        interest=interest,
        trends_volume_min=vol_min,
    )

    final = min(score, 100)
    return {
        "query": query,
        "seed": seed,
        "score": final,
        "score_breakdown": breakdown,
        "tier": tier,
        "intent": classify(query),
        "signals": "; ".join(signals) or "autocomplete only",
        "published_slug": published or "",
        "word_count": len(words(query)),
        "specificity": spec,
        "discover_source": discover_source,
        "trends_rising": rising,
        "trends_top": top,
        "trends_trending_now": on_trending,
        "trends_volume_min": int(trend_hit.get("volume_min") or 0) if trend_hit else 0,
        "trends_volume_text": (trend_hit.get("volume_text") or "") if trend_hit else "",
        "interest_momentum": round(interest.momentum, 2) if interest else None,
        "headline_hint": headline_hint(query),
    }


def opportunity_tier(
    *,
    score,
    rising,
    on_trending,
    published,
    interest,
    trends_volume_min: int = 0,
) -> str:
    if published:
        return "Skip — published"
    hot_volume = trends_volume_min >= 50_000
    if rising or on_trending or hot_volume or (interest and interest.momentum >= 1.4):
        return "Catch now"
    if score >= 45:
        return "Write soon"
    if score >= 30:
        return "Backlog"
    return "Watch"


def headline_hint(query: str) -> str:
    q = query.strip()
    title = q.title()
    if "?" not in q and not any(x in q.lower() for x in ("how", "what", "when", "why", "is ")):
        return f"{title}: Dates, Deadlines and What to Know"
    return f"{title}: What to Know"


def rank_autocomplete_rows(
    autocomplete_rows: list[dict],
    *,
    related_observations: list[dict],
    trending_list: list[dict],
    trend_index: dict[str, dict] | None = None,
    interest_by_query: dict[str, TrendInterestSnapshot],
    published_slugs: set[str],
) -> list[dict]:
    rel_idx = index_rising(related_observations)
    trending_keys = index_trending(trending_list)
    ranked = []
    for row in autocomplete_rows:
        q = row["query"]
        ranked.append(score_opportunity(
            q,
            relevance=row.get("relevance", 0),
            depth=row.get("depth", 1),
            discover_source=row.get("source", ""),
            seed=row.get("seed", ""),
            related_index=rel_idx,
            trending_keys=trending_keys,
            trend_index=trend_index,
            interest=interest_by_query.get(" ".join(q.lower().split())),
            published_slugs=published_slugs,
        ))
    return sorted(ranked, key=lambda r: (-r["score"], -r["word_count"], r["query"]))
