"""Long-tail discovery helpers — modifiers, specificity, dedupe."""

from __future__ import annotations

import re

from long_tail import words, normalize

# Probes appended to each seed (SEO autocomplete mining pattern)
ALPHA = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
QUESTION_PREFIXES = (
    "how",
    "what",
    "when",
    "where",
    "why",
    "is",
    "can",
    "does",
)

# Fresh Calendars–relevant specificity signals (US news / calendar niche)
SPECIFICITY_TOKENS = {
    "county", "zip", "deadline", "hours", "schedule", "dates", "calendar",
    "ballot", "proposition", "amendment", "district", "break", "printable",
    "pdf", "primary", "registration", "polling", "mail", "absentee",
    "sunset", "trick", "turkey", "shipping", "enrollment", "payment", "cola",
}

GENERIC_HEAD_TERMS = {
    "news", "update", "live", "video", "reddit", "twitter", "tiktok",
}

# Fresh Calendars — downloadable / year-specific content mining
CONTENT_MODIFIERS = ("printable", "pdf", "template", "free", "download")
CONTENT_YEARS = ("2026", "2027")
_CONTENT_MOD_SET = set(CONTENT_MODIFIERS)
_CONTENT_YEAR_SET = set(CONTENT_YEARS)

# High-intent autocomplete entry points (works even when holiday seed returns no PDF suggestions)
PRINTABLE_ANCHOR_SEEDS = (
    "printable calendar 2026",
    "printable calendar 2027",
    "calendar 2026 pdf",
    "calendar 2027 pdf",
    "free printable calendar 2026",
    "free printable calendar 2027",
)
_ANCHOR_SEED_KEYS = {normalize(s) for s in PRINTABLE_ANCHOR_SEEDS}

_JUNK_URL = re.compile(r"https?://|\bwww\.", re.I)
_JUNK_DOMAIN = re.compile(r"\b[a-z0-9][-a-z0-9]*\.(com|org|net|io|gov|edu)\b", re.I)


def build_probes(
    seed: str,
    *,
    alphabet: bool,
    question_prefixes: bool,
    tail_space: bool,
    digits: bool = False,
) -> list[tuple[str, str]]:
    seed = " ".join(seed.split())
    if not seed:
        return []
    probes: list[tuple[str, str]] = [(seed, "seed")]
    if tail_space:
        probes.append((seed + " ", "tail"))
    if question_prefixes:
        for prefix in QUESTION_PREFIXES:
            probes.append((f"{prefix} {seed}", f"q:{prefix}"))
    base = seed if seed.endswith(" ") else seed + " "
    if alphabet:
        for letter in ALPHA:
            probes.append((base + letter, f"a:{letter}"))
    if digits:
        for digit in DIGITS:
            probes.append((base + digit, f"n:{digit}"))
    return probes


# High-intent entry probes (clipart / stock / template niches)
INTENT_MODIFIER_PROBES = (
    "free",
    "png",
    "transparent",
    "vector",
    "svg",
    "cute",
    "cartoon",
    "black and white",
    "download",
    "school",
    "teacher",
    "christmas",
    "halloween",
    "birthday",
    "thanksgiving",
    "easter",
    "valentine",
    "animal",
    "flower",
    "background",
    "border",
    "frame",
    "logo",
    "icon",
)


def build_intent_probes(seed: str) -> list[tuple[str, str]]:
    """Prefix/suffix modifiers that surface download & seasonal clusters."""
    seed = " ".join(seed.split())
    if not seed:
        return []
    probes: list[tuple[str, str]] = []
    seen: set[str] = set()
    for mod in INTENT_MODIFIER_PROBES:
        for q, tag in (
            (f"{mod} {seed}", f"int:{mod}"),
            (f"{seed} {mod}", f"int_r:{mod}"),
            (f"{seed} {mod} ", f"int_t:{mod}"),
        ):
            key = normalize(q)
            if key not in seen:
                seen.add(key)
                probes.append((q, tag))
    return probes


def build_modifier_probes(seed: str) -> list[tuple[str, str]]:
    """Probes for printable / PDF / 2026–2027 intent (no A–Z — fewer API calls)."""
    seed = " ".join(seed.split())
    if not seed:
        return []
    probes: list[tuple[str, str]] = [(seed, "seed")]
    probes.append((seed + " ", "tail"))
    for mod in CONTENT_MODIFIERS:
        probes.append((f"{seed} {mod}", f"mod:{mod}"))
        probes.append((f"{mod} {seed}", f"modr:{mod}"))
    for year in CONTENT_YEARS:
        probes.append((f"{seed} {year}", f"yr:{year}"))
        probes.append((f"{seed} calendar {year}", f"yr_cal:{year}"))
        for mod in ("printable", "pdf", "free"):
            probes.append((f"{seed} {mod} {year}", f"mod_yr:{mod}:{year}"))
            probes.append((f"{mod} {seed} {year}", f"modr_yr:{mod}:{year}"))
            probes.append((f"free printable {seed} {year}", f"fp:{year}"))
    # Generic calendar hooks when seed is short / root-like
    if len(words(seed)) <= 2:
        for year in CONTENT_YEARS:
            for mod in ("printable", "pdf"):
                probes.append((f"{mod} calendar {year}", f"cal:{mod}:{year}"))
                probes.append((f"{seed} {mod} calendar {year}", f"cal_seed:{mod}:{year}"))
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for q, tag in probes:
        key = normalize(q)
        if key not in seen:
            seen.add(key)
            out.append((q, tag))
    return out


def has_printable_content_intent(query: str) -> bool:
    w = set(words(query))
    if not (w & _CONTENT_MOD_SET):
        return False
    if w & _CONTENT_YEAR_SET:
        return True
    if w & {"calendar", "schedule", "dates", "monthly", "holiday", "holidays"}:
        return True
    return len(w) >= 4


def matches_modifier_mining(query: str, seed: str) -> bool:
    """Suggestion fits printable/PDF/year mining for this seed."""
    if not has_printable_content_intent(query):
        return False
    if extends_seed(query, seed):
        return True
    w = set(words(query))
    if w & seed_anchor(seed):
        return True
    # e.g. seed "thanksgiving 2026" → allow "printable calendar 2026 november"
    if w & _CONTENT_YEAR_SET and (w & {"calendar", "thanksgiving", "holiday"} or seed_anchor(seed) & w):
        return True
    return False


def accept_modifier_suggestion(
    text: str,
    *,
    seed: str,
    min_words: int,
    min_relevance: int,
    relevance: int,
) -> bool:
    if relevance < min_relevance:
        return False
    if is_junk_autocomplete(text):
        return False
    if not is_long_tail_candidate(text, min_words=min_words):
        return False
    if normalize(text) == normalize(seed):
        return False
    if normalize(seed) in _ANCHOR_SEED_KEYS:
        return has_printable_content_intent(text)
    return matches_modifier_mining(text, seed)


def seed_anchor(seed: str) -> set[str]:
    """Core tokens from seed (ignore bare years for matching)."""
    anchor = {w for w in words(seed) if not re.fullmatch(r"20\d{2}", w) and len(w) > 1}
    if not anchor:
        anchor = {w for w in words(seed) if len(w) > 1}
    return anchor


def extends_seed(suggestion: str, seed: str) -> bool:
    anchor = seed_anchor(seed)
    if not anchor:
        return False
    return anchor <= set(words(suggestion))


def is_junk_autocomplete(query: str) -> bool:
    """Drop URL-like suggestions that are not editorial queries."""
    raw = (query or "").strip()
    if not raw:
        return True
    if _JUNK_URL.search(raw):
        return True
    if _JUNK_DOMAIN.search(raw) and " " not in raw.strip():
        return True
    return False


def accept_autocomplete_suggestion(
    text: str,
    *,
    seed: str,
    min_words: int,
    min_relevance: int,
    relevance: int,
) -> bool:
    if relevance < min_relevance:
        return False
    if is_junk_autocomplete(text):
        return False
    if not extends_seed(text, seed):
        return False
    if not is_long_tail_candidate(text, min_words=min_words):
        return False
    if normalize(text) == normalize(seed):
        return False
    return True


def is_long_tail_candidate(query: str, *, min_words: int = 3) -> bool:
    w = words(query)
    if len(w) < min_words:
        return False
    if set(w) & GENERIC_HEAD_TERMS and len(w) <= 4:
        return False
    return True


def specificity_score(query: str) -> int:
    tokens = set(words(query))
    score = 0
    score += min(len(tokens), 8) * 2
    score += 8 * len(tokens & SPECIFICITY_TOKENS)
    if re.search(r"\b20\d{2}\b", query):
        score += 4
    if re.search(r"\b\d{5}\b", query):
        score += 6
    return score


def dedupe_rows(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        key = normalize(row["query"])
        prev = best.get(key)
        if prev is None or row.get("relevance", 0) > prev.get("relevance", 0):
            best[key] = row
        elif prev is not None:
            prev.setdefault("probes", [])
            row_probes = row.get("probe") or row.get("source")
            if row_probes and row_probes not in prev.get("probes", []):
                prev.setdefault("probes", []).append(row_probes)
    return list(best.values())
