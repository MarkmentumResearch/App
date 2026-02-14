import streamlit as st
st.set_page_config(page_title="Markmentum – Education", layout="wide")

from utils.auth import verify_proof, make_proof, make_session, verify_session, restore_session_from_cookie2

session = st.session_state.get("session")

if not st.session_state.get("authenticated"):
    if not verify_session(session):
        if not restore_session_from_cookie2():
            st.stop()
            home_url = "https://www.markmentumresearch.com/login"
            st.markdown(
                f'<meta http-equiv="refresh" content="0; url={home_url}" />',
                unsafe_allow_html=True
            )
            st.stop()

import base64
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import streamlit.components.v1 as components
import os

# -------------------------
# Page & shared style
# -------------------------
# --- Typography + image scaling to match About page ---
st.markdown("""
<style>
/* Mirror About page font stack */
html, body, [class^="css"], .stMarkdown, .stDataFrame, .stTable, .stText, .stButton {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

/* Education content container + default sizing */
.edu-wrapper {
  max-width: 900px;          /* same visual width as About’s main column */
  margin: 0 auto;
  padding: 0 6px;
  line-height: 1.5;
}
.edu-wrapper p, .edu-wrapper li { font-size: 16px; }
.edu-wrapper h1 { font-size: 28px; font-weight: 700; margin: 16px 0 8px; }
.edu-wrapper h2 { font-size: 24px; font-weight: 700; margin: 16px 0 8px; }
.edu-wrapper h3 { font-size: 21px; font-weight: 600; margin: 14px 0 8px; }

/* Make screenshots fit nicely on Cloud */
.edu-wrapper img {
  max-width: 100% !important;
  height: auto !important;
  display: block;
  margin: 8px auto;
}
</style>
""", unsafe_allow_html=True)

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

EXCEL_BLUE   = "#4472C4"
EXCEL_ORANGE = "#FFC000"
EXCEL_GRAY   = "#A6A6A6"
DEFAULT_TICKER = "SPY"

# -------------------------
# Paths
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR  = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"

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

# -------------------------
# Header: logo centered - end
# -------------------------

st.markdown(
        f"""
        <div style="text-align:center; margin:-6px 0 14px;
                    font-size:18px; font-weight:600; color:#1a1a1a;">
            Education - How to Use
        </div>
        """,
        unsafe_allow_html=True,
    )

st.cache_data.clear()

# ---------- Render the Education .docx as-is ----------
import io
import os
from pathlib import Path
import streamlit as st

DOCX_PATH = DATA_DIR / "Educational Page.docx"

def render_docx_as_html(docx_path: Path):
    """Render a .docx (with screenshots) as HTML inside a 900px column."""
    try:
        import mammoth  # ensure mammoth is in requirements.txt (e.g., mammoth==1.11.0)
    except Exception:
        st.error('Missing dependency: **mammoth**. Add `mammoth==1.11.0` to requirements.txt and redeploy.')
        if Path(docx_path).exists():
            with open(docx_path, "rb") as f:
                st.download_button("Download the Education doc (DOCX)", f, file_name=Path(docx_path).name)
        return

    if not Path(docx_path).exists():
        st.error(f"Couldn't find: `{docx_path}`")
        return

    with open(docx_path, "rb") as f:
        html_body = mammoth.convert_to_html(f).value  # images are inlined as data URIs by default

    # Scoped styles so this block matches About page typography and scales screenshots
    scoped_css = """
    <style>
      .edu-wrapper {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 6px;
        line-height: 1.5;
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      }
      .edu-wrapper p, .edu-wrapper li { font-size: 16px; }
      .edu-wrapper h1 { font-size: 28px; font-weight: 700; margin: 16px 0 8px; }
      .edu-wrapper h2 { font-size: 24px; font-weight: 700; margin: 16px 0 8px; }
      .edu-wrapper h3 { font-size: 21px; font-weight: 600; margin: 14px 0 8px; }
      .edu-wrapper img {
        max-width: 100% !important;
        height: auto !important;
        display: block;
        margin: 8px auto;
      }
    </style>
    """

    wrapped = f'{scoped_css}<div class="edu-wrapper">{html_body}</div>'
    st.components.v1.html(wrapped, height=1200, scrolling=True)
# Call it
#st.markdown("### Education")
render_docx_as_html(DOCX_PATH)


PDF_PATH = Path("data/Educational Page.pdf")   # adjust name if different

def render_education_download():
    if PDF_PATH.exists():
        # read once so Streamlit can serve bytes
        pdf_bytes = PDF_PATH.read_bytes()
        # center the button (optional)
        left, mid, right = st.columns([1, 2, 1])
        with mid:
            st.download_button(
                "📄 Download Education (PDF)",
                data=pdf_bytes,
                file_name="Markmentum_Education.pdf",
                mime="application/pdf",
                type="secondary",
            )
    else:
        st.info(f"Education PDF not found at: `{PDF_PATH}`")

# call this after rendering the page content
render_education_download()


# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("---")
st.markdown(
    """
    <div style="font-size: 12px; color: gray;">
    © 2026 Markmentum Research LLC. <b>Disclaimer</b>: This content is for informational purposes only. 
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