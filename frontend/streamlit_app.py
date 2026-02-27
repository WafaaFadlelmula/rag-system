"""
ECOICE Assistant — Streamlit Frontend
==========================================
Connects to the FastAPI backend. Set the backend URL in .streamlit/secrets.toml:
    [api]
    base_url = "http://localhost:8000/api/v1"
"""

import requests
import streamlit as st

from auth import require_auth, show_logout_button

# ---------------------------------------------------------------------------
# Authentication — must come before set_page_config is not possible, but
# require_auth() is called after set_page_config (Streamlit requirement).
# ---------------------------------------------------------------------------

# Read API base URL from secrets, fall back to localhost for local dev
try:
    API_BASE = st.secrets["api"]["base_url"]
except Exception:
    API_BASE = "http://localhost:8000/api/v1"

LOGO_B64 = "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"

st.set_page_config(
    page_title="ECOICE Chatbot Assistant",
    page_icon="🔬",
    layout="wide",
)

require_auth()

# ---------------------------------------------------------------------------
# Full CSS redesign — light professional theme matching Ultracell brand
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* ── Global ── */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f0f4f8;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stMain"] {
        background-color: #f0f4f8;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(160deg, #0d1f2d 0%, #0a3d47 100%);
        border-right: none;
    }
    [data-testid="stSidebar"] * {
        color: #d0eaf0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p {
        color: #a8d4de !important;
        font-size: 0.88rem;
    }
    [data-testid="stSidebar"] hr {
        border-color: #1a5060 !important;
    }

    /* Slider — force teal on every internal element */
    [data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
        background: #00BCD4 !important;
        border-color: #00BCD4 !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] div:nth-child(4) { 
        background: #00BCD4 !important; 
    }
    [data-testid="stSlider"] [data-baseweb="slider"] div:nth-child(3) { 
        background: #c8edf2 !important; 
    }

    /* Toggles — teal, remove label highlight */
    [data-testid="stToggle"] label {
        background: transparent !important;
        padding: 0 !important;
    }
    [data-testid="stToggle"] label:hover {
        background: transparent !important;
    }
    [data-testid="stToggle"] p {
        color: #d0eaf0 !important;
        background: transparent !important;
    }
    /* Toggle track off state */
    [data-testid="stToggle"] [data-baseweb="toggle"] div {
        background-color: #4a6572 !important;
    }
    /* Toggle track on state */
    [data-testid="stToggle"] input:checked + div + div,
    [data-testid="stToggle"] input:checked ~ div[data-baseweb="toggle"] div {
        background-color: #00BCD4 !important;
    }
    [role="switch"][aria-checked="true"] {
        background-color: #00BCD4 !important;
        border-color: #00BCD4 !important;
    }
    [role="switch"][aria-checked="false"] {
        background-color: #4a6572 !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(0,188,212,0.1) !important;
        color: #00BCD4 !important;
        border: 1px solid rgba(0,188,212,0.4) !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        padding: 6px 10px !important;
        text-align: left !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
        margin-bottom: 2px !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #00BCD4 !important;
        color: #0d1f2d !important;
        font-weight: 600 !important;
        border-color: #00BCD4 !important;
    }

    /* ── Main area ── */
    /* Page header bar */
    .rag-header {
        background: linear-gradient(135deg, #0d1f2d 0%, #0a3d47 60%, #00838f 100%);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,188,212,0.15);
    }
    .rag-header h1 {
        color: white !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }
    .rag-header p {
        color: #80deea !important;
        margin: 6px 0 0 0 !important;
        font-size: 0.88rem !important;
    }

    /* Chat messages — user */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: white !important;
        border-radius: 14px !important;
        border: 1px solid #e2ecf0 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        padding: 14px !important;
    }

    /* Chat messages — assistant */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: white !important;
        border-radius: 14px !important;
        border-left: 4px solid #00BCD4 !important;
        border-top: 1px solid #e2ecf0 !important;
        border-right: 1px solid #e2ecf0 !important;
        border-bottom: 1px solid #e2ecf0 !important;
        box-shadow: 0 2px 12px rgba(0,188,212,0.08) !important;
        padding: 14px !important;
    }

    /* Chat input box */
    [data-testid="stChatInput"] {
        background: white !important;
        border-radius: 14px !important;
        border: 2px solid #00BCD4 !important;
        box-shadow: 0 4px 16px rgba(0,188,212,0.12) !important;
    }
    [data-testid="stChatInput"] textarea {
        background: white !important;
        color: #0d1f2d !important;
        font-size: 0.95rem !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background: #f8fbfc !important;
        border: 1px solid #d0eaf0 !important;
        border-radius: 10px !important;
    }

    /* Spinner */
    [data-testid="stSpinner"] { color: #00BCD4 !important; }

    /* Caption text */
    .stCaptionContainer, caption { color: #6b8fa0 !important; }

    /* Chat avatars — replace red with teal */
    [data-testid="stChatMessageAvatarUser"] {
        background-color: #00838f !important;
        color: white !important;
    }
    [data-testid="stChatMessageAvatarAssistant"] {
        background-color: #0d1f2d !important;
        color: #00BCD4 !important;
    }
    /* Override any svg/img inside avatars */
    [data-testid="stChatMessageAvatarUser"] svg,
    [data-testid="stChatMessageAvatarUser"] img {
        filter: none !important;
    }

    /* Hide Streamlit default menu/footer */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# JS override for slider inline styles (Streamlit injects these directly)
st.markdown("""
<script>
function fixColors() {
    // Fix slider filled track (inline style overrides)
    document.querySelectorAll('[data-baseweb="slider"] [data-testid="stSlider"] div').forEach(el => {
        if (el.style.backgroundColor && el.style.backgroundColor.includes('rgb(255')) {
            el.style.backgroundColor = '#00BCD4';
        }
    });
    // Fix toggle switches
    document.querySelectorAll('[role="switch"]').forEach(el => {
        if (el.getAttribute('aria-checked') === 'true') {
            el.style.backgroundColor = '#00BCD4';
        }
    });
}
// Run on load and after any re-render
const observer = new MutationObserver(fixColors);
observer.observe(document.body, { childList: true, subtree: true, attributes: true });
setTimeout(fixColors, 500);
setTimeout(fixColors, 1500);
</script>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 16px 0 12px 0;">
        <img src="data:image/png;base64,{LOGO_B64}"
             style="width:160px; border-radius:8px; margin-bottom:8px;" />
        <div style="height:2px; background:linear-gradient(90deg,transparent,#00BCD4,transparent);
                    border-radius:2px; margin: 8px 16px 0 16px;"/>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        "<p style='text-align:center; font-size:0.85rem;'>Ask questions about the "
        "<b>ECOICE project</b> and <b>C-PON technology</b> across all 8 milestone reports.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    top_k = st.slider("Sources to retrieve", min_value=1, max_value=10, value=5)
    show_sources = st.toggle("Show sources", value=True)
    show_cost = st.toggle("Show token usage & cost", value=True)

    st.divider()

    # Health check
    with st.expander("⚡ System Status", expanded=False):
        try:
            r = requests.get(f"{API_BASE}/health", timeout=3)
            if r.status_code == 200:
                h = r.json()
                st.success("API: Online")
                st.write(f"**Qdrant:** {h['qdrant']}")
                st.write(f"**Chunks:** {h['chunks_loaded']}")
                st.write(f"**Model:** {h['model']}")
            else:
                st.error("API: Error")
        except Exception:
            st.error("API: Offline — run `make serve`")

    st.divider()

    st.markdown("<p style='font-size:0.82rem; font-weight:600; color:#00BCD4;'>💡 Try asking:</p>",
                unsafe_allow_html=True)
    suggested = [
        "What is C-PON?",
        "What are the power consumption results?",
        "How does C-PON compare to spine and leaf?",
        "What AR/VR applications were tested?",
        "What were the Q3 2023 milestones?",
        "What is the latency improvement of C-PON?",
    ]
    for q in suggested:
        if st.button(q, use_container_width=True, key=q):
            st.session_state.prefill = q

    st.divider()
    if st.button("🗑️  Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    show_logout_button()

# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="rag-header">
    <h1>🔬 ECOICE Chatbot Assistant</h1>
    <p>Powered by GPT-4o-mini &nbsp;·&nbsp; Qdrant Vector DB &nbsp;·&nbsp;
       Hybrid Search &nbsp;·&nbsp; Cross-encoder Reranking</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

for msg in st.session_state.messages:
    avatar = "🔵" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and show_sources and msg.get("sources"):
            with st.expander(f"📄 Sources ({len(msg['sources'])})"):
                for i, src in enumerate(msg["sources"], 1):
                    headers = " > ".join(src.get("headers", [])) or "General"
                    score = src.get("rerank_score")
                    score_str = f"  `score={score:.3f}`" if score is not None else ""
                    st.markdown(f"**[{i}] {src['source_file']}** — {headers}{score_str}")
                    st.caption(src["text"][:300] + ("..." if len(src["text"]) > 300 else ""))

        if msg["role"] == "assistant" and show_cost and msg.get("usage"):
            u = msg["usage"]
            st.caption(
                f"🔢 {u['prompt_tokens']} + {u['completion_tokens']} tokens · "
                f"💰 ${u['cost_usd']:.6f}"
            )

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
prefill = st.session_state.pop("prefill", "") if st.session_state.prefill else ""
question = st.chat_input("Ask a question about the ECOICE project...") or prefill

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🔵"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Searching documents and generating answer..."):
            try:
                response = requests.post(
                    f"{API_BASE}/query",
                    json={"question": question, "top_k": top_k, "stream": False},
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()

                answer = data["answer"]
                sources = data.get("sources", [])
                usage = {
                    "prompt_tokens": data["prompt_tokens"],
                    "completion_tokens": data["completion_tokens"],
                    "cost_usd": data["cost_usd"],
                }

                st.markdown(answer)

                if show_sources and sources:
                    with st.expander(f"📄 Sources ({len(sources)})"):
                        for i, src in enumerate(sources, 1):
                            headers = " > ".join(src.get("headers", [])) or "General"
                            score = src.get("rerank_score")
                            score_str = f"  `score={score:.3f}`" if score is not None else ""
                            st.markdown(f"**[{i}] {src['source_file']}** — {headers}{score_str}")
                            st.caption(src["text"][:300] + ("..." if len(src["text"]) > 300 else ""))

                if show_cost:
                    st.caption(
                        f"🔢 {usage['prompt_tokens']} + {usage['completion_tokens']} tokens · "
                        f"💰 ${usage['cost_usd']:.6f}"
                    )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "usage": usage,
                })

            except requests.exceptions.ConnectionError:
                err = "❌ Cannot connect to API. Make sure the server is running: `make serve`"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

            except requests.exceptions.Timeout:
                err = "⏱️ Request timed out. Try again."
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

            except Exception as e:
                err = f"❌ Error: {str(e)}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})