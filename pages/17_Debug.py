import streamlit as st
import time

st.set_page_config(page_title="Cookie Debug", layout="wide")

from utils.auth import restore_session_from_cookie2

if not st.session_state.get("authenticated"):
    if not restore_session_from_cookie2():
        st.stop()



import extra_streamlit_components as stx
from utils.auth import COOKIE_NAME, verify_cookie_value  # adjust if names differ

def mask(s: str, keep: int = 10) -> str:
    if not s:
        return ""
    if len(s) <= keep * 2:
        return s
    return f"{s[:keep]}...{s[-keep:]}"

st.title("🔒 Cookie Debug")

cm = stx.CookieManager(key="mr_cookie_mgr")  # must match your app key

raw = cm.get(COOKIE_NAME)

st.subheader("Raw cookie read")
st.write("COOKIE_NAME:", COOKIE_NAME)
st.write("Type:", type(raw).__name__)
st.write("Is None:", raw is None)
st.write("Falsy (not raw):", not raw)

if raw:
    st.code(mask(raw), language="text")
else:
    st.info("Cookie not available yet (or does not exist).")

st.divider()
st.subheader("Decoded / expiry check (verify_cookie_value)")

if raw:
    member_id = verify_cookie_value(raw)
    st.write("verify_cookie_value(raw) returned:", member_id)
else:
    st.write("Skipped decode because raw is None/empty.")

st.divider()
st.subheader("Hydration test (rerun)")

if st.button("Force rerun"):
    st.session_state["_debug_rerun_at"] = int(time.time())
    st.rerun()

st.write("Last debug rerun at:", st.session_state.get("_debug_rerun_at"))