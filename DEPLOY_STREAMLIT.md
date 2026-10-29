# Streamlit Community Cloud (RSS + autocomplete mode)

This deploy runs **without Chrome**: trending via **RSS**, long-tail via **Google autocomplete**, GSC via **file upload**, slugs via **live sitemap fetch**.

## 1. Push to a **public** GitHub repo

```bash
cd google-trends
git init -b main
git add .
git commit -m "FC News Radar for Streamlit Community Cloud"
git remote add origin https://github.com/YOUR_USER/google-trends.git
git push -u origin main
```

Do not commit `.cache/`, `venv/`, or `downloads/` (see `.gitignore`).

## 2. Deploy on Community Cloud

1. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → repository `YOUR_USER/google-trends`, branch `main`.
3. **Main file path:** `dashboard.py`
4. **App URL (optional):** e.g. `fc-news-radar`
5. Deploy.

## 3. Optional secrets

In **App settings → Secrets**, you can add:

```toml
FC_CLOUD = "1"
```

(Usually auto-detected on Cloud; this forces the same behavior locally.)

## 4. What works on Cloud

| Feature | Cloud |
|---------|--------|
| Trending RSS + landing | Yes |
| Autocomplete / printable scan | Yes (rate limits apply) |
| GSC upload | Yes (session; re-upload after sleep) |
| Sitemap slug refresh | Yes |
| Full trending CSV (Chrome) | **No** |
| Related Explore live / Interest live | **No** (scan uses `run_interest=False`) |

## 5. After deploy

- Upload **Search Console → Queries.csv** in the sidebar when you need GSC scoring.
- App **sleeps after ~12h** without visits; first open may take 30–60s.
- For **private** editor access: use `st.login()` or keep repo private (1 private app limit).

## Local parity (cloud mode)

```bash
export FC_CLOUD=1
streamlit run dashboard.py --server.port 8502
```
