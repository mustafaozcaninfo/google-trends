"""Smart volumetric keyword mining — A–Z, digits, intent probes, queued expansion."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from google_autocomplete import AutocompleteService
from long_tail import normalize, words
from long_tail_discover import (
    accept_autocomplete_suggestion,
    build_intent_probes,
    build_probes,
    dedupe_rows,
    extends_seed,
    is_junk_autocomplete,
    specificity_score,
)

_YEAR = re.compile(r"\b20\d{2}\b")


def _mine_score(query: str, *, relevance: int) -> int:
    w = words(query)
    score = relevance + specificity_score(query) * 3
    if len(w) >= 3:
        score += 25
    if len(w) >= 4:
        score += 20
    if _YEAR.search(query):
        score += 15
    if any(t in w for t in ("free", "png", "svg", "vector", "transparent", "printable", "download")):
        score += 12
    return score


def _accept(query: str, *, root_seed: str, min_words: int, relevance: int) -> bool:
    if is_junk_autocomplete(query):
        return False
    if normalize(query) == normalize(root_seed):
        return False
    if not extends_seed(query, root_seed):
        return False
    if len(words(query)) < min_words:
        return False
    return accept_autocomplete_suggestion(
        query,
        seed=root_seed,
        min_words=min_words,
        min_relevance=0,
        relevance=relevance,
    )


def _collect_from_probe(
    ac: AutocompleteService,
    probe: str,
    source: str,
    *,
    root_seed: str,
    min_words: int,
    hl: str,
    gl: str,
    depth: int,
    seen: set[str],
    out: list[dict],
) -> None:
    result = ac._get_resilient(probe, hl=hl, gl=gl)
    for sug in result.suggestions:
        q = sug.text.strip()
        key = normalize(q)
        if not key or key in seen:
            continue
        if not _accept(q, root_seed=root_seed, min_words=min_words, relevance=sug.relevance):
            continue
        seen.add(key)
        out.append({
            "query": q,
            "seed": root_seed,
            "source": source,
            "probe": probe,
            "depth": depth,
            "relevance": sug.relevance,
            "score": _mine_score(q, relevance=sug.relevance),
        })


def _pick_queue_terms(rows: list[dict], *, limit: int, root_seed: str) -> list[str]:
    ranked = sorted(rows, key=lambda r: (-r.get("score", 0), -r.get("relevance", 0)))
    picked: list[str] = []
    seen: set[str] = set()
    for row in ranked:
        q = row["query"].strip()
        key = normalize(q)
        if key in seen or key == normalize(root_seed):
            continue
        # Prefer alphabet/digit/int discoveries and 2+ word phrases
        src = row.get("source") or ""
        if src == "seed" and len(words(q)) < 3:
            continue
        seen.add(key)
        picked.append(q)
        if len(picked) >= limit:
            break
    return picked


def mine_keywords(
    seed: str,
    *,
    cache_dir: Path,
    hl: str = "en",
    gl: str = "us",
    min_words: int = 2,
    queue_rounds: int = 2,
    queue_breadth: int = 28,
    min_interval: float = 0.45,
    alphabet: bool = True,
    digits: bool = True,
    question_prefixes: bool = True,
    intent_probes: bool = True,
) -> tuple[list[dict], dict]:
    seed = " ".join(seed.split())
    ac = AutocompleteService(cache_dir / "autocomplete.sqlite3", min_interval=min_interval)
    seen: set[str] = set()
    rows: list[dict] = []
    stats = {
        "probes": 0,
        "phases": [],
        "unique": 0,
    }

    probes: list[tuple[str, str]] = build_probes(
        seed,
        alphabet=alphabet,
        question_prefixes=question_prefixes,
        tail_space=True,
        digits=digits,
    )
    if intent_probes:
        probes.extend(build_intent_probes(seed))

    for probe, source in probes:
        stats["probes"] += 1
        _collect_from_probe(
            ac, probe, source,
            root_seed=seed, min_words=min_words, hl=hl, gl=gl, depth=0,
            seen=seen, out=rows,
        )

    stats["phases"].append({"name": "base", "rows": len(rows)})

    frontier = _pick_queue_terms(rows, limit=queue_breadth, root_seed=seed)
    for round_i in range(queue_rounds):
        if not frontier:
            break
        added_before = len(rows)
        next_frontier: list[str] = []
        for term in frontier:
            stats["probes"] += 1
            _collect_from_probe(
                ac, term + " ", f"q{round_i + 1}:tail",
                root_seed=seed, min_words=min_words, hl=hl, gl=gl, depth=round_i + 1,
                seen=seen, out=rows,
            )
            # Second hop on promising 3+ word terms only
            if len(words(term)) >= 3 and round_i == 0:
                stats["probes"] += 1
                _collect_from_probe(
                    ac, term, f"q{round_i + 1}:term",
                    root_seed=seed, min_words=min_words, hl=hl, gl=gl, depth=round_i + 1,
                    seen=seen, out=rows,
                )
        stats["phases"].append({
            "name": f"queue_{round_i + 1}",
            "frontier": len(frontier),
            "added": len(rows) - added_before,
        })
        fresh = rows[added_before:]
        next_frontier = _pick_queue_terms(fresh, limit=max(12, queue_breadth // 2), root_seed=seed)
        frontier = next_frontier

    deduped = dedupe_rows(rows)
    for row in deduped:
        row["score"] = _mine_score(row["query"], relevance=row.get("relevance", 0))
    deduped.sort(key=lambda r: (-r["score"], -r.get("relevance", 0), r["query"]))
    stats["unique"] = len(deduped)
    return deduped, stats


def export_rows(rows: list[dict], out_base: Path) -> tuple[Path, Path]:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")
    fields = ["query", "score", "relevance", "source", "depth", "probe", "seed"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine unique long-tail keywords for a seed.")
    parser.add_argument("seed", help="Root seed, e.g. clipart")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    parser.add_argument("--min-words", type=int, default=2)
    parser.add_argument("--queue-rounds", type=int, default=2)
    parser.add_argument("--queue-breadth", type=int, default=28)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = normalize(args.seed).replace(" ", "-") or "seed"
    out_base = args.out or Path("downloads") / f"keywords_{slug}_{stamp}"

    t0 = time.time()
    rows, stats = mine_keywords(
        args.seed,
        cache_dir=args.cache_dir,
        min_words=args.min_words,
        queue_rounds=args.queue_rounds,
        queue_breadth=args.queue_breadth,
    )
    csv_path, json_path = export_rows(rows, out_base)
    elapsed = time.time() - t0
    print(f"seed={args.seed!r} unique={stats['unique']} probes={stats['probes']} elapsed={elapsed:.1f}s")
    print(f"phases={stats['phases']}")
    print(f"csv={csv_path}")
    print(f"json={json_path}")
    print("top20:")
    for row in rows[:20]:
        print(f"  {row['score']:4d} | {row['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
