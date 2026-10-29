"""Dashboard CSS aligned with Streamlit theme tokens (light + dark)."""

DASHBOARD_CSS = """
<style>
:root {
  --fc-accent: #5B9FD4;
  --fc-accent-soft: rgba(91, 159, 212, 0.14);
  --fc-border: rgba(232, 237, 244, 0.12);
  --fc-muted: rgba(232, 237, 244, 0.62);
  --fc-tier-catch: #F87171;
  --fc-tier-soon: #FB923C;
  --fc-tier-backlog: #5B9FD4;
  --fc-tier-watch: #94A3B8;
  --fc-tier-skip: #64748B;
}

.block-container {
  padding-top: 1.25rem;
  padding-bottom: 2rem;
  max-width: 1180px;
}

/* Metrics — never hardcode light gray boxes on dark theme */
div[data-testid="stMetric"] {
  background: var(--secondary-background-color) !important;
  border: 1px solid var(--fc-border) !important;
  border-radius: 12px !important;
  padding: 0.75rem 1rem !important;
  box-shadow: none !important;
}
div[data-testid="stMetric"] label {
  color: var(--fc-muted) !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-color) !important;
}

h1 {
  font-size: 1.65rem !important;
  font-weight: 650 !important;
  letter-spacing: -0.02em;
  color: var(--text-color) !important;
}
h2, h3 {
  color: var(--text-color) !important;
}

/* Caption + markdown links */
[data-testid="stCaptionContainer"], .stCaption {
  color: var(--fc-muted) !important;
}
a {
  color: var(--fc-accent) !important;
}

/* Sidebar coherence */
section[data-testid="stSidebar"] {
  border-right: 1px solid var(--fc-border);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
  color: var(--text-color) !important;
}

/* Bordered containers (opportunity cards) */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--secondary-background-color) !important;
  border: 1px solid var(--fc-border) !important;
  border-radius: 12px !important;
}

/* Primary button — match accent, not default salmon */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
  background-color: var(--fc-accent) !important;
  border: 1px solid var(--fc-accent) !important;
  color: #0F1419 !important;
  font-weight: 600;
  border-radius: 10px !important;
}
.stButton > button[kind="primary"]:hover {
  filter: brightness(1.08);
}

/* Trend pick tiles (secondary buttons) */
.stButton > button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
  background: var(--secondary-background-color) !important;
  border: 1px solid var(--fc-border) !important;
  color: var(--text-color) !important;
  border-radius: 10px !important;
  min-height: 3.2rem;
  white-space: normal !important;
  line-height: 1.25 !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--fc-accent) !important;
  background: var(--fc-accent-soft) !important;
}

/* Link button secondary style */
.stLinkButton > a {
  border-radius: 10px !important;
  border: 1px solid var(--fc-border) !important;
  background: transparent !important;
  color: var(--fc-accent) !important;
}
.stLinkButton > a:hover {
  background: var(--fc-accent-soft) !important;
  color: var(--text-color) !important;
}

/* Multiselect chips */
span[data-baseweb="tag"] {
  background-color: var(--fc-accent-soft) !important;
  border: 1px solid var(--fc-border) !important;
}
span[data-baseweb="tag"] span,
span[data-baseweb="tag"] svg {
  color: var(--text-color) !important;
  fill: var(--text-color) !important;
}

/* Select / input fields */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] {
  background-color: var(--secondary-background-color) !important;
  border-color: var(--fc-border) !important;
}

/* Slider */
div[data-testid="stSlider"] [role="slider"] {
  background-color: var(--fc-accent) !important;
}

/* Dataframe — avoid pure black grid on dark app */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] canvas,
[data-testid="stDataFrame"] [data-testid="glideDataEditor"] {
  background-color: var(--secondary-background-color) !important;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--fc-border);
  border-radius: 12px;
  overflow: hidden;
}

/* Alerts (info / warning / error) */
div[data-testid="stAlert"] {
  background-color: var(--secondary-background-color) !important;
  border: 1px solid var(--fc-border) !important;
  color: var(--text-color) !important;
}
div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
  color: var(--text-color) !important;
}

/* Expanders */
details[data-testid="stExpander"] {
  border: 1px solid var(--fc-border);
  border-radius: 12px;
  background: var(--secondary-background-color);
}

.fc-trending-chip {
  display: inline-block;
  margin: 0.15rem 0.35rem 0.15rem 0;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  background: var(--fc-accent-soft);
  border: 1px solid var(--fc-border);
  color: var(--text-color);
  font-size: 0.85rem;
}

.fc-opp {
  border-left: 4px solid var(--fc-tier-backlog);
  padding: 0.15rem 0 0.15rem 0.85rem;
  margin: 0;
}
.fc-opp--catch { border-left-color: var(--fc-tier-catch); }
.fc-opp--soon { border-left-color: var(--fc-tier-soon); }
.fc-opp--backlog { border-left-color: var(--fc-tier-backlog); }
.fc-opp--watch { border-left-color: var(--fc-tier-watch); }
.fc-opp--skip { border-left-color: var(--fc-tier-skip); }

.fc-opp-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}
.fc-opp-hint {
  color: var(--fc-muted);
  font-size: 0.88rem;
  margin-bottom: 0.45rem;
}
.fc-opp-meta {
  color: var(--fc-muted);
  font-size: 0.82rem;
  line-height: 1.35;
}
.fc-opp-score {
  color: var(--fc-accent);
  font-weight: 600;
}

.fc-footer {
  color: var(--fc-muted);
  font-size: 0.8rem;
  margin-top: 1.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--fc-border);
}

.fc-pipeline {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0 1.25rem 0;
}
.fc-step {
  flex: 1 1 140px;
  background: var(--secondary-background-color);
  border: 1px solid var(--fc-border);
  border-radius: 12px;
  padding: 0.65rem 0.85rem;
}
.fc-step-num {
  color: var(--fc-accent);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.fc-step-title {
  color: var(--text-color);
  font-weight: 600;
  font-size: 0.92rem;
  margin: 0.15rem 0;
}
.fc-step-val {
  color: var(--fc-muted);
  font-size: 0.82rem;
}

.fc-badges { margin: 0.35rem 0 0.5rem 0; }
.fc-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  margin-right: 0.35rem;
  border: 1px solid var(--fc-border);
}
.fc-badge--on { background: var(--fc-accent-soft); color: var(--fc-accent); }
.fc-badge--off { background: transparent; color: var(--fc-muted); opacity: 0.65; }

.fc-score-bar {
  height: 6px;
  border-radius: 999px;
  background: rgba(232, 237, 244, 0.08);
  overflow: hidden;
  margin: 0.35rem 0 0.5rem 0;
  display: flex;
}
.fc-score-seg-ac { background: #5B9FD4; }
.fc-score-seg-tr { background: #FBBF24; }
.fc-score-seg-lt { background: #34D399; }
.fc-score-seg-pn { background: #F87171; }

/* Streamlit 1.66 — hide "Made with Streamlit v…" */
[data-testid="stFooter"] {
  position: relative;
}
[data-testid="stFooter"] > div {
  opacity: 0;
  height: 0;
  overflow: hidden;
  pointer-events: none;
}
[data-testid="stFooter"]::after {
  content: "Fresh Calendars News Radar · US long-tail";
  display: block;
  text-align: center;
  color: rgba(232, 237, 244, 0.55);
  font-size: 0.75rem;
  padding: 0.35rem 0 0.85rem 0;
}
</style>
"""

SCORE_LABELS = {
    "autocomplete": ("AC", "fc-score-seg-ac"),
    "related": ("Trends Related", "fc-score-seg-tr"),
    "trending_rss": ("Trending RSS", "fc-score-seg-tr"),
    "trending_volume": ("Search vol.", "fc-score-seg-tr"),
    "interest": ("Interest 7d", "fc-score-seg-tr"),
    "long_tail": ("Long-tail", "fc-score-seg-lt"),
    "discover": ("Discover", "fc-score-seg-lt"),
}

TABLE_COLUMNS = [
    "tier", "score", "future_demand", "site_boost", "word_count", "specificity", "query",
    "content_intent", "gsc_impressions", "discover_source", "headline_hint",
    "site_action", "signals", "published_slug",
]

TIER_CLASS = {
    "Catch now": "fc-opp--catch",
    "Write soon": "fc-opp--soon",
    "Backlog": "fc-opp--backlog",
    "Watch": "fc-opp--watch",
    "Skip — published": "fc-opp--skip",
}
