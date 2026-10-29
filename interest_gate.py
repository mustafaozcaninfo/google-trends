"""Global throttle so live Google Interest calls don't burst into 429."""

from __future__ import annotations

import json
import time
from pathlib import Path


class InterestGate:
    """Minimum spacing between uncached live Interest fetches (all scans share one file)."""

    def __init__(self, state_path: Path, *, min_interval_seconds: float = 55.0):
        self.state_path = state_path
        self.min_interval = max(10.0, min_interval_seconds)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        if not self.state_path.is_file():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.state_path.write_text(json.dumps(data), encoding="utf-8")

    def seconds_until_allowed(self) -> int:
        data = self._read()
        last = float(data.get("last_live_at") or 0)
        if last <= 0:
            return 0
        wait = self.min_interval - (time.time() - last)
        return max(0, int(wait + 0.999))

    def allow_live(self) -> bool:
        return self.seconds_until_allowed() == 0

    def mark_live(self) -> None:
        data = self._read()
        data["last_live_at"] = time.time()
        self._write(data)
