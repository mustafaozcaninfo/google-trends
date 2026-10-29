"""Fresh Calendars News post slugs from sitemap (duplicate guard)."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

POST_SITEMAP = "https://freshcalendars.com/news/post-sitemap.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def slug_from_loc(loc: str) -> str:
    parts = [p for p in urlparse(loc).path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "news":
        return parts[1]
    return parts[-1] if parts else ""


def fetch_post_slugs(timeout: float = 30.0) -> set[str]:
    response = requests.get(POST_SITEMAP, timeout=timeout, headers={"User-Agent": "FreshCalendarsSignalBot/1.0"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    slugs = set()
    for url in root.findall(".//sm:url", NS):
        loc = url.find("sm:loc", NS)
        if loc is None or not loc.text:
            continue
        slug = slug_from_loc(loc.text.strip())
        if slug and slug != "news":
            slugs.add(slug)
    return slugs


def query_to_slug(query: str) -> str:
    q = query.lower().strip()
    q = re.sub(r"[^a-z0-9\s-]", "", q)
    q = re.sub(r"\s+", "-", q)
    return q.strip("-")


def match_published(query: str, slugs: set[str]) -> str | None:
    """Return matching slug if query likely already covered."""
    candidate = query_to_slug(query)
    if candidate in slugs:
        return candidate
    for slug in slugs:
        if candidate in slug or slug in candidate:
            if len(candidate) >= 12 or len(slug) >= 12:
                return slug
    return None


class PublishedSlugCache:
    def __init__(self, cache_file: Path, ttl: float = 21600, clock=None):
        import time
        self.cache_file = Path(cache_file)
        self.ttl = ttl
        self.clock = clock or time.time

    def load(self, *, refresh: bool = False) -> set[str]:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_file.exists() and not refresh:
            try:
                payload = json.loads(self.cache_file.read_text())
                if self.clock() - payload.get("fetched_at", 0) < self.ttl:
                    return set(payload.get("slugs", []))
            except (json.JSONDecodeError, OSError):
                pass
        slugs = sorted(fetch_post_slugs())
        self.cache_file.write_text(json.dumps({"fetched_at": self.clock(), "slugs": slugs}))
        return set(slugs)
