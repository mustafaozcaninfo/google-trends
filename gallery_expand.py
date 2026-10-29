"""Expand gallery list — autocomplete A–Z + digits per seed (same logic as root mine)."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google_autocomplete import AutocompleteService
from keyword_mine import _mine_score
from long_tail import normalize, words
from long_tail_discover import (
    accept_autocomplete_suggestion,
    build_probes,
    dedupe_rows,
    extends_seed,
    is_junk_autocomplete,
)
from keyword_individualize import NOISE, subject_key


def load_gallery_seeds(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _accept_gallery_expand(query: str, *, root_seed: str, min_words: int, relevance: int) -> bool:
    """Keep seed-specific tails plus new subjects still tied to clipart autocomplete."""
    if is_junk_autocomplete(query):
        return False
    if "clipart" not in words(query):
        return False
    if len(words(query)) < min_words:
        return False
    if normalize(query) == normalize(root_seed):
        return False
    if extends_seed(query, root_seed):
        return accept_autocomplete_suggestion(
            query, seed=root_seed, min_words=min_words, min_relevance=0, relevance=relevance,
        )
    if extends_seed(query, "clipart"):
        return accept_autocomplete_suggestion(
            query, seed="clipart", min_words=min_words, min_relevance=0, relevance=relevance,
        )
    return False


def _collect_probe(
    ac: AutocompleteService,
    probe: str,
    source: str,
    *,
    root_seed: str,
    min_words: int,
    hl: str,
    gl: str,
    seen: set[str],
    out: list[dict],
) -> None:
    result = ac._get_resilient(probe, hl=hl, gl=gl)
    for sug in result.suggestions:
        q = sug.text.strip()
        key = normalize(q)
        if not key or key in seen:
            continue
        if not _accept_gallery_expand(q, root_seed=root_seed, min_words=min_words, relevance=sug.relevance):
            continue
        seen.add(key)
        out.append({
            "query": q,
            "seed": root_seed,
            "source": source,
            "probe": probe,
            "depth": 1,
            "relevance": sug.relevance,
            "score": _mine_score(q, relevance=sug.relevance),
        })


def mine_gallery_seeds(
    seeds: list[str],
    *,
    cache_dir: Path,
    hl: str = "en",
    gl: str = "us",
    min_words: int = 2,
    min_interval: float = 0.35,
    alphabet: bool = True,
    digits: bool = True,
    checkpoint: Path | None = None,
    checkpoint_every: int = 20,
) -> tuple[list[dict], dict]:
    ac = AutocompleteService(cache_dir / "autocomplete.sqlite3", min_interval=min_interval)
    seen: set[str] = set()
    rows: list[dict] = []
    stats = {"seeds": 0, "probes": 0, "cached_skipped_probes": 0}

    start_idx = 0
    if checkpoint and checkpoint.exists():
        prev = json.loads(checkpoint.read_text(encoding="utf-8"))
        rows = prev.get("rows") or []
        seen = set(prev.get("seen") or [])
        start_idx = int(prev.get("next_seed_index") or 0)
        stats = prev.get("stats") or stats

    for idx, seed in enumerate(seeds):
        if idx < start_idx:
            continue
        seed = " ".join(seed.split())
        if not seed:
            continue
        stats["seeds"] += 1
        key0 = normalize(seed)
        if key0 not in seen:
            seen.add(key0)
            rows.append({
                "query": seed,
                "seed": seed,
                "source": "gallery_seed",
                "probe": seed,
                "depth": 0,
                "relevance": 600,
                "score": 600,
            })
        for probe, source in build_probes(
            seed,
            alphabet=alphabet,
            question_prefixes=False,
            tail_space=True,
            digits=digits,
        ):
            stats["probes"] += 1
            _collect_probe(
                ac, probe, f"g:{source}",
                root_seed=seed, min_words=min_words, hl=hl, gl=gl,
                seen=seen, out=rows,
            )
        if checkpoint and (idx + 1) % checkpoint_every == 0:
            checkpoint.write_text(
                json.dumps({
                    "next_seed_index": idx + 1,
                    "seen": list(seen),
                    "rows": rows,
                    "stats": stats,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
    if checkpoint and checkpoint.exists():
        checkpoint.unlink(missing_ok=True)
    return dedupe_rows(rows), stats


def discover_gallery_subjects(rows: list[dict]) -> list[dict]:
    """One row per single-token gallery subject extracted from mined queries."""
    best: dict[tuple[str, ...], dict] = {}
    for row in rows:
        kind, subject = subject_key(row["query"])
        if kind != "topic" or len(subject) != 1:
            continue
        token = subject[0]
        if token in NOISE or len(token) <= 1:
            continue
        prev = best.get(subject)
        score = int(row.get("score") or 0)
        if prev is None or score > int(prev.get("score") or 0):
            title = f"{token} clipart"
            best[subject] = {
                "page_title": title,
                "slug": normalize(title).replace(" ", "-"),
                "subject": token,
                "canonical_query": row["query"],
                "score": score,
                "source_seed": row.get("seed", ""),
            }
    out = list(best.values())
    out.sort(key=lambda r: (-r["score"], r["page_title"]))
    return out


def merge_gallery_lists(base: list[dict], discovered: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in base:
        subj = row.get("subject") or ""
        merged[subj] = {
            "page_title": row.get("page_title") or f"{subj} clipart",
            "slug": row.get("slug") or normalize(f"{subj} clipart").replace(" ", "-"),
            "subject": subj,
            "canonical_query": row.get("canonical_query") or row.get("page_title"),
            "score": int(row.get("score") or 0),
            "origin": "base416",
        }
    for row in discovered:
        subj = row["subject"]
        if subj in merged:
            continue
        row["origin"] = "autocomplete_new"
        merged[subj] = row
    out = list(merged.values())
    out.sort(key=lambda r: (-int(r.get("score") or 0), r.get("page_title") or ""))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gallery-csv",
        type=Path,
        default=Path("downloads/keywords_clipart_gallery_416.csv"),
    )
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    parser.add_argument("--limit", type=int, default=0, help="0 = all seeds")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=Path(".cache/gallery_expand_checkpoint.json"))
    args = parser.parse_args()

    meta_in = load_gallery_seeds(args.gallery_csv)
    titles = [r["page_title"] for r in meta_in if r.get("page_title")]
    if args.limit > 0:
        titles = titles[: args.limit]

    prior_subjects = {r["subject"] for r in meta_in if r.get("subject")}
    t0 = time.time()
    rows, mine_stats = mine_gallery_seeds(
        titles,
        cache_dir=args.cache_dir,
        checkpoint=args.checkpoint if args.limit == 0 else None,
    )
    discovered = discover_gallery_subjects(rows)
    merged = merge_gallery_lists(meta_in, discovered)
    new_only = [g for g in merged if g.get("origin") == "autocomplete_new"]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or Path("downloads") / f"keywords_clipart_gallery_expanded_{stamp}.csv"
    fields = [
        "page_title", "slug", "subject", "canonical_query", "score", "origin", "source_seed",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged)

    report = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(time.time() - t0, 1),
        "input_gallery_seeds": len(titles),
        "mine_stats": mine_stats,
        "raw_queries": len(rows),
        "gallery_total": len(merged),
        "gallery_base": len(meta_in),
        "gallery_new_subjects": len(new_only),
        "new_subjects_sample": [g["subject"] for g in new_only[:40]],
        "out": str(out),
    }
    report_path = out.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
