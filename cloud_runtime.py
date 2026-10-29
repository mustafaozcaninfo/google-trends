"""Detect Streamlit Community Cloud and disable Chrome-dependent features."""

from __future__ import annotations

import os
from pathlib import Path


def is_streamlit_community_cloud() -> bool:
    """True on share.streamlit.io (no Selenium/Chrome)."""
    if os.environ.get("FC_CLOUD", "").strip().lower() in ("1", "true", "yes"):
        return True
    env = os.environ.get("STREAMLIT_RUNTIME_ENVIRONMENT", "").strip().lower()
    if env in ("cloud", "community-cloud"):
        return True
    # Streamlit Cloud mounts repo at /mount/src
    if Path("/mount/src").is_dir():
        return True
    return False


def trending_mode_cloud() -> str:
    return "rss"


def chrome_features_enabled() -> bool:
    return not is_streamlit_community_cloud()
