"""
Shared authentication helper for all Streamlit pages.

Behaviour:
- If [auth] is absent from st.secrets (e.g. local dev without secrets.toml),
  authentication is skipped and every user is allowed in.
- If [auth] is present, a branded login form is shown before any page content.
  Credentials are checked against st.secrets["auth"]["username"] and ["password"].
- Session state key: "authenticated"
"""

import streamlit as st


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def require_auth() -> None:
    """
    Call this as the very first statement in every page (after set_page_config).
    If the user is not authenticated it renders the login form and stops execution
    so that no page content is shown.
    """
    if not _auth_configured():
        return          # No secrets set up — allow access (local dev)

    if st.session_state.get("authenticated"):
        return          # Already logged in

    _render_login_form()
    st.stop()           # Halt the rest of the page


def show_logout_button() -> None:
    """
    Place this inside a `with st.sidebar:` block.
    Only renders when auth is configured.
    """
    if not _auth_configured():
        return
    if st.button("🔒 Sign out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _auth_configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def _render_login_form() -> None:
    st.markdown("""
    <style>
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #f0f4f8;
            font-family: 'Inter', 'Segoe UI', sans-serif;
        }
        #MainMenu { visibility: hidden; }
        footer     { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #0d1f2d 0%, #0a3d47 60%, #00838f 100%);
            border-radius: 16px;
            padding: 36px 36px 28px 36px;
            margin: 60px 0 24px 0;
            box-shadow: 0 4px 24px rgba(0,188,212,0.22);
            text-align: center;
        ">
            <h2 style="color:white; margin:0 0 6px 0; font-size:1.6rem; font-weight:800;">
                ECOICE Assistant
            </h2>
            <p style="color:#80deea; margin:0; font-size:0.88rem;">
                Sign in to continue
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password",
                                     placeholder="Enter password")
            submitted = st.form_submit_button(
                "Sign in", use_container_width=True, type="primary"
            )

        if submitted:
            if (username == st.secrets["auth"]["username"] and
                    password == st.secrets["auth"]["password"]):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect username or password.", icon="🔒")
