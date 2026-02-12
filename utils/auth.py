# utils/auth.py

import os
import time
import hmac
import hashlib
import base64
import streamlit as st

# -----------------------------
# Config
# -----------------------------
COOKIE_NAME = "mr_auth"
DEFAULT_TTL_SECONDS = 60 * 60 * 12  # 12 hours

# IMPORTANT: set this in Render -> Environment
# MR_AUTH_COOKIE_SECRET = <long random string 32+ chars>
AUTH_SECRET = os.environ.get("MR_AUTH_COOKIE_SECRET", "")

# -----------------------------
# Signing helpers (tamper-proof)
# -----------------------------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _sign(payload: str) -> str:
    if not AUTH_SECRET:
        return ""
    return _b64(hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).digest())

def make_cookie_value(member_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """
    Cookie format: member_id|exp|sig
    sig = HMAC(secret, "member_id|exp")
    """
    member_id = (member_id or "").strip()
    exp = int(time.time()) + int(ttl_seconds)
    payload = f"{member_id}|{exp}"
    sig = _sign(payload)
    return f"{payload}|{sig}"

def verify_cookie_value(cookie_value: str) -> str | None:
    """
    Returns member_id if cookie is valid, else None.
    """
    if not AUTH_SECRET:
        return None
    if not cookie_value:
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

    if not member_id:
        return None
    if exp < int(time.time()):
        return None

    payload = f"{member_id}|{exp}"
    expected = _sign(payload)
    if not expected:
        return None

    if not hmac.compare_digest(expected, sig):
        return None

    return member_id

# -----------------------------
# Native cookie helpers
# -----------------------------
def _cookies():
    """
    Streamlit native cookies.
    """
    # Streamlit 1.37+ supports st.context.cookies
    return st.context.cookies

def set_auth_cookie(member_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """
    Sets signed auth cookie using Streamlit native cookies.
    """
    value = make_cookie_value(member_id, ttl_seconds=ttl_seconds)
    # max_age in seconds. Path "/" so it works across pages.
    _cookies().set(COOKIE_NAME,value,max_age=ttl_seconds,path="/",secure=True,samesite="None",)

def clear_auth_cookie() -> None:
    """
    Removes the auth cookie.
    """
    # Setting max_age=0 deletes in browsers
    _cookies().set(COOKIE_NAME,"",max_age=0,path="/",secure=True,samesite="None",)

def restore_auth_from_cookie() -> bool:
    """
    If session_state is not authenticated, try to restore it from cookie.
    Returns True if authenticated after this, else False.
    """
    if st.session_state.get("authenticated") is True:
        return True

    raw = _cookies().get(COOKIE_NAME)
    member_id = verify_cookie_value(raw) if raw else None

    if member_id:
        st.session_state["authenticated"] = True
        st.session_state["member_id"] = member_id
        st.session_state["auth_restored_at"] = int(time.time())
        return True

    return False