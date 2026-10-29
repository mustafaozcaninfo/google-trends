"""Dashboard render helpers — pipeline + score breakdown + landing."""
from __future__ import annotations

import html

import streamlit as st

from dashboard_styles import SCORE_LABELS
import pandas as pd

from editor_pick import rank_trend_picks
from interest_config import interest_label
from motors import MOTORS

__all__ = [
    "render_landing",
    "render_pipeline",
    "render_score_bar",
    "render_trends_badges",
    "render_trending_chips",
    "render_interest_chart",
    "render_how_it_works",
]


def render_how_it_works() -> None:
    with st.expander("Radar mantığı — nasıl işe yarar?", expanded=False):
        st.markdown(
            """
1. **Trending** — Tam liste (468) search volume + RSS özeti; skor için birleşik index.
2. **Seed seç** — Trend/editör önerisi, sidebar **Serbest kelime**, veya isteğe bağlı paket.
3. **Autocomplete** — Google suggest: `seed`, `seed␠`, `a…z`, `how/what/when…` → long-tail adaylar.
4. **Related** — Varsa SQLite cache (Top/Rising); yoksa skor autocomplete + trending hacimle devam eder.
5. **Skor (429’suz)** — Autocomplete + trending hacim (10K–500K+) + Related cache + slug gap.
6. **Interest grafiği** — Sadece **“Interest / grafik getir”** ile; tarama otomatik istek atmaz.
7. **Tier** — **Catch now** = spike / 50K+ hacim; **Write soon** = güçlü long-tail; **Skip** = sitede var.
            """
        )


def _autocomplete_step_label(meta: dict) -> str:
    pipe = meta.get("pipeline") or {}
    ac = meta.get("autocomplete_stats") or {}
    base = f"{pipe.get('step2_autocomplete', 0)} long-tail"
    if not ac:
        return base
    parts = [base]
    if ac.get("bootstrap_added"):
        parts.append(f"+{ac['bootstrap_added']} bootstrap")
    if ac.get("throttled_probes"):
        parts.append(f"{ac['throttled_probes']} probe bekletildi")
    return " · ".join(parts)


def render_pipeline(meta: dict) -> None:
    pipe = meta.get("pipeline") or {}
    import streamlit as st

    steps = [
        ("1", "Seeds", f"{pipe.get('step1_seeds', 0)} phrase · {pipe.get('step1_seeds_with_roots', 0)} scan"),
        ("2", "Autocomplete", _autocomplete_step_label(meta)),
        ("3", "Trends", (
            f"Full {pipe.get('step3_trending_full', 0)} · "
            f"RSS {pipe.get('step3_trending_rss', 0)} · "
            f"Related cache {pipe.get('step3_related_cached', 0)}"
        )),
        ("4", "Skor", f"{pipe.get('step4_scored', 0)} fırsat"),
    ]
    cols = st.columns(len(steps))
    for col, (num, title, val) in zip(cols, steps):
        with col:
            st.markdown(
                f"""
<div class="fc-step">
  <div class="fc-step-num">Adım {num}</div>
  <div class="fc-step-title">{html.escape(title)}</div>
  <div class="fc-step-val">{html.escape(str(val))}</div>
</div>""",
                unsafe_allow_html=True,
            )


def render_trends_badges(row: dict) -> str:
    def badge(label: str, on: bool) -> str:
        cls = "fc-badge fc-badge--on" if on else "fc-badge fc-badge--off"
        return f'<span class="{cls}">{html.escape(label)}</span>'

    parts = [
        badge("Rising", bool(row.get("trends_rising"))),
        badge("Top", bool(row.get("trends_top"))),
        badge("Trending Now", bool(row.get("trends_trending_now"))),
    ]
    vol = row.get("trends_volume_text") or ""
    if vol:
        parts.append(badge(f"Vol {vol}", True))
    mom = row.get("interest_momentum")
    if mom is not None and mom > 0:
        parts.append(badge(f"Interest ×{mom}", mom >= 1.15))
    return '<div class="fc-badges">' + "".join(parts) + "</div>"


def _trends_to_table(trends: list[dict]) -> pd.DataFrame:
    rows = []
    for t in trends:
        kw = (t.get("keyword") or t.get("trend") or "").strip()
        if not kw:
            continue
        rel = t.get("related_queries") or []
        rows.append({
            "sıra": t.get("rank") or "",
            "trend": kw,
            "hacim": t.get("volume_text") or t.get("approx_traffic") or "",
            "hacim_min": int(t.get("volume_min") or 0),
            "başladı": t.get("started_at") or "",
            "breakdown": ", ".join(rel),
            "kaynak": t.get("origin") or "",
            "explore": t.get("explore_url") or "",
        })
    return pd.DataFrame(rows)


def _trends_for_editor_picks(bundle: dict) -> list[dict]:
    """Same keyword pool as motor_scan scoring: display list + merged index (RSS ∪ full)."""
    trends = bundle.get("trends") or []
    index = bundle.get("index") or {}
    by_key: dict[str, dict] = {}
    for t in trends:
        kw = (t.get("keyword") or t.get("trend") or "").strip()
        if not kw:
            continue
        by_key[" ".join(kw.lower().split())] = {**t, "keyword": kw}
    for entry in index.values():
        kw = (entry.get("keyword") or "").strip()
        if not kw:
            continue
        key = " ".join(kw.lower().split())
        prev = by_key.get(key)
        if prev is None or int(entry.get("volume_min") or 0) > int(prev.get("volume_min") or 0):
            by_key[key] = {**entry, "keyword": kw}
    return list(by_key.values())


def render_landing(
    bundle: dict,
    *,
    geo: str,
    key_prefix: str = "home",
) -> None:
    """Trending + editor packs — user picks before any heavy autocomplete scan."""
    _ = geo
    primary = bundle.get("primary") or "rss"
    trends = bundle.get("trends") or []
    errs = bundle.get("errors") or {}

    st.subheader("1 · Editör önerisi (FC News)")
    st.caption("Takvim/haber uyumu + hacim — tıkla, long-tail tarama başlar.")

    picks = rank_trend_picks(_trends_for_editor_picks(bundle), limit=6)
    if picks:
        pcols = st.columns(min(len(picks), 3))
        for i, t in enumerate(picks):
            kw = t["keyword"]
            vol = t.get("volume_text") or ""
            fit = t.get("calendar_fit", 0)
            label = f"★ {kw}\n{vol} · uyum {fit}" if vol else f"★ {kw}\nuyum {fit}"
            with pcols[i % len(pcols)]:
                if st.button(label, key=f"{key_prefix}_pick_{i}", width="stretch"):
                    st.session_state.picked_seeds = [kw]
                    st.session_state.picked_label = f"Öneri: {kw}"
                    st.session_state.trigger_scan = True
                    st.rerun()
    if not trends:
        st.info("Trending boş. Sidebar → **Seed’leri tara**.")
        render_how_it_works()
        return

    st.markdown("---")
    st.subheader("2 · Tüm trending tablosu")
    cap = f"{len(trends)} satır"
    if primary != "full":
        cap += " · tam liste için sidebar → Tam listeyi indir / yenile"
    st.caption(cap)
    if errs.get("rss"):
        st.warning(f"RSS: {errs['rss']}")

    table = _trends_to_table(trends)
    n = len(table)
    table_height = min(2400, 48 + 35 * max(n, 1))
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        height=table_height,
        column_config={
            "explore": st.column_config.LinkColumn("Explore", display_text="Trends"),
            "breakdown": st.column_config.TextColumn("breakdown", width="large"),
        },
    )

    keywords = table["trend"].tolist()
    pick_col, go_col = st.columns([4, 1])
    with pick_col:
        chosen = st.selectbox(
            "Trend seç → long-tail tara",
            keywords,
            key=f"{key_prefix}_trend_select",
        )
    with go_col:
        st.write("")
        st.write("")
        if st.button("Tara", key=f"{key_prefix}_trend_go", type="primary", width="stretch"):
            st.session_state.picked_seeds = [chosen]
            st.session_state.picked_label = chosen
            st.session_state.trigger_scan = True
            st.rerun()

    with st.expander("3 · Editör paketleri (Black Friday, school, …)", expanded=False):
        for name, seed_list in MOTORS.items():
            safe = name.replace(" ", "_").replace("&", "and")
            if st.button(name, key=f"{key_prefix}_motor_{safe}", width="stretch"):
                st.session_state.picked_seeds = list(seed_list)
                st.session_state.picked_label = name
                st.session_state.trigger_scan = True
                st.rerun()

    render_how_it_works()


def render_interest_chart(
    series: dict[str, list[dict]],
    *,
    timeframe: str,
    query_labels: list[str] | None = None,
) -> None:
    """Line chart from motor_scan interest_series (0–100 Google interest)."""
    if not series:
        st.caption("Interest grafiği için veri yok (Trends API hatası veya sıfır hacim).")
        return
    label = interest_label(timeframe)
    st.caption(f"Google Interest — {label} · 0–100 göreli popülerlik")

    order = query_labels or list(series.keys())
    frames = []
    for q in order:
        key = " ".join(q.lower().split())
        pts = series.get(key)
        if not pts:
            continue
        idx = pd.to_datetime([p["t"] for p in pts], errors="coerce")
        frames.append(pd.Series([p["v"] for p in pts], index=idx, name=q[:48]))
    if not frames:
        st.caption("Seçili ifadeler için seri bulunamadı.")
        return
    chart_df = pd.concat(frames, axis=1).sort_index()
    st.line_chart(chart_df, width="stretch")


def render_trending_chips(trending: list[dict], limit: int = 12) -> None:
    chips = []
    for t in trending[:limit]:
        kw = html.escape((t.get("keyword") or t.get("trend") or "?").strip())
        vol = t.get("volume_text") or t.get("approx_traffic") or ""
        label = f"{kw} ({html.escape(str(vol))})" if vol else kw
        chips.append(f'<span class="fc-trending-chip">{label}</span>')
    if chips:
        st.markdown(" ".join(chips), unsafe_allow_html=True)


def render_score_bar(breakdown: dict, total: int) -> str:
    if not breakdown or total <= 0:
        return ""
    pos_total = max(
        sum(v for k, v in breakdown.items() if k != "published_penalty" and v > 0),
        1,
    )
    segs = []
    order = ["autocomplete", "related", "trending_rss", "trending_volume", "interest", "long_tail", "discover"]
    for key in order:
        val = breakdown.get(key, 0)
        if val <= 0:
            continue
        _, css = SCORE_LABELS.get(key, (key, "fc-score-seg-ac"))
        width = max(4, int(100 * val / pos_total))
        segs.append(f'<div class="{css}" style="width:{width}%"></div>')
    pen = breakdown.get("published_penalty", 0)
    if pen < 0:
        segs.append(f'<div class="fc-score-seg-pn" style="width:12%"></div>')
    return '<div class="fc-score-bar">' + "".join(segs) + "</div>"
