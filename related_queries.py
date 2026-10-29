"""Bounded Explore requests with persistent cache and a shared cooldown."""
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import json
import sqlite3
import time
from urllib.parse import urlencode


@dataclass
class RelatedResult:
    data: dict | None
    fetched_at: float | None = None
    cached: bool = False
    stale: bool = False
    retry_after: int = 0
    message: str = ""


def explore_url(keyword, geo, timeframe):
    return "https://trends.google.com/trends/explore?" + urlencode(
        {"q": keyword, "geo": geo, "date": timeframe, "hl": "en"}
    )


def fetch_explore(keyword, geo, timeframe):
    from trendspyg import download_google_trends_explore
    # A real Explore session replaces trendspy's quota-prone embed endpoint.
    # No proxy rotation or repeated requests after Google's hard refusal.
    return download_google_trends_explore(
        keyword, geo=geo, timeframe=timeframe, include_related=True,
        include_geo=False, engine="browser", max_retries=2, retry_wait=8.0,
        cache=False,
    )


class RelatedQueriesService:
    def __init__(self, db_path, fetch=fetch_explore, clock=time.time):
        self.db_path = Path(db_path)
        self.fetch = fetch
        self.clock = clock
        self.lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, fetched REAL, data TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value REAL)")

    def _db(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def peek(self, keyword, geo, timeframe):
        """Read existing results without issuing a request or consuming cooldown."""
        key = json.dumps([keyword.strip(), geo.strip().upper(), timeframe.strip()])
        with self._db() as db:
            row = db.execute("SELECT fetched, data FROM results WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        ttl = 3600 if timeframe.strip().startswith("now ") else 86400
        return RelatedResult(json.loads(row[1]), row[0], cached=True,
                             stale=self.clock() - row[0] >= ttl)

    def get(self, keyword, geo, timeframe):
        keyword, geo, timeframe = keyword.strip(), geo.strip().upper(), timeframe.strip()
        if not keyword:
            raise ValueError("En az bir keyword gir.")
        key = json.dumps([keyword, geo, timeframe])
        ttl = 3600 if timeframe.startswith("now ") else 86400
        with self.lock, self._db() as db:
            now = self.clock()
            row = db.execute("SELECT fetched, data FROM results WHERE key=?", (key,)).fetchone()
            cached = json.loads(row[1]) if row else None
            if row and now - row[0] < ttl:
                return RelatedResult(cached, row[0], cached=True)
            state = dict(db.execute("SELECT key, value FROM state"))
            wait = max(0, int(state.get("retry_at", 0) - now + 0.999))
            if wait:
                return self._unavailable(row, cached, wait)
            try:
                envelope = self.fetch(keyword, geo, timeframe)
                related = envelope.get("related_queries")
                if not isinstance(related, dict) or not all(
                    isinstance(related.get(part), list) for part in ("top", "rising")
                ):
                    raise ValueError("Unexpected related queries response")
                fetched = self.clock()
                # A missing widget is not evidence that no related searches exist.
                # Don't replace useful saved data with an empty best-effort widget.
                if not related["top"] and not related["rising"]:
                    db.execute("INSERT OR REPLACE INTO state VALUES ('retry_at', ?)", (fetched + 120,))
                    result = self._unavailable(row, cached, 120)
                    result.message = "Google bu seçim için ilgili sorgu verisi döndürmedi. Veri azlığı veya geçici erişim kısıtı olabilir."
                    return result
                db.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?)",
                           (key, fetched, json.dumps(related)))
                # Space distinct browser sessions, even for different keywords.
                db.execute("INSERT OR REPLACE INTO state VALUES ('retry_at', ?)", (fetched + 30,))
                return RelatedResult(related, fetched)
            except Exception as exc:
                from trendspyg.exceptions import RateLimitError
                quota = isinstance(exc, RateLimitError) or getattr(
                    getattr(exc, "response", None), "status_code", None
                ) in (403, 429)
                delay = 1800 if quota else 120
                db.execute("INSERT OR REPLACE INTO state VALUES ('retry_at', ?)", (self.clock() + delay,))
                result = self._unavailable(row, cached, delay)
                result.message = (
                    "Google istekleri geçici olarak sınırladı. Otomatik tekrar durduruldu."
                    if quota else
                    "Google Trends verisine erişilemedi. Chrome kurulumunu ve internet bağlantısını kontrol edin."
                )
                return result

    @staticmethod
    def _unavailable(row, cached, wait):
        # Old data is always labelled; never serve another filter's result.
        usable = row is not None and cached is not None
        return RelatedResult(cached if usable else None, row[0] if usable else None,
                             cached=usable, stale=usable, retry_after=wait,
                             message="Yeni istekler kısa süreliğine bekletiliyor.")
