# utils/require_auth.py

import streamlit as st
from utils.auth import restore_auth_from_cookie

HOME_URL = "https://www.markmentumresearch.com"

def require_auth() -> None:
    """
    Use on every protected page (pages/* and any gated root page).
    Restores session auth from signed cookie if needed.
    Redirects out if not authenticated.
    """
    # If session already authenticated, we're good
    if st.session_state.get("authenticated") is True:
        return

    # Try to restore from cookie (refresh/new tab/new session)
    if restore_auth_from_cookie():
        return

    # Not authenticated -> bounce to home/login
    st.markdown(
        f"""<meta http-equiv="refresh" content="0; url={HOME_URL}" />""",
        unsafe_allow_html=True,
    )
    st.stop()