"""Disk cache for trendspy interest_over_time batches (reduces 429 on rerun)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


def _ttl_seconds(timeframe: str) -> int:
    return 3600 if (timeframe or "").strip().lower().startswith("now ") else 86400


def _batch_key(geo: str, timeframe: str, batch: list[str]) -> str:
    payload = f"{geo.upper()}|{timeframe}|" + "|".join(sorted(q.strip().lower() for q in batch if q.strip()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class InterestCache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interest_batch (
                    key TEXT PRIMARY KEY,
                    geo TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    fetched_at REAL NOT NULL,
                    ttl INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def get(self, geo: str, timeframe: str, batch: list[str]) -> dict | None:
        key = _batch_key(geo, timeframe, batch)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT fetched_at, ttl, payload FROM interest_batch WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        fetched_at, ttl, payload = row
        if time.time() - fetched_at > ttl:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, geo: str, timeframe: str, batch: list[str], payload: dict) -> None:
        key = _batch_key(geo, timeframe, batch)
        ttl = _ttl_seconds(timeframe)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO interest_batch (key, geo, timeframe, fetched_at, ttl, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (key, geo.upper(), timeframe, time.time(), ttl, json.dumps(payload)),
            )
