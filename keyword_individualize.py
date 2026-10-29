"""One canonical page per distinct clipart subject — variant merge only within same subject."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from long_tail import normalize, words

# Format / intent noise — not the page topic (keep background/border — they define pages)
NOISE = frozenset({
    "free", "png", "svg", "vector", "vectors", "transparent", "download", "downloads",
    "image", "images", "picture", "pictures", "icon", "icons", "logo", "logos",
    "clip", "art", "clipart", "stock", "file", "files",
    "online", "printable", "hd", "high", "quality", "no", "with", "for", "and", "the",
    "a", "an", "of", "in", "to", "use", "using", "simple", "easy", "cute", "remover",
})

QUESTION = frozenset({"is", "can", "does", "how", "what", "when", "where", "why", "are", "do"})

GENERIC_SUBJECT = frozenset({"design", "images", "image"})


def subject_key(query: str) -> tuple[str, tuple[str, ...]]:
    w = words(query)
    if w and w[0] in QUESTION:
        return ("faq", tuple(sorted(w)))
    content = [t for t in w if t not in NOISE]
    if not content:
        content = [t for t in w if t != "clipart"]
    return ("topic", tuple(sorted(content)))


def _content_tokens_ordered(query: str) -> list[str]:
    return [t for t in words(query) if t not in NOISE and t != "clipart"]


def natural_subject_phrase(subject: tuple[str, ...], variants: list[str], scores: dict[str, int]) -> str:
    """Recover readable subject order from the best matching variant."""
    want = set(subject)
    best = max(variants, key=lambda q: (-scores.get(q, 0), -len(_content_tokens_ordered(q)), q))
    ordered = [t for t in _content_tokens_ordered(best) if t in want]
    if ordered and set(ordered) == want:
        return " ".join(ordered)
    return " ".join(subject)


def preferred_canonical(subject: tuple[str, ...], variants: list[str], scores: dict[str, int]) -> str:
    """Prefer '{subject} clipart' (school clipart, car clipart, …)."""
    subj = natural_subject_phrase(subject, variants, scores)
    ideals = (f"{subj} clipart", f"clipart {subj}")
    by_score = sorted(variants, key=lambda q: (-scores.get(q, 0), len(words(q)), q))
    for ideal in ideals:
        n = normalize(ideal)
        for v in by_score:
            if normalize(v) == n:
                return v
    for v in by_score:
        if len(words(v)) == 2 and "clipart" in words(v):
            return v
    return by_score[0]


def classify_page(subject: tuple[str, ...], canonical: str) -> str:
    if len(subject) == 1:
        if subject[0] in GENERIC_SUBJECT:
            return "hub"
        return "gallery"
    if len(words(canonical)) >= 4:
        return "long_tail"
    return "topic"


def review_status(subject: tuple[str, ...], variant_count: int, page_type: str) -> str:
    if not subject:
        return "reject_empty"
    if page_type == "hub" and variant_count >= 5:
        return "ok_hub"
    if len(subject) == 1 and len(subject[0]) <= 2 and not subject[0].isdigit():
        return "review_short_token"
    return "ok"


def individualize(rows: list[dict]) -> list[dict]:
    scores = {r["query"]: int(r.get("score") or 0) for r in rows}
    groups: dict[tuple, list[str]] = defaultdict(list)
    for r in rows:
        q = r["query"].strip()
        if not q:
            continue
        groups[subject_key(q)].append(q)

    out: list[dict] = []
    cluster_id = 0
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        kind, subject = key
        variants = list(dict.fromkeys(groups[key]))
        cluster_id += 1
        canonical = preferred_canonical(subject, variants, scores)
        subj_label = natural_subject_phrase(subject, variants, scores) if kind == "topic" else ""
        page_type = "faq" if kind == "faq" else classify_page(subject, canonical)
        status = "ok_faq" if kind == "faq" else review_status(subject, len(variants), page_type)
        best_score = max(scores.get(v, 0) for v in variants)
        page_title = canonical
        if kind == "topic" and subj_label:
            page_title = f"{subj_label} clipart"
        slug = normalize(page_title).replace(" ", "-") if page_title else ""
        out.append({
            "cluster_id": cluster_id,
            "kind": kind,
            "subject": subj_label,
            "slug": slug,
            "page_title": page_title,
            "canonical_query": canonical,
            "variant_count": len(variants),
            "variants": " | ".join(sorted(variants, key=lambda v: -scores.get(v, 0))),
            "page_type": page_type,
            "review_status": status,
            "score": best_score,
        })
    out.sort(key=lambda r: (-r["score"], r["canonical_query"]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", type=Path, default=Path("downloads/keywords_clipart_20261025-210147.csv"))
    parser.add_argument("--out", type=Path, default=Path("downloads/keywords_clipart_individual.csv"))
    args = parser.parse_args()

    rows = list(csv.DictReader(args.inp.open(encoding="utf-8")))
    items = individualize(rows)
    fields = [
        "cluster_id", "kind", "subject", "slug", "page_title", "canonical_query", "page_type",
        "review_status", "variant_count", "score", "variants",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(items)

    publish = [i for i in items if i["review_status"].startswith("ok")]
    pub_path = args.out.with_name("keywords_clipart_pages.csv")
    with pub_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(publish)

    meta = {
        "source": str(args.inp),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "input_rows": len(rows),
        "clusters": len(items),
        "publish_rows": len(publish),
        "topic_gallery": sum(1 for i in items if i["page_type"] == "gallery"),
        "topic_long_tail": sum(1 for i in items if i["page_type"] == "long_tail"),
        "faq": sum(1 for i in items if i["page_type"] == "faq"),
        "hubs": sum(1 for i in items if i["page_type"] == "hub"),
    }
    meta_path = args.out.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(json.dumps(meta, indent=2))
    print(f"wrote {args.out}")
    print(f"wrote {pub_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
