"""Google Search autocomplete via suggestqueries (unofficial).

Adapted from the public-domain patterns in:
- https://github.com/jsvine/compleat (compleat/query.py)
- https://github.com/jimkang/autocompl (autocompl.js)
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import time
from threading import Lock
import requests

from long_tail_discover import build_modifier_probes, build_probes, dedupe_rows


def _accept_suggestion(text: str, *, seed: str, min_words: int, min_relevance: int, relevance: int) -> bool:
    from long_tail_discover import accept_autocomplete_suggestion

    return accept_autocomplete_suggestion(
        text,
        seed=seed,
        min_words=min_words,
        min_relevance=min_relevance,
        relevance=relevance,
    )


def _accept_modifier(text: str, *, seed: str, min_words: int, min_relevance: int, relevance: int) -> bool:
    from long_tail_discover import accept_modifier_suggestion

    return accept_modifier_suggestion(
        text,
        seed=seed,
        min_words=min_words,
        min_relevance=min_relevance,
        relevance=relevance,
    )

SUGGEST_URL = "http://suggestqueries.google.com/complete/search"


@dataclass
class Suggestion:
    text: str
    relevance: int = 0
    suggest_type: str = ""


@dataclass
class AutocompleteResult:
    suggestions: list[Suggestion]
    fetched_at: float
    cached: bool = False
    retry_after: int = 0
    message: str = ""


def parse_chrome_payload(data) -> list[Suggestion]:
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return []
    texts = data[1]
    meta = data[4] if len(data) > 4 and isinstance(data[4], dict) else {}
    types = meta.get("google:suggesttype") or []
    rels = meta.get("google:suggestrelevance") or []
    out: list[Suggestion] = []
    for i, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
        rel = rels[i] if i < len(rels) and isinstance(rels[i], int) else max(0, 600 - i * 10)
        st = types[i] if i < len(types) and isinstance(types[i], str) else ""
        out.append(Suggestion(text.strip(), rel, st))
    return out


def fetch_suggestions(
    query: str,
    *,
    hl: str = "en",
    gl: str = "us",
    client: str = "chrome",
    timeout: float = 12.0,
) -> list[Suggestion]:
    query = " ".join(str(query).split())
    if not query:
        return []
    response = requests.get(
        SUGGEST_URL,
        params={"client": client, "hl": hl, "gl": gl.lower(), "q": query},
        timeout=timeout,
    )
    if response.status_code in (403, 429):
        raise RuntimeError("Google autocomplete rate-limited")
    response.raise_for_status()
    return parse_chrome_payload(response.json())


class AutocompleteService:
    """Cached autocomplete with a short global cooldown between live requests."""

    def __init__(self, db_path, fetch=fetch_suggestions, clock=time.time, min_interval=1.5, ttl=21600):
        self.db_path = db_path
        self.fetch = fetch
        self.clock = clock
        self.min_interval = min_interval
        self.ttl = ttl
        self.lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS suggestions "
                "(key TEXT PRIMARY KEY, fetched REAL, data TEXT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value REAL)")

    def _db(self):
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _key(query: str, hl: str, gl: str) -> str:
        return json.dumps([" ".join(query.split()), hl.lower(), gl.lower()])

    def get(self, query: str, hl: str = "en", gl: str = "us") -> AutocompleteResult:
        key = self._key(query, hl, gl)
        with self.lock, self._db() as db:
            now = self.clock()
            row = db.execute("SELECT fetched, data FROM suggestions WHERE key=?", (key,)).fetchone()
            if row and now - row[0] < self.ttl:
                items = [Suggestion(**item) for item in json.loads(row[1])]
                return AutocompleteResult(items, row[0], cached=True)
            state = dict(db.execute("SELECT key, value FROM state"))
            wait = max(0, int(state.get("retry_at", 0) - now + 0.999))
            if wait:
                if row:
                    items = [Suggestion(**item) for item in json.loads(row[1])]
                    return AutocompleteResult(
                        items, row[0], cached=True, retry_after=wait,
                        message="Autocomplete istekleri kısa süre bekletiliyor.",
                    )
                return AutocompleteResult([], None, retry_after=wait,
                                          message="Autocomplete bekletiliyor; önbellek yok.")
            try:
                items = self.fetch(query, hl=hl, gl=gl)
                fetched = self.clock()
                payload = [{"text": s.text, "relevance": s.relevance, "suggest_type": s.suggest_type} for s in items]
                db.execute(
                    "INSERT OR REPLACE INTO suggestions VALUES (?, ?, ?)",
                    (key, fetched, json.dumps(payload)),
                )
                db.execute("INSERT OR REPLACE INTO state VALUES ('retry_at', ?)", (fetched + self.min_interval,))
                return AutocompleteResult(items, fetched)
            except Exception as exc:
                delay = 45 if "rate" in str(exc).lower() or "429" in str(exc) else 90
                db.execute("INSERT OR REPLACE INTO state VALUES ('retry_at', ?)", (self.clock() + delay,))
                if row:
                    items = [Suggestion(**item) for item in json.loads(row[1])]
                    return AutocompleteResult(
                        items, row[0], cached=True, retry_after=delay,
                        message=f"Canlı autocomplete alınamadı: {exc}",
                    )
                return AutocompleteResult([], None, retry_after=delay, message=str(exc))

    def discover_long_tail(
        self,
        seeds: list[str],
        *,
        hl: str = "en",
        gl: str = "us",
        alphabet: bool = True,
        question_prefixes: bool = True,
        tail_space: bool = True,
        min_words: int = 3,
        min_relevance: int = 0,
        digits: bool = False,
    ) -> tuple[list[dict], dict]:
        """Mine Search autocomplete: seed, trailing space, a–z, digits, question prefixes."""
        rows: list[dict] = []
        stats = {
            "probes": 0,
            "live_fetches": 0,
            "cached_hits": 0,
            "throttled_probes": 0,
            "suggestions_kept": 0,
            "message": "",
        }
        for seed in seeds:
            seed = seed.strip()
            if not seed:
                continue
            for probe, source in build_probes(
                seed,
                alphabet=alphabet,
                question_prefixes=question_prefixes,
                tail_space=tail_space,
                digits=digits,
            ):
                stats["probes"] += 1
                result = self._get_resilient(probe, hl=hl, gl=gl)
                if result.cached:
                    stats["cached_hits"] += 1
                elif result.suggestions or not result.retry_after:
                    stats["live_fetches"] += 1
                if result.retry_after and not result.suggestions:
                    stats["throttled_probes"] += 1
                    if result.message and not stats["message"]:
                        stats["message"] = result.message
                for sug in result.suggestions:
                    if not _accept_suggestion(
                        sug.text,
                        seed=seed,
                        min_words=min_words,
                        min_relevance=min_relevance,
                        relevance=sug.relevance,
                    ):
                        continue
                    stats["suggestions_kept"] += 1
                    rows.append({
                        "query": sug.text,
                        "seed": seed,
                        "probe": probe,
                        "source": source,
                        "depth": 1,
                        "relevance": sug.relevance,
                    })
        return dedupe_rows(rows), stats

    def _get_resilient(self, query: str, *, hl: str, gl: str, attempts: int = 4) -> AutocompleteResult:
        result = self.get(query, hl=hl, gl=gl)
        tries = 0
        while result.retry_after and not result.suggestions and tries < attempts:
            time.sleep(min(result.retry_after, 45))
            result = self.get(query, hl=hl, gl=gl)
            tries += 1
        return result

    def discover_modifier_content(
        self,
        seeds: list[str],
        *,
        hl: str = "en",
        gl: str = "us",
        min_words: int = 3,
        min_relevance: int = 0,
    ) -> tuple[list[dict], dict]:
        """Printable / PDF / 2026–2027 probes — FC downloadable content angles."""
        rows: list[dict] = []
        stats = {
            "probes": 0,
            "live_fetches": 0,
            "cached_hits": 0,
            "throttled_probes": 0,
            "suggestions_kept": 0,
            "message": "",
        }
        for seed in seeds:
            seed = seed.strip()
            if not seed:
                continue
            for probe, source in build_modifier_probes(seed):
                stats["probes"] += 1
                result = self.get(probe, hl=hl, gl=gl)
                if result.cached:
                    stats["cached_hits"] += 1
                elif result.suggestions or not result.retry_after:
                    stats["live_fetches"] += 1
                if result.retry_after and not result.suggestions:
                    stats["throttled_probes"] += 1
                    if result.message and not stats["message"]:
                        stats["message"] = result.message
                for sug in result.suggestions:
                    if not _accept_modifier(
                        sug.text,
                        seed=seed,
                        min_words=min_words,
                        min_relevance=min_relevance,
                        relevance=sug.relevance,
                    ):
                        continue
                    stats["suggestions_kept"] += 1
                    rows.append({
                        "query": sug.text,
                        "seed": seed,
                        "probe": probe,
                        "source": source,
                        "depth": 1,
                        "relevance": sug.relevance,
                    })
        return dedupe_rows(rows), stats

    def expand(
        self,
        seeds: list[str],
        *,
        hl: str = "en",
        gl: str = "us",
        depth: int = 1,
        max_children: int = 3,
        min_words: int = 3,
        filter_seeds: list[str] | None = None,
    ) -> list[dict]:
        """Breadth-first: each seed → suggestions; optional second hop on top-N children."""
        def norm(q: str) -> str:
            return " ".join(q.lower().split())

        anchor_seeds = [s.strip() for s in (filter_seeds or seeds) if s.strip()]
        fetched: set[str] = set()
        rows: list[dict] = []
        queue: list[tuple[str, str, int]] = [(s.strip(), s.strip(), 0) for s in seeds if s.strip()]

        while queue:
            term, root_seed, level = queue.pop(0)
            n = norm(term)
            if not n or n in fetched:
                continue
            fetched.add(n)
            result = self.get(term, hl=hl, gl=gl)
            parent_label = root_seed or term
            for rank, sug in enumerate(result.suggestions):
                sn = norm(sug.text)
                if not sn or sn == n:
                    continue
                if anchor_seeds and not any(
                    _accept_suggestion(
                        sug.text,
                        seed=s,
                        min_words=min_words,
                        min_relevance=0,
                        relevance=sug.relevance,
                    )
                    for s in anchor_seeds
                ):
                    continue
                rows.append({
                    "query": sug.text,
                    "seed": root_seed,
                    "parent": parent_label if level == 0 else term,
                    "depth": level + 1,
                    "relevance": sug.relevance,
                    "source": "autocomplete",
                })
                if level + 1 < depth and rank < max_children and sn not in fetched:
                    queue.append((sug.text, root_seed, level + 1))
        return dedupe_rows(rows)


def normalize_query(q: str) -> str:
    return " ".join(q.lower().split())
