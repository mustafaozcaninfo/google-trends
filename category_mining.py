"""Mine autocomplete from FC strategic categories (GSC + site_intelligence themes)."""

from __future__ import annotations

from dataclasses import dataclass

# Category → short seeds + sub-word roots for probe expansion
FC_CATEGORIES: dict[str, dict] = {
    "ballot_printable": {
        "seeds": [
            "sample ballot by zip code",
            "printable sample ballot 2026",
            "view my sample ballot 2026",
        ],
        "roots": ["ballot", "zip", "printable", "voting", "precinct"],
    },
    "thanksgiving_hub": {
        "seeds": ["thanksgiving 2026", "thanksgiving 2026 date"],
        "roots": ["thanksgiving", "turkey", "november"],
    },
    "bank_holidays": {
        "seeds": ["bank holidays 2027", "federal holidays 2026"],
        "roots": ["bank", "holiday", "federal", "observed"],
    },
    "faith_calendar": {
        "seeds": ["diwali 2026 usa", "ramadan 2027 calendar", "when is diwali 2026"],
        "roots": ["diwali", "ramadan", "eid", "puja"],
    },
    "school_calendar": {
        "seeds": ["school closings", "school calendar 2026", "school delays"],
        "roots": ["school", "closings", "delays", "district"],
    },
    "printable_calendar": {
        "seeds": ["printable calendar 2026", "calendar 2026 pdf", "free printable calendar 2027"],
        "roots": ["printable", "calendar", "pdf", "monthly"],
    },
    "election_news": {
        "seeds": ["election day 2026", "election results 2026", "is election day a holiday"],
        "roots": ["election", "vote", "midterm", "polling"],
    },
    "time_dst": {
        "seeds": ["daylight saving time 2026", "what time is sunset", "sunset times 2026"],
        "roots": ["sunset", "daylight", "time change"],
    },
    "retail_calendar": {
        "seeds": ["black friday 2026", "cyber monday 2026 dates"],
        "roots": ["black", "friday", "cyber", "deals"],
    },
}


@dataclass
class CategoryPlan:
    category_id: str
    label: str
    seeds: list[str]


def plans_from_gsc(gsc_index: dict, *, per_category: int = 2) -> list[CategoryPlan]:
    """Pull top GSC queries into matching categories when possible."""
    from site_intelligence import fc_theme_boost

    by_cat: dict[str, list[tuple[float, str]]] = {}
    for entry in gsc_index.values():
        q = entry["query"]
        pts, label, _ = fc_theme_boost(q)
        if pts <= 0 or not label:
            continue
        by_cat.setdefault(label, []).append((entry["impressions"], q))
    out: list[CategoryPlan] = []
    for cat_id, cfg in FC_CATEGORIES.items():
        seeds = list(cfg["seeds"])
        theme_rows = by_cat.get(cat_id.replace("_hub", "").split("_")[0], [])
        # match theme label prefix loosely
        for label, rows in by_cat.items():
            if label.split("_")[0] in cat_id or cat_id.startswith(label.split("_")[0]):
                theme_rows = rows
                break
        rows_sorted = sorted(theme_rows, key=lambda x: -x[0])
        for _, q in rows_sorted[:per_category]:
            if q not in seeds:
                seeds.append(q)
        out.append(CategoryPlan(cat_id, cat_id.replace("_", " ").title(), seeds[:6]))
    return out


def expand_seeds_with_roots(seeds: list[str], roots: list[str]) -> list[str]:
    """Long phrase seeds + root bigrams for autocomplete."""
    out = list(seeds)
    for root in roots:
        for year in ("2026", "2027"):
            out.append(f"{root} {year}")
        if root in ("printable", "pdf", "calendar"):
            out.append(f"{root} calendar 2026")
    return list(dict.fromkeys(out))[:10]
