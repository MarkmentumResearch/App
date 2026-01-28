# -------------------------
# Markmentum — Ranking (Model Scores + Sharpe Rank + Sharpe Ratio + Sharpe Ratio 30D Change)
# -------------------------

from pathlib import Path
import base64
import pandas as pd
import altair as alt
import streamlit as st
import sys
import numpy as np
from urllib.parse import quote_plus
import os

st.cache_data.clear()
# 13_Contact.py (or wherever your Contact page lives)
#import streamlit as st
import requests

st.set_page_config(page_title="Contact", page_icon="✉️", layout="wide")
# -------------------------
# Page & shared style
# -------------------------
#st.set_page_config(page_title="Markmentum - Universe", layout="wide")

st.markdown(
    """
<style>
div[data-testid="stHorizontalBlock"] { min-width: 1100px; }
section.main > div { max-width: 1700px; margin-left: auto; margin-right: auto; }
html, body, [class^="css"], .stMarkdown, .stDataFrame, .stTable, .stText, .stButton {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}
.card {
  border: 1px solid #cfcfcf;
  border-radius: 8px;
  background: #fff;
  padding: 14px 14px 10px 14px;
}
.card h3 { margin: 0 0 10px 0; font-size: 16px; font-weight: 700; color:#1a1a1a; }
.small { font-size:12px; color:#666; }

/* keep the selector compact (≈36 chars) */
div[data-baseweb="select"] {
  max-width: 36ch !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown("""
<style>
/* ========== Bigger, easier-to-grab scrollbars (light theme) ========== */

/* Global page scrollbar — Chromium/WebKit */
:root::-webkit-scrollbar        { width: 16px; height: 16px; }
:root::-webkit-scrollbar-track  { background: #f2f2f2; }
:root::-webkit-scrollbar-thumb  { background: #bdbdbd; border-radius: 8px; border: 3px solid #f2f2f2; }
:root::-webkit-scrollbar-thumb:hover { background: #9a9a9a; }

/* Inner scrollables (tables/dataframes/expander bodies) — Chromium/WebKit */
div[tabindex="0"]::-webkit-scrollbar        { width: 14px; height: 14px; }
div[tabindex="0"]::-webkit-scrollbar-track  { background: #f2f2f2; }
div[tabindex="0"]::-webkit-scrollbar-thumb  { background: #bdbdbd; border-radius: 8px; border: 3px solid #f2f2f2; }
div[tabindex="0"]::-webkit-scrollbar-thumb:hover { background: #9a9a9a; }

/* Firefox */
html { scrollbar-width: thick; scrollbar-color: #bdbdbd #f2f2f2; }
</style>
""", unsafe_allow_html=True)


def _image_b64(p: Path) -> str:
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

# -------------------------
# Paths
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR  = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"



CSV_PATH  = DATA_DIR / "ticker_data.csv"   # model_score


# -------------------------
# Header: logo centered
# -------------------------
if LOGO_PATH.exists():
    st.markdown(
        f"""
        <div style="text-align:center; margin: 8px 0 16px;">
            <img src="data:image/png;base64,{_image_b64(LOGO_PATH)}" width="440">
        </div>
        """,
        unsafe_allow_html=True,
    )

#st.markdown('<h2 style="text-align:center; margin:0.25rem 0 0.5rem;">Contact Us </h2>',unsafe_allow_html=True,)
st.markdown("---")



# 13_Contact.py (or wherever your Contact page lives)




st.title("Contact Markmentum Research")
st.write("Have a question or want to get in touch? Send us a note below.")

# Build endpoint from secrets
fs = st.secrets.get("formspree", {})
endpoint = fs.get("endpoint") or f"https://formspree.io/f/{fs.get('id', '').strip()}"
if not endpoint or endpoint.endswith("/f/"):
    st.error("Formspree endpoint is not configured. Add it to .streamlit/secrets.toml under [formspree].")
    st.stop()

with st.form("contact_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Your name*", placeholder="Jane Doe")
    with col2:
        email = st.text_input("Your email*", placeholder="you@example.com")

    message = st.text_area("Message*", placeholder="How can we help?", height=160)

    # Optional extra fields Formspree can store
    st.write("")  # spacer
    send = st.form_submit_button("Send message")

    if send:
        if not name or not email or not message:
            st.warning("Please fill out name, email, and message.")
        else:
            payload = {
                "name": name,
                "email": email,        # Formspree will use this as reply-to if configured
                "message": message,
                "from_page": "Contact",  # extra context
                "_subject": "New message from Markmentum Contact",
                "_captcha": "false",     # optional (Formspree supports this)
            }
            try:
                r = requests.post(
                    endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    timeout=10,
                )
                if r.status_code in (200, 201):
                    st.success("Thanks! Your message was sent successfully.")
                else:
                    # Formspree returns helpful JSON errors
                    try:
                        err = r.json()
                    except Exception:
                        err = {}
                    st.error(f"Could not send message (status {r.status_code}). {err}")
            except requests.RequestException as e:
                st.error(f"Network error while sending message: {e}")

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("---")
st.markdown(
    """
    <div style="font-size: 12px; color: gray;">
    © 2026 Markmentum Research. <b>Disclaimer</b>: This content is for informational purposes only. 
    Nothing herein constitutes an offer to sell, a solicitation of an offer to buy, or a recommendation regarding any security, 
    investment vehicle, or strategy. It does not represent legal, tax, accounting, or investment advice by Markmentum Research LLC 
    or its employees. The information is provided without regard to individual objectives or risk parameters and is general, 
    non-tailored, and non-specific. Sources are believed to be reliable, but accuracy and completeness are not guaranteed. 
    Markmentum Research LLC is not responsible for errors, omissions, or losses arising from use of this material. 
    Investments involve risk, and financial markets are subject to fluctuation. Consult your financial professional before 
    making investment decisions.
    </div>
    """,
    unsafe_allow_html=True,
)