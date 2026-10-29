"""Opportunity Radar — embedded in main app (uses shared motor_scan)."""
from datetime import datetime
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import importlib
import motor_scan as _motor_scan_mod
from motors import DEFAULT_MOTOR, MOTORS
from related_queries import explore_url


def render_opportunity_radar(seeds, geo, timeframe, related_service, get_trendspy, get_trending_rss):
    st.subheader("Opportunity Radar")
    st.caption("Tam dashboard için: `streamlit run dashboard.py`")
    cache_dir = Path(__file__).parent / ".cache"

    motor_name = st.selectbox("Motor paketi", list(MOTORS.keys()), index=list(MOTORS.keys()).index(DEFAULT_MOTOR))
    use_motor = st.checkbox("Motor seed'lerini kullan", value=True)
    active_seeds = MOTORS[motor_name] if use_motor else seeds
    if not use_motor and seeds:
        active_seeds = seeds
    elif use_motor and seeds:
        active_seeds = list(dict.fromkeys(MOTORS[motor_name] + seeds))[:8]

    if not active_seeds:
        st.info("Seed girin veya motor paketi seçin.")
        return

    if st.button("Tara", type="primary"):
        with st.spinner("Taranıyor…"):
            importlib.reload(_motor_scan_mod)
            st.session_state.scan_payload = _motor_scan_mod.run_motor_scan(
                active_seeds,
                geo=geo or "US",
                related_service=related_service,
                get_trendspy=get_trendspy,
                get_trending_rss=get_trending_rss,
                cache_dir=cache_dir,
                scan_mode="deep",
            )

    payload = st.session_state.get("scan_payload") or {}
    rows = payload.get("rows", [])
    if not rows:
        st.info("Tara'ya bas.")
        return

    new_rows = [r for r in rows if not r.get("published_slug")]
    st.metric("Yeni fırsat", len(new_rows))
    for r in new_rows[:5]:
        st.markdown(f"**{r['score']}** · {r.get('tier')} · {r['query']}")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.download_button("JSON", json.dumps(rows, indent=2).encode(), "opportunities.json")
