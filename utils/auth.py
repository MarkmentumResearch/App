# utils/auth.py

import os
import time
import hmac
import hashlib
import base64
import streamlit as st
import extra_streamlit_components as stx


def _cookie_mgr():
    # Key should be stable across reruns/pages
    return stx.CookieManager(key="mr_cookie_mgr")


COOKIE_NAME = "mr_auth"
COOKIE_TTL_SECONDS = 60 * 60 * 12  # 12 hours

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _cookie_secret() -> str:
    # You already have this in Render
    return os.environ.get("MR_AUTH_COOKIE_SECRET", "")

def _sign(payload: str) -> str:
    secret = _cookie_secret()
    if not secret:
        return ""
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())

def make_cookie_value(member_id: str, ttl_seconds: int = COOKIE_TTL_SECONDS) -> str:
    member_id = (member_id or "").strip()
    exp = int(time.time()) + int(ttl_seconds)
    payload = f"{member_id}|{exp}"
    sig = _sign(payload)
    return f"{payload}|{sig}"

def verify_cookie_value(cookie_value: str) -> str | None:
    secret = _cookie_secret()
    if not secret or not cookie_value:
        return None

    parts = cookie_value.split("|")
    if len(parts) != 3:
        return None

    member_id, exp_s, sig = parts
    member_id = (member_id or "").strip()

    try:
        exp = int(exp_s)
    except Exception:
        return None

    if not member_id or exp < int(time.time()):
        return None

    payload = f"{member_id}|{exp}"
    expected = _sign(payload)
    if not expected or not hmac.compare_digest(expected, sig):
        return None

    return member_id

def set_auth_cookie(member_id: str) -> None:
    val = make_cookie_value(member_id)
    cm = _cookie_mgr()
    cm.set(
        COOKIE_NAME,
        val,
        max_age=COOKIE_TTL_SECONDS,
        path="/",
    )


def restore_session_from_cookie() -> bool:
    cm = _cookie_mgr()
    raw = cm.get(COOKIE_NAME)

    # ONE rerun to allow CookieManager to hydrate after navigation
    if raw is None and not st.session_state.get("_cookie_retry_done"):
        st.session_state["_cookie_retry_done"] = True
        st.rerun()

    # treat "" as missing too
    if not raw:
        return False

    member_id = verify_cookie_value(raw)  # keep your expiry check
    if not member_id:
        return False

    st.session_state["authenticated"] = True
    st.session_state["member_id"] = member_id
    st.session_state["auth_restored_at"] = int(time.time())

    # reset retry flag once we're in
    st.session_state["_cookie_retry_done"] = False
    return True

def restore_session_from_cookie2() -> bool:
    cm = _cookie_mgr()
    raw = cm.get(COOKIE_NAME)

    # 1) CookieManager often returns None on the first pass after navigation.
    #    Give it ONE rerun to hydrate from the browser.
    if raw is None and not st.session_state.get("_cookie_retry_done"):
        st.session_state["_cookie_retry_done"] = True
        st.rerun()

    # 2) Treat empty string as missing too
    if not raw:
        return False

    st.session_state["authenticated"] = True
    st.session_state["auth_restored_at"] = int(time.time())
    return True