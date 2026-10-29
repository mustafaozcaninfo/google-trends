"""One-click seed packs for Fresh Calendars News (US English)."""

# Sidebar: scan only user-typed seeds (no pack injection).
MOTOR_FREE = "— Serbest kelime (paket yok) —"

MOTORS = {
    "Election & civic": [
        "election day 2026",
        "early voting 2026",
        "sample ballot 2026",
    ],
    "Holidays & dates": [
        "thanksgiving 2026",
        "halloween 2026",
        "daylight saving time 2026",
    ],
    "Retail & shipping": [
        "black friday 2026",
        "usps holiday shipping 2026",
        "cyber monday 2026",
    ],
    "Benefits & deadlines": [
        "social security payment schedule",
        "medicare open enrollment 2026",
        "tax deadline 2027",
    ],
    "School calendars": [
        "thanksgiving break 2026 school",
        "winter break 2026 school",
        "school calendar 2026-27",
    ],
}

DEFAULT_MOTOR = "Election & civic"

# Optional single-word autocomplete roots (phrase seeds stay primary).
MOTOR_ROOTS = {
    "Election & civic": ["election", "ballot", "voting"],
    "Holidays & dates": ["thanksgiving", "halloween", "christmas"],
    "Retail & shipping": ["black", "cyber", "shipping"],
    "Benefits & deadlines": ["medicare", "social", "tax"],
    "School calendars": ["school", "calendar", "break"],
}
