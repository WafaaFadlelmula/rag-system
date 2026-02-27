"""
ECOICE Assistant — Query Monitoring Dashboard
================================================
Page 2 of the multipage Streamlit app.
Reads from the FastAPI monitoring endpoints to display:
  - Cumulative cost tracker
  - Latency chart over time
  - Retrieval score chart over time
  - Full query log table with per-row flag-for-review controls
"""

import json

import pandas as pd
import requests
import streamlit as st

from auth import require_auth, show_logout_button

# Read API base URL from secrets, fall back to localhost for local dev
try:
    API_BASE = st.secrets["api"]["base_url"]
except Exception:
    API_BASE = "http://localhost:8000/api/v1"

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Monitoring — ECOICE Assistant",
    page_icon="📊",
    layout="wide",
)

require_auth()

# ---------------------------------------------------------------------------
# CSS — matches the chat page branding
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f0f4f8;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stMain"] { background-color: #f0f4f8; }

    [data-testid="stSidebar"] {
        background: linear-gradient(160deg, #0d1f2d 0%, #0a3d47 100%);
    }
    [data-testid="stSidebar"] * { color: #d0eaf0 !important; }
    [data-testid="stSidebar"] hr { border-color: #1a5060 !important; }

    .monitor-header {
        background: linear-gradient(135deg, #0d1f2d 0%, #0a3d47 60%, #00838f 100%);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,188,212,0.15);
    }
    .monitor-header h1 {
        color: white !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
    }
    .monitor-header p {
        color: #80deea !important;
        margin: 6px 0 0 0 !important;
        font-size: 0.88rem !important;
    }

    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #d0eaf0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0,188,212,0.06);
    }
    [data-testid="stMetricValue"] { color: #0d1f2d !important; }
    [data-testid="stMetricLabel"] { color: #6b8fa0 !important; font-size: 0.82rem !important; }

    .section-heading {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0d1f2d;
        margin: 24px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid #00BCD4;
    }

    [data-testid="stSidebar"] .stButton > button {
        background: rgba(0,188,212,0.1) !important;
        color: #00BCD4 !important;
        border: 1px solid rgba(0,188,212,0.4) !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #00BCD4 !important;
        color: #0d1f2d !important;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<p style='font-size:0.9rem; font-weight:700; color:#00BCD4;'>📊 Monitoring</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.82rem;'>Live dashboard for every query processed "
        "by the RAG pipeline. Flag queries for manual review.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    auto_refresh = st.toggle("Auto-refresh (30 s)", value=False)
    if st.button("🔄 Refresh now", use_container_width=True):
        st.rerun()

    st.divider()
    show_logout_button()

if auto_refresh:
    import time as _time
    _time.sleep(30)
    st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="monitor-header">
    <h1>📊 Query Monitoring Dashboard</h1>
    <p>Every query is automatically logged · Flag queries for review · Refresh to see new data</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Fetch data from API
# ---------------------------------------------------------------------------
try:
    resp = requests.get(f"{API_BASE}/monitor/queries", timeout=5)
    resp.raise_for_status()
    rows = resp.json()
except requests.exceptions.ConnectionError:
    st.error("Cannot connect to the API. Start the server with `make serve`.")
    st.stop()
except Exception as exc:
    st.error(f"Failed to load query log: {exc}")
    st.stop()

if not rows:
    st.info("No queries logged yet. Start chatting on the Chat page!")
    st.stop()

# ---------------------------------------------------------------------------
# Build DataFrame
# ---------------------------------------------------------------------------
df = pd.DataFrame(rows)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values("timestamp").reset_index(drop=True)

df["sources_list"] = df["sources_cited"].apply(
    lambda v: ", ".join(json.loads(v)) if v else "—"
)
df["flagged_bool"] = df["flagged"].astype(bool)

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
total_queries = len(df)
total_cost    = df["cost_usd"].sum(skipna=True)
avg_latency   = df["latency_ms"].mean(skipna=True)
avg_score     = df["top_reranker_score"].mean(skipna=True)
flagged_count = df["flagged_bool"].sum()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Queries",      total_queries)
m2.metric("Cumulative Cost",    f"${total_cost:.5f}")
m3.metric("Avg Latency",        f"{avg_latency:.0f} ms"  if pd.notna(avg_latency) else "—")
m4.metric("Avg Top Score",      f"{avg_score:.3f}"       if pd.notna(avg_score)   else "—")
m5.metric("Flagged for Review", int(flagged_count))

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
st.markdown('<p class="section-heading">Latency over time</p>', unsafe_allow_html=True)
latency_df = df[df["latency_ms"].notna()].set_index("timestamp")[["latency_ms"]]
latency_df.columns = ["Latency (ms)"]
st.line_chart(latency_df, color="#00BCD4")

st.markdown('<p class="section-heading">Top reranker score over time</p>',
            unsafe_allow_html=True)
score_df = df[df["top_reranker_score"].notna()].set_index("timestamp")[["top_reranker_score"]]
score_df.columns = ["Top Reranker Score"]
st.line_chart(score_df, color="#00838f")

# ---------------------------------------------------------------------------
# Query log table with flag editing
# ---------------------------------------------------------------------------
st.markdown('<p class="section-heading">Query log</p>', unsafe_allow_html=True)
st.caption(
    "Toggle the 🚩 checkbox to flag a query for review, "
    "then click **Save flag changes** below the table."
)

display_cols = ["id", "timestamp", "question", "answer",
                "sources_list", "cost_usd", "latency_ms",
                "top_reranker_score", "flagged_bool"]
display_df = (
    df[display_cols]
    .sort_values("timestamp", ascending=False)
    .reset_index(drop=True)
)

edited = st.data_editor(
    display_df,
    column_config={
        "id": st.column_config.NumberColumn("ID", width="small"),
        "timestamp": st.column_config.DatetimeColumn(
            "Timestamp", format="YYYY-MM-DD HH:mm:ss", width="medium"
        ),
        "question":            st.column_config.TextColumn("Question",      width="large"),
        "answer":              st.column_config.TextColumn("Answer",        width="large"),
        "sources_list":        st.column_config.TextColumn("Sources cited", width="medium"),
        "cost_usd":            st.column_config.NumberColumn("Cost (USD)",  format="$%.5f",   width="small"),
        "latency_ms":          st.column_config.NumberColumn("Latency (ms)", format="%.0f ms", width="small"),
        "top_reranker_score":  st.column_config.NumberColumn("Top score",   format="%.3f",    width="small"),
        "flagged_bool":        st.column_config.CheckboxColumn("🚩 Flag",   width="small"),
    },
    disabled=["id", "timestamp", "question", "answer", "sources_list",
              "cost_usd", "latency_ms", "top_reranker_score"],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

# Detect flag changes and offer save button
original_flags = dict(zip(display_df["id"], display_df["flagged_bool"]))
edited_flags   = dict(zip(edited["id"],     edited["flagged_bool"]))
changes = {
    qid: flagged
    for qid, flagged in edited_flags.items()
    if original_flags.get(qid) != flagged
}

if changes:
    n = len(changes)
    if st.button(f"💾 Save {n} flag change{'s' if n != 1 else ''}", type="primary"):
        errors = []
        for qid, flagged in changes.items():
            try:
                r = requests.post(
                    f"{API_BASE}/monitor/flag/{int(qid)}",
                    json={"flagged": flagged},
                    timeout=5,
                )
                r.raise_for_status()
            except Exception as exc:
                errors.append(f"ID {qid}: {exc}")
        if errors:
            st.error("Some updates failed:\n" + "\n".join(errors))
        else:
            st.success(f"Saved {n} flag change{'s' if n != 1 else ''}.")
            st.rerun()
