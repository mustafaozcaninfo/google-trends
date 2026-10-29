#!/usr/bin/env python3
"""Google Trends Advanced App — macOS ready."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from pathlib import Path
from related_queries import explore_url


@st.cache_resource
def _load_research_service(source_revision):
    # Streamlit reruns app.py but imported modules and resource objects may
    # survive. Reload the service when its source changes, then cache by revision.
    import importlib
    import related_queries
    module = importlib.reload(related_queries)
    return module.RelatedQueriesService(Path(__file__).parent / ".cache" / "related.sqlite3")


def get_research_service():
    import hashlib
    source = Path(__file__).with_name("related_queries.py")
    revision = hashlib.sha256(source.read_bytes()).hexdigest()
    return _load_research_service(revision)

# Lazy imports for speed
def get_trendspy():
    from trendspy import Trends
    return Trends()

def get_trending_rss(geo="US"):
    from trendspyg import download_google_trends_rss
    return download_google_trends_rss(geo=geo, normalize=True)

st.set_page_config(
    page_title="Google Trends Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Google Trends Pro")
st.caption("Interest Over Time · Related Queries · Trending Now · Region")

# --- Sidebar ---
with st.sidebar:
    st.header("Ayarlar")
    mode = st.radio(
        "Mod",
        [
            "Opportunity Radar",
            "Interest Over Time",
            "Related Queries",
            "Uzun Kuyruk Araştırması",
            "Trending Now",
            "Interest by Region",
        ],
        index=0,
    )
    geo = st.text_input("Geo (ülke kodu)", value="US", help="US, TR, GB, DE, FR, ...")
    keywords_raw = st.text_input(
        "Keywords (virgülle ayır, max 5)",
        value="2027 calendar",
        help="Örn: bitcoin, ethereum, solana",
    )
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()][:5]

    st.subheader("Tarih Aralığı")
    tf_preset = st.selectbox(
        "Hazır aralık",
        [
            "today 12-m",
            "today 5-y",
            "today 3-m",
            "today 1-m",
            "now 7-d",
            "now 1-d",
            "Özel tarih",
        ],
        index=0,
    )
    custom_start = custom_end = None
    if tf_preset == "Özel tarih":
        col1, col2 = st.columns(2)
        with col1:
            custom_start = st.date_input("Başlangıç", datetime.now() - timedelta(days=365))
        with col2:
            custom_end = st.date_input("Bitiş", datetime.now())
        timeframe = f"{custom_start} {custom_end}"
    else:
        timeframe = tf_preset

    geo = geo.strip().upper()
    run = st.button("🔍 Çalıştır", type="primary", use_container_width=True)

# --- Main ---
if mode == "Opportunity Radar":
    from opportunity_ui import render_opportunity_radar
    render_opportunity_radar(keywords, geo, timeframe, get_research_service(), get_trendspy, get_trending_rss)
    st.stop()

if mode == "Uzun Kuyruk Araştırması":
    from long_tail_ui import render_long_tail
    render_long_tail(keywords, geo, timeframe, get_research_service())
    st.stop()

request_key = (mode, tuple(keywords), geo, timeframe)
if run:
    st.session_state["active_request"] = request_key
if st.session_state.get("active_request") != request_key:
    st.info("Soldan ayarları yapıp **Çalıştır**'a bas.")
    st.stop()

if not keywords and mode != "Trending Now":
    st.error("En az bir keyword gir.")
    st.stop()

with st.spinner("Veri çekiliyor..."):
    try:
        if mode == "Trending Now":
            data = get_trending_rss(geo)
            trends = data.get("trends", []) if isinstance(data, dict) else data
            st.subheader(f"🔥 Trending Now — {geo}")
            if trends:
                rows = []
                for t in trends:
                    rows.append({
                        "Rank": t.get("rank"),
                        "Keyword": t.get("keyword") or t.get("trend"),
                        "Volume": t.get("volume_text") or t.get("approx_traffic"),
                        "Started": t.get("started_at"),
                        "Explore": t.get("explore_url"),
                    })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "CSV indir",
                    df.to_csv(index=False).encode(),
                    f"trending_{geo}.csv",
                    "text/csv",
                )
            else:
                st.warning("Trend bulunamadı.")

        elif mode == "Interest Over Time":
            tr = get_trendspy()
            df = tr.interest_over_time(keywords, timeframe=timeframe, geo=geo)
            if df is None or df.empty:
                st.error("Veri gelmedi.")
            else:
                st.subheader(f"Interest Over Time — {', '.join(keywords)} ({geo})")
                plot_df = df.reset_index()
                date_col = plot_df.columns[0]
                fig = px.line(
                    plot_df,
                    x=date_col,
                    y=keywords,
                    markers=True,
                    title=f"{timeframe} · {geo}",
                )
                fig.update_layout(hovermode="x unified", height=480)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "CSV indir",
                    df.to_csv().encode(),
                    f"interest_{'_'.join(keywords)}.csv",
                    "text/csv",
                )

        elif mode == "Related Queries":
            kw = keywords[0]
            st.subheader(f"Related Queries — {kw} ({geo or 'Worldwide'})")
            st.caption(f"Tarih aralığı: {timeframe} · İlk keyword kullanılır. İlk istek Chrome ile yaklaşık 1 dakika sürebilir.")
            st.link_button("Google Trends'te aç", explore_url(kw, geo, timeframe))
            result = get_research_service().get(kw, geo, timeframe)
            if result.message:
                st.warning(result.message)
            if result.retry_after:
                st.info(f"Yeni istek için yaklaşık {result.retry_after} saniye bekleyin. Google kısıtının kalkma süresi değişebilir.")
            if result.data is not None:
                fetched = datetime.fromtimestamp(result.fetched_at).astimezone().isoformat(timespec="seconds")
                label = "Önceki kayıt; güncel veri alınamadı" if result.stale else ("Önbellekten" if result.cached else "Google Trends")
                st.caption(f"{label} · Alınma zamanı: {fetched}")
                st.caption("Google’dan dönen tüm Top ve Rising kayıtları gösterilir; uygulama satır sınırı uygulamaz.")
                show_all_rows = st.checkbox("Tüm satırları açık göster", value=True, key="related_show_all")
                for part, column in zip(("top", "rising"), st.columns(2)):
                    with column:
                        frame = pd.DataFrame(result.data[part])
                        st.markdown(f"**{part.title()} · {len(frame)} kayıt**")
                        if frame.empty:
                            st.info("Bu bölüm için veri döndürülmedi.")
                        else:
                            if show_all_rows:
                                st.table(frame)
                            else:
                                st.dataframe(frame, use_container_width=True, hide_index=True)
                            st.download_button(
                                f"{part.title()} CSV indir", frame.to_csv(index=False).encode("utf-8-sig"),
                                f"related_{part}_{geo or 'worldwide'}.csv", "text/csv", key=f"related_{part}",
                            )

        elif mode == "Interest by Region":
            tr = get_trendspy()
            kw = keywords[0]
            df = tr.interest_by_region(kw, resolution="COUNTRY", inc_low_vol=True)
            # Some versions need geo context differently; fallback simple
            st.subheader(f"Interest by Region — {kw}")
            if df is not None and not df.empty:
                st.dataframe(df.head(30), use_container_width=True)
                fig = px.bar(
                    df.reset_index().head(20),
                    x=df.reset_index().columns[0],
                    y=kw if kw in df.columns else df.columns[0],
                    title="Top regions",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Region verisi gelmedi (rate limit veya keyword).")

    except Exception as e:
        st.error(f"Hata: {type(e).__name__}: {e}")
        st.info("Google rate limit olabilir. Birkaç dakika bekleyip tekrar dene.")

st.divider()
st.caption("trendspy + trendspyg · Unofficial · Rate limit'e dikkat et")
