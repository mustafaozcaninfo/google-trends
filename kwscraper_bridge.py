"""Batch A–Z autocomplete via kwscraper (seo-keyword-scraper) — no Chrome."""

from __future__ import annotations

from long_tail_discover import accept_autocomplete_suggestion, dedupe_rows


def harvest_alpha_rows(
    seeds: list[str],
    *,
    lang: str = "en",
    country: str = "us",
    min_words: int = 3,
    sleep_between: float = 0.15,
) -> tuple[list[dict], dict]:
    """
    For each seed, fetch Google suggest for seed + seed + a..z.
    Returns motor_scan-compatible autocomplete rows.
    """
    from kwscraper.suggest import fetch_with_alpha

    stats = {
        "probes": 0,
        "live_fetches": 0,
        "suggestions_kept": 0,
        "seeds": len(seeds),
        "source": "kwscraper",
    }
    rows: list[dict] = []

    for seed in seeds:
        seed = seed.strip()
        if not seed:
            continue
        stats["probes"] += 27  # base + 26 letters
        pairs = fetch_with_alpha(
            seed,
            lang=lang,
            country=country.lower(),
            sleep_between=sleep_between,
            sort=True,
        )
        stats["live_fetches"] += 27
        for _seed_tag, keyword in pairs:
            if not accept_autocomplete_suggestion(
                keyword,
                seed=seed,
                min_words=min_words,
                min_relevance=0,
                relevance=50,
            ):
                continue
            stats["suggestions_kept"] += 1
            rows.append({
                "query": keyword,
                "seed": seed,
                "probe": f"alpha:{seed}",
                "source": "kwscraper:alpha",
                "depth": 1,
                "relevance": 50,
            })

    return dedupe_rows(rows), stats
