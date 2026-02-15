import streamlit as st
st.set_page_config(page_title="Markmentum - Universe", layout="wide")

from utils.auth import verify_proof, make_proof, restore_session_from_cookie2

# --- Gate Morning Compass ---
if not st.session_state.get("authenticated"):
        if not restore_session_from_cookie2():
            home_url = "https://www.markmentumresearch.com/reauth"
            st.markdown(
                f'<meta http-equiv="refresh" content="0; url={home_url}" />',
                unsafe_allow_html=True
            )
            st.stop()


from pathlib import Path
import base64
import pandas as pd
import altair as alt
import sys
import numpy as np
from urllib.parse import quote_plus
import os
import os

# -------------------------
# Page & shared style
# -------------------------

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


# === Universe – All Instruments (index hidden + fixed % formatting) ===

@st.cache_data(ttl=600)
def load_universe(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        st.error("Could not find ticker_data.csv. Place it in ./data or the working directory.")
        st.stop()

    df = pd.read_csv(csv_path)

    expected = [
        "Ticker", "Ticker_name", "Category", "Date", "Close",
        "day_pct_change", "week_pct_change", "month_pct_change", "quarter_pct_change",
    ]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        st.error(f"CSV is missing required columns: {missing}")
        st.stop()

    # types
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    for c in ["day_pct_change", "week_pct_change", "month_pct_change", "quarter_pct_change"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # friendly headers
    df = df.rename(
        columns={
            "Ticker_name": "Name",
            "day_pct_change": "Day %",
            "week_pct_change": "Week %",
            "month_pct_change": "Month %",
            "quarter_pct_change": "Quarter %",
        }
    )

    # stable ordering
    return df.sort_values(["Category", "Ticker"], kind="mergesort").reset_index(drop=True)

df = load_universe(CSV_PATH)

st.markdown(
    '<h2 style="text-align:center; margin:0.25rem 0 0.5rem;">Universe – All Instruments</h2>',
    unsafe_allow_html=True,
)
st.markdown(
    '<hr style="margin-top:0.5rem;margin-bottom:0.75rem;border:none;border-top:1px solid #e6e6e6;">',
    unsafe_allow_html=True,
)

# A narrow center column with equal side gutters to visually center everything
pad_l, center, pad_r = st.columns([1, 4, 1], gap="small")

with center:
    # Top row inside the centered column: search on the left, last-updated on the right
    tleft, tright = st.columns([3, 1])
    with tleft:
        q = st.text_input("Search (ticker or name)", placeholder="Type to filter…")
    with tright:
        if df["Date"].notna().any():
            st.caption(f"Last updated: {pd.to_datetime(df['Date']).max().date():%Y-%m-%d}")
        else:
            st.caption("Last updated: —")

    # Filter the view based on the query
    if q:
        ql = q.strip().lower()
        view = df[
            df["Ticker"].str.lower().str.contains(ql, na=False)
            | df["Name"].str.lower().str.contains(ql, na=False)
        ].copy()
    else:
        view = df.copy()

    # Compact column widths + correct percent formatting
    cc = st.column_config
    table_config = {
        "Ticker":     cc.TextColumn("Ticker", width="small"),
        "Name":       cc.TextColumn("Name", width="large"),
        "Category":   cc.TextColumn("Category", width="medium"),
        "Date":       cc.DateColumn("Date", format="YYYY-MM-DD", width="small"),
        "Close":      cc.NumberColumn("Close", format="%.2f", width="small"),
        "Day %":      cc.NumberColumn("Day %",     format="%+.2f%%", width="small"),
        "Week %":     cc.NumberColumn("Week %",    format="%+.2f%%", width="small"),
        "Month %":    cc.NumberColumn("Month %",   format="%+.2f%%", width="small"),
        "Quarter %":  cc.NumberColumn("Quarter %", format="%+.2f%%", width="small"),
    }

    # Render the table centered (because it's inside the center column)
    st.dataframe(
        view[["Ticker", "Name", "Category", "Date", "Close", "Day %", "Week %", "Month %", "Quarter %"]],
        hide_index=True,
        use_container_width=True,  # fills the center column width
        height=560,
        column_config=table_config,
    )

    # Download button centered with the table (same column)
    st.download_button(
        "Download current view (CSV)",
        view.to_csv(index=False).encode("utf-8"),
        file_name="universe_view.csv",
        type="secondary",
    )

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