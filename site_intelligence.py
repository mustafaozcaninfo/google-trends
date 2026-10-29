"""Fresh Calendars — GSC + proven winners → ranking lift for /news growth."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from long_tail import words, normalize

# Themes that already win in Search Console (Oct 2026 export)
_PROVEN_THEMES: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"\b(sample ballot|ballot by zip|view my sample ballot)\b", re.I), 35, "ballot_hub"),
    (re.compile(r"\bprintable.*ballot\b|\bballot.*printable\b", re.I), 40, "ballot_printable"),
    (re.compile(r"\bthanksgiving 2026\b", re.I), 45, "thanksgiving_hub"),
    (re.compile(r"\bthanksgiving\b.*\b(2026|date|day|calendar|printable)\b", re.I), 30, "thanksgiving_longtail"),
    (re.compile(r"\bbank holidays?\b.*\b2027\b|\b2027\b.*\bbank holidays?\b", re.I), 38, "bank_holidays"),
    (re.compile(r"\b(diwali|ramadan|eid)\b.*\b(2026|2027|usa|calendar|date)\b", re.I), 28, "faith_calendar"),
    (re.compile(r"\b(daylight saving|sunset time|what time is sunset)\b", re.I), 22, "time_change"),
    (re.compile(r"\b(election day|election results|is election day)\b", re.I), 26, "election_news"),
    (re.compile(r"\b(school closings|school delays|school calendar)\b", re.I), 20, "school_calendar"),
    (re.compile(r"\bprintable calendar\b.*\b(2026|2027)\b", re.I), 32, "printable_calendar"),
    (re.compile(r"\b(black friday|cyber monday)\b.*\b2026\b", re.I), 18, "retail_calendar"),
    (re.compile(r"\b\w+ calendar\b.*\b(2026|2027|september|october)\b", re.I), 15, "month_calendar"),
]

# Queries we should NOT chase (puzzle/viral noise in GSC)
_DEMOTE = re.compile(
    r"\b(strands|connections|wordle|minion|misnomer|stooge|gta 6|english horn food)\b",
    re.I,
)


def parse_gsc_queries_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = (row.get("Top queries") or row.get("Query") or "").strip()
            if not q:
                continue
            rows.append({
                "query": q,
                "clicks": _num(row.get("Clicks")),
                "impressions": _num(row.get("Impressions")),
                "ctr": _num(str(row.get("CTR", "")).replace("%", "")),
                "position": _num(row.get("Position")),
            })
    return rows


def _num(val) -> float:
    try:
        return float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def build_gsc_index(rows: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for row in rows:
        key = normalize(row["query"])
        prev = idx.get(key)
        if prev is None or row["impressions"] > prev["impressions"]:
            idx[key] = row
    return idx


def load_gsc_index(cache_dir: Path) -> dict[str, dict]:
    path = cache_dir / "gsc_queries.csv"
    if not path.is_file():
        return {}
    return build_gsc_index(parse_gsc_queries_csv(path))


def lookup_gsc(query: str, gsc_index: dict[str, dict]) -> dict | None:
    key = normalize(query)
    if key in gsc_index:
        return gsc_index[key]
    q_tokens = set(words(query))
    best: dict | None = None
    best_imp = 0.0
    for gk, entry in gsc_index.items():
        gt = set(gk.split())
        overlap = len(q_tokens & gt)
        if overlap >= 2 and overlap >= len(q_tokens) * 0.5:
            if entry["impressions"] > best_imp:
                best_imp = entry["impressions"]
                best = entry
    return best


def gsc_opportunity_points(entry: dict | None) -> tuple[int, list[str]]:
    """High impressions + weak CTR + page 2–12 = room to climb."""
    if not entry:
        return 0, []
    imp = entry["impressions"]
    ctr = entry["ctr"]
    pos = entry["position"]
    parts: list[str] = []
    pts = 0
    if imp >= 500:
        pts += min(int(imp // 800), 40)
        parts.append(f"gsc imp {int(imp)}")
    if imp >= 200 and ctr < 1.0:
        pts += 15
        parts.append(f"gsc low ctr {ctr:.2f}%")
    if 3.5 <= pos <= 12:
        pts += 12
        parts.append(f"gsc pos {pos:.1f}")
    if imp >= 5000 and ctr < 0.5:
        pts += 20
        parts.append("gsc leak")
    return pts, parts


def fc_theme_boost(query: str) -> tuple[int, str, list[str]]:
    if _DEMOTE.search(query):
        return -25, "demote_puzzle", ["site demote puzzle/viral"]
    for pat, pts, label in _PROVEN_THEMES:
        if pat.search(query):
            return pts, label, [f"site theme {label}"]
    return 0, "", []


def content_intent(query: str) -> str:
    ql = query.lower()
    if re.search(r"\bprintable\b|\bpdf\b|\btemplate\b|\bdownload\b", ql):
        return "printable_asset"
    if re.search(r"\b(ballot|zip code|by county|by state)\b", ql):
        return "tool_hub"
    if re.search(r"\bthanksgiving 2026\b", ql) and "why" not in ql and "november 26" not in ql:
        return "date_hub"
    if re.search(r"\b(when is|what day|what time|how long until)\b", ql):
        return "date_explainer"
    if re.search(r"\b(holiday|open|closed|hours)\b", ql):
        return "hours_explainer"
    return "news_explainer"


def site_action_hint(query: str, intent: str, gsc: dict | None) -> str:
    if gsc and gsc["impressions"] >= 5000 and gsc["ctr"] < 0.5:
        if intent == "date_hub":
            return "Title/H1’i genel aramaya çevir (date hub); mevcut ‘why Nov 26’ makalesini iç linkle."
        return "Snippet + title eşleşmesi; CTR düşük, sıra iyi — meta yenile."
    if intent == "tool_hub":
        return "Eyalet/zip hub veya printable CTA ekle."
    if intent == "printable_asset":
        return "PDF/printable indirme + schema FAQ."
    if intent == "date_hub":
        return "Tek sayfada date, countdown, calendar PDF."
    return "Long-tail haber + internal link cluster."


def apply_site_intelligence(
    ranked_rows: list[dict],
    gsc_index: dict[str, dict],
) -> list[dict]:
    if not ranked_rows:
        return ranked_rows
    out: list[dict] = []
    for row in ranked_rows:
        q = row.get("query") or ""
        gsc = lookup_gsc(q, gsc_index)
        theme_pts, theme_label, theme_parts = fc_theme_boost(q)
        gsc_pts, gsc_parts = gsc_opportunity_points(gsc)
        site_pts = theme_pts + gsc_pts
        if site_pts < -10:
            site_pts = -10
        intent = content_intent(q)
        breakdown = dict(row.get("score_breakdown") or {})
        breakdown["site_intelligence"] = site_pts
        signals = row.get("signals") or ""
        extra = theme_parts + gsc_parts
        if extra:
            signals = "; ".join(filter(None, [signals, "; ".join(extra)]))
        site_score = int(row.get("score", 0)) + site_pts
        tier = row.get("tier", "")
        if (
            site_pts >= 35
            and gsc
            and gsc["impressions"] >= 1000
            and tier not in ("Skip — published",)
        ):
            tier = "Catch now"
        elif site_pts >= 25 and tier == "Watch":
            tier = "Write soon"

        out.append({
            **row,
            "score": site_score,
            "score_breakdown": breakdown,
            "signals": signals,
            "tier": tier,
            "site_boost": site_pts,
            "site_theme": theme_label,
            "content_intent": intent,
            "site_action": site_action_hint(q, intent, gsc),
            "gsc_impressions": int(gsc["impressions"]) if gsc else 0,
            "gsc_position": round(gsc["position"], 1) if gsc else None,
            "gsc_ctr": round(gsc["ctr"], 2) if gsc else None,
        })
    return sorted(out, key=lambda r: (-r.get("site_boost", 0), -r["score"], r["query"]))


def top_gsc_gaps(gsc_index: dict[str, dict], *, limit: int = 12) -> list[dict]:
    """Prioritize fixes: high imp, low CTR, striking distance."""
    rows = list(gsc_index.values())
    scored = []
    for e in rows:
        if _DEMOTE.search(e["query"]):
            continue
        theme_pts, label, _ = fc_theme_boost(e["query"])
        if theme_pts <= 0 and e["impressions"] < 800:
            continue
        gap = e["impressions"] * max(0, 2.0 - e["ctr"]) * (1.0 / max(e["position"], 1.0))
        scored.append({**e, "gap_score": gap, "site_theme": label, "theme_boost": theme_pts})
    scored.sort(key=lambda x: (-x["gap_score"], -x["impressions"]))
    return scored[:limit]
