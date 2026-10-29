#!/usr/bin/env python3
"""Fresh Calendars News — live opportunity dashboard (autocomplete + Trends)."""

from datetime import datetime
import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard_styles import DASHBOARD_CSS, TABLE_COLUMNS, TIER_CLASS
import importlib
import motors as _motors_mod
importlib.reload(_motors_mod)
MOTOR_FREE = getattr(_motors_mod, "MOTOR_FREE", "— Serbest kelime (paket yok) —")
MOTORS = _motors_mod.MOTORS

import dashboard_ui as _dashboard_ui
importlib.reload(_dashboard_ui)
render_landing = _dashboard_ui.render_landing
render_pipeline = _dashboard_ui.render_pipeline
render_score_bar = _dashboard_ui.render_score_bar
render_trends_badges = _dashboard_ui.render_trends_badges
render_interest_chart = _dashboard_ui.render_interest_chart
from related_queries import explore_url
from content_brief import build_content_brief
import interest_config as _interest_config_mod
importlib.reload(_interest_config_mod)
from interest_config import (
    DEFAULT_INTEREST_TIMEFRAME,
    INTEREST_TIMEFRAME_CHOICES,
    INTEREST_TIMEFRAME_IDS,
)
DEFAULT_INTEREST_BACKEND = getattr(_interest_config_mod, "DEFAULT_INTEREST_BACKEND", "auto")
INTEREST_BACKEND_CHOICES = getattr(
    _interest_config_mod,
    "INTEREST_BACKEND_CHOICES",
    [
        ("auto", "Otomatik — önbellek, sonra trendspyg (önerilen)"),
        ("cache_only", "Sadece önbellek — 429 yok, canlı çağrı yok"),
        ("live", "Canlı trendspy — riskli, test için"),
    ],
)
import seed_expand as _seed_expand_mod
importlib.reload(_seed_expand_mod)
parse_seed_input = _seed_expand_mod.parse_seed_input
import trending_service as _trending_service_mod
importlib.reload(_trending_service_mod)
from trending_service import TrendingService, fetch_trending_bundle
from cloud_runtime import chrome_features_enabled, is_streamlit_community_cloud, trending_mode_cloud


def _motor_scan_mod():
    import long_tail_discover
    import google_autocomplete
    import signals
    import site_intelligence
    import trends_layer
    import motor_scan

    importlib.reload(long_tail_discover)
    importlib.reload(google_autocomplete)
    importlib.reload(signals)
    importlib.reload(site_intelligence)
    importlib.reload(trends_layer)
    importlib.reload(motor_scan)
    return motor_scan


@st.cache_resource
def related_service():
    import related_queries
    mod = importlib.reload(related_queries)
    return mod.RelatedQueriesService(Path(__file__).parent / ".cache" / "related.sqlite3")


@st.cache_resource
def get_trendspy():
    from trendspy import Trends
    return Trends(request_delay=2.0, max_retries=2)


def get_trending_rss(geo="US"):
    from trendspyg import download_google_trends_rss
    return download_google_trends_rss(geo=geo, normalize=True)


def get_trending_csv(**kwargs):
    if not chrome_features_enabled():
        raise RuntimeError("Tam trend listesi (Chrome) bu ortamda kapalı.")
    from trendspyg import download_google_trends_csv
    return download_google_trends_csv(**kwargs)


CACHE_DIR = Path(__file__).parent / ".cache"


@st.cache_resource
def trending_service() -> TrendingService:
    return TrendingService(CACHE_DIR)


@st.cache_data(ttl=300, show_spinner=False)
def load_trending_bundle(geo: str, mode: str, hours: int, refresh_full: bool) -> dict:
    cloud = is_streamlit_community_cloud()
    eff_mode = trending_mode_cloud() if cloud else (mode if mode in ("rss", "full", "auto") else "auto")
    return fetch_trending_bundle(
        trending_service(),
        geo,
        mode=eff_mode,
        hours=int(hours),
        fetch_rss=get_trending_rss,
        fetch_csv=get_trending_csv if chrome_features_enabled() else None,
        refresh_full=refresh_full and chrome_features_enabled(),
    )


def _init_session():
    defaults = {
        "scan_payload": None,
        "picked_seeds": None,
        "picked_label": "",
        "trigger_scan": False,
        "last_seeds": [],
        "refresh_trending_full": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _tier_class(tier: str) -> str:
    return TIER_CLASS.get(tier, "fc-opp--backlog")


def _render_opp_row(r: dict, geo: str) -> None:
    tier = r.get("tier", "")
    cls = _tier_class(tier)
    q = html.escape(r.get("query", ""))
    hint = html.escape(r.get("headline_hint", ""))
    seed = html.escape(r.get("seed") or "—")
    signals = html.escape((r.get("signals") or "")[:140])
    score = int(r.get("score", 0))
    bar = render_score_bar(r.get("score_breakdown") or {}, score)
    badges = render_trends_badges(r)

    st.markdown(
        f"""
<div class="fc-opp {cls}">
  <div class="fc-opp-title">{q}</div>
  <div class="fc-opp-hint">{hint}</div>
  {badges}
  {bar}
  <div class="fc-opp-meta">
    <span class="fc-opp-score">Skor {score}</span> · {html.escape(tier)} · kök: {seed}<br/>
    {signals}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.link_button("Google Trends'te aç", explore_url(r["query"], geo, "today 3-m"), width="stretch")


def _run_scan(
    seeds: list[str],
    *,
    scan_mode,
    min_words,
    use_trending_seeds,
    refresh_slugs,
    trending_mode,
    trending_hours,
    refresh_trending_full,
    trending_seed_limit,
    trending_bundle,
):
    return _motor_scan_mod().run_motor_scan(
        seeds,
        geo=GEO,
        related_service=related_service(),
        get_trendspy=get_trendspy,
        get_trending_rss=get_trending_rss,
        get_trending_csv=get_trending_csv,
        trending_service=trending_service(),
        cache_dir=CACHE_DIR,
        scan_mode=scan_mode,
        min_words=int(min_words),
        run_interest=False,
        use_trending_as_seeds=use_trending_seeds,
        trending_mode=trending_mode,
        trending_hours=int(trending_hours),
        refresh_trending_full=refresh_trending_full,
        trending_seed_limit=int(trending_seed_limit),
        refresh_slugs=refresh_slugs,
        trending_bundle=trending_bundle,
    )


st.set_page_config(
    page_title="FC News Radar",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Fresh Calendars News Radar — US trending + long-tail opportunities.",
    },
)

st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
_init_session()

GEO = "US"
_CLOUD = is_streamlit_community_cloud()

with st.sidebar:
    if _CLOUD:
        st.info(
            "**Community Cloud** — Trending: RSS (~10 konu). "
            "Autocomplete + GSC upload açık. Chrome (tam CSV) yok."
        )
    st.header("Trending kaynağı")
    if _CLOUD:
        trending_mode = trending_mode_cloud()
        st.caption("Liste: **RSS** (Cloud modu)")
        trending_hours = 24
    else:
        trending_mode = st.selectbox(
            "Liste",
            ["auto", "rss", "full"],
            format_func=lambda x: {
                "auto": "Otomatik — önbellekli tam liste, yoksa RSS",
                "rss": "RSS — hızlı (~10 konu)",
                "full": "Tam liste — search volume (Chrome)",
            }[x],
            index=0,
        )
        trending_hours = st.selectbox("Tam liste süresi", [4, 24, 48, 168], index=1)
        refresh_full_btn = st.button("Tam listeyi indir / yenile", width="stretch")
        if refresh_full_btn:
            st.session_state.refresh_trending_full = True
            load_trending_bundle.clear()
    st.divider()
    st.header("Kelime taraması")
    st.caption("Paket seçmeden sadece kendi seed’lerinle tarayabilirsin.")
    motor_name = st.selectbox(
        "Editör paketi (opsiyonel)",
        [MOTOR_FREE, *MOTORS.keys()],
        index=0,
        help="Serbest mod: yalnızca aşağıdaki seed kutusu kullanılır.",
    )
    extra = st.text_input(
        "Seed kelime / cümle (virgülle)",
        value="",
        placeholder="ör. black friday 2026, school closings michigan",
    )
    root_words = st.checkbox(
        "Tek kelime kökleri ekle (sadece paket seçiliyken)",
        value=False,
        disabled=(motor_name == MOTOR_FREE),
    )
    scan_mode = st.selectbox(
        "Keşif modu",
        ["deep", "deep_plus", "printable", "quick"],
        format_func=lambda x: {
            "deep": "Derin — A–Z + soru önekleri",
            "deep_plus": "Derin+ — A–Z + 2. dalga",
            "printable": "Printable/PDF — 2026–2027 + indirilebilir niyet",
            "quick": "Hızlı — seed genişletme",
        }[x],
        index=0,
    )
    min_words = st.slider("Min kelime (long-tail)", 3, 8, 4)
    use_trending_seeds = st.checkbox("Trending'i ek seed yap", value=False)
    trending_seed_limit = st.slider("Ek seed (trending'den, max 5)", 0, 5, 1)
    auto = st.checkbox("Trending RSS’i otomatik yenile (2 dk)", value=False)
    refresh_slugs = st.checkbox("Sitemap slug yenile", value=False)
    st.divider()
    st.header("Site zekâsı (GSC)")
    gsc_upload = st.file_uploader("Search Console → Queries.csv", type=["csv"])
    if gsc_upload is not None:
        dest = CACHE_DIR / "gsc_queries.csv"
        dest.write_bytes(gsc_upload.getvalue())
        st.caption(f"Kaydedildi · {dest.name}")
    elif (CACHE_DIR / "gsc_queries.csv").is_file():
        st.caption("GSC yüklü — skorlar site + gap ile ağırlanır.")
    sidebar_scan = st.button("Kelime(ler)i tara", type="primary", width="stretch")
    if st.button("Başa dön — öneriler", width="stretch"):
        st.session_state.scan_payload = None
        st.session_state.picked_seeds = None
        st.session_state.picked_label = ""
        st.session_state.trigger_scan = False
        st.rerun()

sidebar_seeds = parse_seed_input(
    motor_name,
    extra,
    root_words=root_words,
    include_motor_pack=(motor_name != MOTOR_FREE),
)

tick = st.autorefresh(interval=120_000, key="fc_radar_autorefresh") if auto else 0

_refresh_full = bool(st.session_state.pop("refresh_trending_full", False))
trending_bundle = load_trending_bundle(GEO, trending_mode, trending_hours, _refresh_full)

head_l, head_r = st.columns([5, 1])
with head_l:
    st.title("Fresh Calendars News Radar")
    prim = trending_bundle.get("primary") or "rss"
    st.caption(f"1) Trend seç → 2) Long-tail tara → 3) Catch now yaz · trending: {prim}")
with head_r:
    st.write("")
    if st.button("RSS yenile", width="stretch", icon=":material/sync:"):
        load_trending_bundle.clear()
        st.rerun()

scan_seeds: list[str] | None = None
if st.session_state.trigger_scan and st.session_state.picked_seeds:
    scan_seeds = list(st.session_state.picked_seeds)
    st.session_state.trigger_scan = False
elif sidebar_scan:
    if not sidebar_seeds:
        st.sidebar.warning("En az bir seed yaz (virgülle birden fazla olabilir).")
    else:
        scan_seeds = sidebar_seeds
        st.session_state.picked_label = extra.strip()[:60] or "Kelime taraması"
elif tick > 0:
    load_trending_bundle.clear()
    trending_bundle = load_trending_bundle(GEO, trending_mode, trending_hours, False)

if scan_seeds:
    label = st.session_state.picked_label or ", ".join(scan_seeds[:2])
    with st.spinner(f"Long-tail taranıyor: {label}…"):
        try:
            st.session_state.scan_payload = _run_scan(
                scan_seeds,
                scan_mode=scan_mode,
                min_words=min_words,
                use_trending_seeds=use_trending_seeds,
                refresh_slugs=refresh_slugs,
                trending_mode=trending_mode,
                trending_hours=trending_hours,
                refresh_trending_full=_refresh_full,
                trending_seed_limit=trending_seed_limit,
                trending_bundle=trending_bundle,
            )
            st.session_state.last_seeds = scan_seeds
        except Exception as exc:
            st.error(f"Tarama hatası: {exc}")

payload = st.session_state.scan_payload

if payload is None:
    from site_intelligence import load_gsc_index, top_gsc_gaps

    gsc_idx = load_gsc_index(CACHE_DIR)
    if gsc_idx:
        from content_prioritizer import prioritize_gsc_index
        from published_slugs import PublishedSlugCache

        slugs = PublishedSlugCache(CACHE_DIR / "freshcalendars_slugs.json").load()
        skip_list, new_list = prioritize_gsc_index(gsc_idx, slugs, min_impressions=300)
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("Yeni içerik üret (GSC + slug)", expanded=True):
                for d in new_list[:10]:
                    tag = "🔄 meta/hub" if d.bucket == "refresh" else "✨ yeni URL"
                    st.markdown(f"**{d.query}** {tag}")
                    st.caption(d.reason)
                    if d.action:
                        st.caption(d.action)
        with c2:
            with st.expander("Önemsiz / atlama", expanded=False):
                for d in skip_list[:12]:
                    st.markdown(f"~~{d.query}~~")
                    st.caption(d.reason)
        with st.expander("Site yükseltme — ham GSC gap", expanded=False):
            gaps = top_gsc_gaps(gsc_idx, limit=8)
            for g in gaps:
                st.markdown(
                    f"**{g['query']}** — {int(g['impressions']):,} gösterim, "
                    f"CTR %{g['ctr']:.2f}, sıra {g['position']:.1f}"
                )
    render_landing(trending_bundle, geo=GEO)
    st.stop()

rows = payload.get("rows", [])
meta = payload.get("motor_meta", {})
trending = payload.get("trending") or trending_bundle.get("trends") or []

new_rows = [r for r in rows if not r.get("published_slug")]
catch = [r for r in new_rows if r.get("tier") == "Catch now"]
write_soon = [r for r in new_rows if r.get("tier") == "Write soon"]

if st.session_state.picked_label:
    st.caption(f"Konu: **{st.session_state.picked_label}** · sidebar **Başa dön** ile trending’e dön")

m1, m2, m3 = st.columns(3)
m1.metric("Catch now", len(catch))
m2.metric("Write soon", len(write_soon))
m3.metric("Long-tail aday", meta.get("autocomplete_count", 0))

_ac = meta.get("autocomplete_stats") or {}
if _ac.get("throttled_probes"):
    st.warning(
        f"Autocomplete kısmen bekletildi ({_ac['throttled_probes']}/{_ac.get('probes', '?')} probe). "
        "Aynı taramayı 1–2 dk sonra tekrarla — önbellek dolunca liste uzar."
    )
elif _ac.get("message"):
    st.info(_ac["message"])

st.subheader("Yazılacaklar — önce bunlar")
top = catch[:3] or write_soon[:3] or new_rows[:3]
if not top:
    if rows:
        st.warning(
            f"Tarama {len(rows)} satır üretti; üst kart filtresinde görünen yok. "
            "Aşağıdaki listede min skoru düşür veya tier seçimini genişlet."
        )
    else:
        st.warning(
            "Autocomplete boş — min kelimeyi düşür, Keşif modunu Hızlı dene veya 1–2 dk sonra tekrar tara."
        )
else:
    for r in top:
        with st.container(border=True):
            _render_opp_row(r, GEO)
            brief = build_content_brief(r)
            with st.expander("İçerik taslağı", expanded=False):
                st.markdown("\n".join(f"- {line}" for line in brief["outline"]))
                st.caption(f"Hedef uzunluk: {brief['word_count_target']}")
            if r.get("site_action"):
                st.caption(f"Site: {r.get('content_intent')} · {r.get('site_action')}")
            if r.get("gsc_impressions"):
                st.caption(
                    f"GSC: {r['gsc_impressions']:,} gösterim · "
                    f"sıra {r.get('gsc_position')} · CTR %{r.get('gsc_ctr')}"
                )

with st.expander("Interest grafiği (isteğe bağlı — Google API)", expanded=False):
    st.caption("Varsayılan tarama interest çekmez. Sadece bu düğmeye basınca istek gider.")
    ic1, ic2 = st.columns(2)
    with ic1:
        interest_timeframe = st.selectbox(
            "Pencere",
            INTEREST_TIMEFRAME_IDS,
            index=INTEREST_TIMEFRAME_IDS.index(DEFAULT_INTEREST_TIMEFRAME),
            format_func=lambda tid: next(l for k, l in INTEREST_TIMEFRAME_CHOICES if k == tid),
            key="interest_tf_pick",
        )
    with ic2:
        interest_backend = st.selectbox(
            "Mod",
            [k for k, _ in INTEREST_BACKEND_CHOICES],
            index=[k for k, _ in INTEREST_BACKEND_CHOICES].index(DEFAULT_INTEREST_BACKEND),
            format_func=lambda k: next(l for key, l in INTEREST_BACKEND_CHOICES if key == k),
            key="interest_backend_pick",
        )
    if st.button("Interest / grafik getir", type="secondary", width="stretch"):
        with st.spinner("Interest çekiliyor (önbellek varsa anında)…"):
            try:
                st.session_state.scan_payload = _motor_scan_mod().add_interest_to_payload(
                    payload,
                    geo=GEO,
                    cache_dir=CACHE_DIR,
                    get_trendspy=get_trendspy,
                    interest_timeframe=interest_timeframe,
                    interest_backend=interest_backend,
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    _meta = st.session_state.scan_payload.get("motor_meta") or meta
    if _meta.get("interest_error"):
        st.warning(_meta["interest_error"])
    _series = (st.session_state.scan_payload or {}).get("interest_series") or {}
    if _series:
        render_interest_chart(
            _series,
            timeframe=_meta.get("interest_timeframe") or DEFAULT_INTEREST_TIMEFRAME,
            query_labels=(st.session_state.scan_payload or {}).get("interest_chart_queries"),
        )

with st.expander("Pipeline detayı", expanded=False):
    render_pipeline(meta)

with st.expander("Başka trending seç", expanded=False):
    render_landing(trending_bundle, geo=GEO, key_prefix="switch")

st.subheader("Tüm long-tail listesi")
tier_filter = st.multiselect(
    "Tier",
    ["Catch now", "Write soon", "Backlog", "Watch", "Skip — published"],
    default=["Catch now", "Write soon", "Backlog"],
)
min_score = st.slider("Min skor", 0, 100, 30)
filtered = [
    r for r in rows
    if r.get("tier") in tier_filter and r["score"] >= min_score
]

display_cols = [c for c in TABLE_COLUMNS if c != "signals"]
if filtered:
    table = pd.DataFrame(filtered)
    cols = [c for c in display_cols if c in table.columns]
    st.dataframe(table[cols], width="stretch", hide_index=True, height=min(420, 35 * len(filtered) + 38))
else:
    st.caption(
        f"Filtreye uyan satır yok (ham {len(rows)} satır). Min skoru düşür veya tier listesine Watch/Backlog ekle."
    )

export_df = pd.DataFrame(filtered) if filtered else pd.DataFrame(columns=TABLE_COLUMNS)
dl1, dl2, _ = st.columns([1, 1, 2])
with dl1:
    st.download_button(
        "CSV indir",
        export_df.to_csv(index=False).encode("utf-8-sig"),
        f"fc_radar_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
        width="stretch",
        disabled=not filtered,
    )
with dl2:
    st.download_button(
        "JSON indir",
        json.dumps(filtered, indent=2, default=str).encode(),
        f"fc_radar_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        "application/json",
        width="stretch",
        disabled=not filtered,
    )

st.markdown(
    f'<p class="fc-footer">Seeds: {html.escape(", ".join(payload.get("seeds", [])))} · '
    f'{meta.get("autocomplete_count", 0)} autocomplete · geo {GEO}</p>',
    unsafe_allow_html=True,
)
