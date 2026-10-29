"""Separate noise vs new content — GSC + published slugs + site themes."""

from __future__ import annotations

from dataclasses import dataclass

from editor_pick import calendar_fit_score
from published_slugs import match_published
from site_intelligence import (
    _DEMOTE,
    content_intent,
    fc_theme_boost,
    lookup_gsc,
    site_action_hint,
)


@dataclass
class ContentDecision:
    query: str
    bucket: str  # skip | refresh | new
    reason: str
    impressions: int = 0
    position: float = 0.0
    ctr: float = 0.0
    intent: str = ""
    action: str = ""


def _skip_reason(query: str, gsc: dict | None, published: str | None) -> str | None:
    if _DEMOTE.search(query):
        return "puzzle/viral — FC dışı, yeni sayfa üretme"
    if published:
        if gsc and gsc["impressions"] >= 5000 and gsc["ctr"] < 0.5:
            return None  # handled as refresh in _new_reason
        return f"zaten yayında (~{published}) — yeni URL değil, güncelle/iç link"
    fit = calendar_fit_score(query)
    if fit < 25 and not (gsc and gsc["impressions"] >= 2000):
        return "düşük FC uyumu — öncelik verme"
    if gsc and gsc["impressions"] >= 500 and gsc["ctr"] >= 2.5 and gsc["position"] <= 6:
        return "GSC sağlıklı (iyi CTR + sıra) — yeni içerik değil, koru"
    theme_pts, _, _ = fc_theme_boost(query)
    if theme_pts < 0:
        return "site zekâsı demote"
    return None


def _new_reason(query: str, gsc: dict | None, published: str | None) -> str | None:
    if published:
        if gsc and gsc["impressions"] >= 5000 and gsc["ctr"] < 0.5:
            return f"Yayın var ama GSC kaçak — yeni hub URL veya title/H1 değiştir (~{published})"
        return None
    theme_pts, label, _ = fc_theme_boost(query)
    intent = content_intent(query)
    if gsc:
        imp, ctr, pos = gsc["impressions"], gsc["ctr"], gsc["position"]
        if imp >= 800 and ctr < 1.2 and pos <= 12:
            return f"GSC fırsat ({int(imp):,} imp, CTR %{ctr:.2f}) — {label or intent}"
        if imp >= 5000 and ctr < 0.5:
            return f"GSC kaçak ({int(imp):,} imp) — hub/title düzelt veya yeni URL"
    if theme_pts >= 28:
        return f"kanıtlı FC tema ({label}) — yeni veya hub"
    if calendar_fit_score(query) >= 45 and intent in ("date_hub", "tool_hub", "printable_asset"):
        return f"yüksek FC fit — {intent}"
    return None


def prioritize_queries(
    queries: list[str],
    *,
    gsc_index: dict[str, dict],
    published_slugs: set[str],
) -> tuple[list[ContentDecision], list[ContentDecision]]:
    """Returns (skip_list, new_content_list)."""
    skip: list[ContentDecision] = []
    new: list[ContentDecision] = []
    seen: set[str] = set()

    for q in queries:
        key = " ".join(q.lower().split())
        if key in seen or not q.strip():
            continue
        seen.add(key)
        gsc = lookup_gsc(q, gsc_index)
        pub = match_published(q, published_slugs)
        imp = int(gsc["impressions"]) if gsc else 0
        pos = float(gsc["position"]) if gsc else 0.0
        ctr = float(gsc["ctr"]) if gsc else 0.0
        intent = content_intent(q)
        action = site_action_hint(q, intent, gsc)

        why_skip = _skip_reason(q, gsc, pub)
        if why_skip:
            skip.append(ContentDecision(q, "skip", why_skip, imp, pos, ctr, intent, action))
            continue

        why_new = _new_reason(q, gsc, pub)
        if why_new:
            bucket = "refresh" if gsc and imp >= 5000 and ctr < 0.5 else "new"
            new.append(ContentDecision(q, bucket, why_new, imp, pos, ctr, intent, action))

    skip.sort(key=lambda x: -x.impressions)
    new.sort(key=lambda x: (-x.impressions, -calendar_fit_score(x.query)))
    return skip, new


def prioritize_gsc_index(
    gsc_index: dict[str, dict],
    published_slugs: set[str],
    *,
    min_impressions: int = 200,
) -> tuple[list[ContentDecision], list[ContentDecision]]:
    entries = sorted(gsc_index.values(), key=lambda e: -e["impressions"])
    queries = [e["query"] for e in entries if e["impressions"] >= min_impressions]
    return prioritize_queries(queries, gsc_index=gsc_index, published_slugs=published_slugs)
