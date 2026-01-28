# 13_Trends.py
# Markmentum — Trends & Changes (ST / MT / LT)

from pathlib import Path
import base64
import pandas as pd
import numpy as np
import streamlit as st
from urllib.parse import quote_plus

# ---------- Page ----------
st.cache_data.clear()
st.set_page_config(page_title="Markmentum - Directional Trends", layout="wide")

# -------------------------
# Paths
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR   = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"

CSV_PATH = DATA_DIR / "qry_graph_data_88.csv"   # <-- single source file for this page

# -------------------------
# Header: logo centered
# -------------------------
def _image_b64(p: Path) -> str:
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

if LOGO_PATH.exists():
    st.markdown(
        f"""
        <div style="text-align:center; margin: 8px 0 16px;">
            <img src="data:image/png;base64,{_image_b64(LOGO_PATH)}" width="440">
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Clickable Deep Dive helper & router (same UX as Performance page)
ADV_VALUE_KEY  = "dd_show_advanced_charts_value"
INFO_VALUE_KEY = "dd_show_information_charts_value"

def _mk_ticker_link(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    if not t:
        return ""

    # current toggle states (default False if not set yet)
    adv_on  = st.session_state.get(ADV_VALUE_KEY, False)
    info_on = st.session_state.get(INFO_VALUE_KEY, False)

    adv_flag  = "1" if adv_on  else "0"
    info_flag = "1" if info_on else "0"

    return (
        f'<a href="?page=Deep%20Dive'
        f'&ticker={quote_plus(t)}'
        f'&adv={adv_flag}'
        f'&info={info_flag}" '
        f'target="_self" rel="noopener" '
        f'style="text-decoration:none; font-weight:600;">{t}</a>'
    )

qp = st.query_params
dest = (qp.get("page") or "").strip().lower()

if dest.replace("%20", " ") == "deep dive":
    t = (qp.get("ticker") or "").strip().upper()
    adv_qp  = (qp.get("adv")  or "0").strip()
    info_qp = (qp.get("info") or "0").strip()

    if t:
        st.session_state["ticker"] = t

        # restore toggle master values for Deep Dive
        st.session_state[ADV_VALUE_KEY]  = (adv_qp == "1")
        st.session_state[INFO_VALUE_KEY] = (info_qp == "1")

        # clean URL – we don't need adv/info/ticker in query params anymore
        st.query_params.clear()
        st.query_params["ticker"] = t

        st.switch_page("pages/09_Deep_Dive_Dashboard.py")

# -------------------------
# Formatting helpers
# -------------------------
def fmt_pct_1(x):
    try:
        if pd.isna(x):
            return ""
        # Treat source as decimal returns (e.g., 0.012 -> 1.2%)
        return f"{float(x)*100:,.1f}%"
    except Exception:
        return ""

def tint_cell(val, cap=0.03, neutral=0.0005):
    """
    val: decimal (e.g., 0.012 = 1.2%)
    cap: magnitude where tint reaches full strength (default 3%)
    neutral: +/- band rendered as no tint (default 0.05%)
    """
    if val is None or pd.isna(val):
        return ""
    try:
        v = float(val)
    except Exception:
        return ""

    # Neutral band (very small values look untinted)
    if -neutral <= v <= neutral:
        bg = "transparent"
    else:
        # Scale opacity by magnitude, capped
        strength = min(abs(v) / cap, 1.0)     # 0..1
        alpha = 0.15 + 0.35 * strength        # 0.15..0.50
        if v > 0:
            bg = f"rgba(16,185,129,{alpha:.2f})"   # green
        else:
            bg = f"rgba(239,68,68,{alpha:.2f})"    # red

    return (
        f'<span style="display:block; background:{bg}; '
        f'padding:0 6px; border-radius:3px; text-align:right;">{v*100:,.1f}%</span>'
    )

# -------------------------
# Load source
# -------------------------
@st.cache_data(show_spinner=False)
def load_csv(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    required = [
        "Date","Ticker","Ticker_name","Category",
        "st_trend","mt_trend","lt_trend",
        "st_trend_change","mt_trend_change","lt_trend_change",
    ]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    # numeric hygiene
    for c in ["st_trend","mt_trend","lt_trend",
              "st_trend_change","mt_trend_change","lt_trend_change"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

df = load_csv(CSV_PATH)

# ---- Page title (under logo) pulled from source Date ----
date_str = ""
if not df.empty and "Date" in df.columns:
    asof = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.notna(asof):
        date_str = f"{asof.month}/{asof.day}/{asof.year}"

st.markdown(
    f"""
    <div style="text-align:center; margin:-6px 0 14px;
                font-size:18px; font-weight:600; color:#1a1a1a;">
        Directional Trends – {date_str}
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Module 2 comment label (ST/MT/LT alignment + changes) ---
def m2_label(st, mt, lt, stc, mtc):
    """Return directional trend category (7-bucket taxonomy) aligned with the final 24-case grid."""
    vals = [st, mt, lt, stc, mtc]
    if any(pd.isna(v) for v in vals):
        return "Insufficient data"
    try:
        st, mt, lt, stc, mtc = map(float, vals)
    except Exception:
        return "Insufficient data"

    # delta helpers
    threshold = 0.0005  # = 0.05%
    both_up   = (stc >= threshold and mtc >= threshold)
    both_down = (stc <= -threshold and mtc <= -threshold)
    st_up_mt_down = (stc >= threshold and mtc <= -threshold)
    st_down_mt_up = (stc <= -threshold and mtc >= threshold)

    if abs(stc) <= threshold or abs(mtc) <= threshold:
        return "Neutral"

    # --------------------------
    # A) Confirmed bullish stack
    #    ST < MT < LT
    # --------------------------
    if st < mt < lt:
        if both_up:               # #1
            return "Buy"
        if st_up_mt_down:         # #2
            return "Bottoming"
        if st_down_mt_up:         # #3
            return "Bottoming"
        if both_down:             # #4
            return "Sell"
        return "Neutral"

    # --------------------------
    # B) LT in the middle (ST < LT < MT)
    # --------------------------
    if st < lt < mt:
        if both_up:               # #5
            return "Leaning Bullish"
        if st_up_mt_down:         # #6
            return "Neutral"
        if st_down_mt_up:         # #7  (MT leadership carries more weight)
            return "Leaning Bullish"
        if both_down:             # #8
            return "Leaning Bearish"
        return "Neutral"

    # --------------------------
    # C) Bullish half, not the stack (MT < ST < LT)
    # --------------------------
    if mt < st < lt:
        if both_up:               # #9
            return "Leaning Bullish"
        if st_up_mt_down:         # #10
            return "Neutral"
        if st_down_mt_up:         # #11
            return "Neutral"
        if both_down:             # #12
            return "Leaning Bearish"
        return "Neutral"

    # --------------------------
    # D) LT in the middle (MT < LT < ST)
    # --------------------------
    if mt < lt < st:
        if both_up:               # #13
            return "Leaning Bullish"
        if st_up_mt_down:         # #14
            return "Neutral"
        if st_down_mt_up:         # #15
            return "Neutral"
        if both_down:             # #16
            return "Leaning Bearish"
        return "Neutral"

    # --------------------------
    # E) Bearish half, not the stack (LT < ST < MT)
    # --------------------------
    if lt < st < mt:
        if both_up:               # #17
            return "Leaning Bullish"
        if st_up_mt_down:         # #18
            return "Leaning Bearish"
        if st_down_mt_up:         # #19
            return "Neutral"
        if both_down:             # #20
            return "Leaning Bearish"
        return "Neutral"

    # --------------------------
    # F) Confirmed bearish stack (LT < MT < ST)
    # --------------------------
    if lt < mt < st:
        if both_up:               # #21
            return "Buy"
        if st_up_mt_down:         # #22
            return "Topping"
        if st_down_mt_up:         # #23
            return "Topping"
        if both_down:             # #24
            return "Sell"
        return "Neutral"

    # Fallback (ties/equalities or anything unexpected)
    return "Neutral"

def trend_tag(label: str) -> str:
    """
    Return a *subtle* tinted pill for the Directional Trend category.
    Tints mirror the cell style (light RGBA), no heavy fills, default dark text.
    """
    if not isinstance(label, str):
        return ""
    l = label.strip()

    # Base style (subtle pill)
    bg = "transparent"
    color = "#1a1a1a"     # default dark text
    pad = "2px 8px"
    radius = "3px"
    weight = 500          # lighter than bold to keep it understated

    # Light tints (align with cell vibe; alpha ~0.12–0.20)
    if l == "Buy":
        bg = "rgba(16,185,129,0.42)"      # deeper green tint
    elif l == "Leaning Bullish":
        bg = "rgba(16,185,129,0.12)"      # lighter green tint
    elif l in ("Topping", "Bottoming"):
        bg = "rgba(107,114,128,0.12)"     # light gray tint
    elif l == "Leaning Bearish":
        bg = "rgba(239,68,68,0.12)"       # lighter red tint
    elif l == "Sell":
        bg = "rgba(239,68,68,0.42)"       # deeper red tint
    elif l == "Neutral":
        bg = "transparent"

    return (
        f'<span style="background:{bg}; color:{color}; '
        f'padding:{pad}; border-radius:{radius}; font-weight:{weight};">{l}</span>'
    )



# ---------- Shared CSS (compass-style card) ----------
st.markdown("""
<style>
.card-wrap { display:flex; justify-content:center; }
.card{
  border:1px solid #cfcfcf; border-radius:8px; background:#fff;
  padding:12px; width:100%; max-width:1200px;
}
.tbl { border-collapse: collapse; width: 100%; table-layout: fixed; }
.tbl th, .tbl td {
  border:1px solid #d9d9d9; padding:6px 8px; font-size:13px;
  overflow:hidden; text-overflow:ellipsis;
}
.tbl th { background:#f2f2f2; font-weight:700; color:#1a1a1a; text-align:left; }
.tbl th:nth-child(n+2) { text-align:center; }
.tbl td:nth-child(n+2) { text-align:right; white-space:nowrap; }

/* Column width helpers */
.tbl col.col-name   { width:28ch; min-width:28ch; max-width:28ch; }
.tbl col.col-ticker { width:8ch; }
.tbl col.col-num    { width:8ch; }
            
/* Center the Ticker column (2nd column) */
.tbl th:nth-child(2),
.tbl td:nth-child(2) { text-align: center; }

/* allow wrapping for Name */
.tbl th:nth-child(1), .tbl td:nth-child(1) { white-space:normal; overflow:visible; text-overflow:clip; }

/* Make the last column (Comment) left-aligned and wider */
.tbl th:last-child, .tbl td:last-child { text-align:left; }
.tbl col.col-comment { width:18ch; min-width:18ch;}            


.subnote { border-top:1px solid #e5e5e5; margin-top:8px; padding-top:10px; font-size:11px; color:#6c757d; }
.vspace-16 { height:16px; }
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


# =========================================================
# Card 1 — Macro Orientation (Trends & Changes)
# =========================================================

macro_list = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

if df.empty:
    st.info("`qry_graph_data_88.csv` missing or columns incomplete.")
else:
    # keep only the latest row per ticker (in case CSV has multiple dates)
    df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
    latest = (
        df.sort_values(["Ticker", "_dt"], ascending=[True, False])
          .drop_duplicates(subset=["Ticker"], keep="first")
    )

    m = latest[latest["Ticker"].isin(macro_list)].copy()
    m["__ord__"] = m["Ticker"].map({t:i for i, t in enumerate(macro_list)})
    m = m.sort_values("__ord__", kind="stable")

    m["Ticker_link"] = m["Ticker"].map(_mk_ticker_link)

    macro_tbl = pd.DataFrame({
        "Name":        m["Ticker_name"],
        "Ticker":      m["Ticker_link"],
        "ST":          [tint_cell(v) for v in m["st_trend"]],
        "MT":          [tint_cell(v) for v in m["mt_trend"]],
        "LT":          [tint_cell(v) for v in m["lt_trend"]],
        "Δ ST":   [tint_cell(v) for v in m["st_trend_change"]],
        "Δ MT":   [tint_cell(v) for v in m["mt_trend_change"]],
        "Δ LT":   [tint_cell(v) for v in m["lt_trend_change"]],
        "Tape Bias":     [trend_tag(m2_label(st, mt, lt, stc, mtc)) for st, mt, lt, stc, mtc in
                    zip(m["st_trend"], m["mt_trend"], m["lt_trend"],
                        m["st_trend_change"], m["mt_trend_change"])],
    })

    html_macro = macro_tbl.to_html(index=False, classes="tbl", escape=False, border=0)
    html_macro = html_macro.replace('class="dataframe tbl"', 'class="tbl"')
    colgroup_macro = """
    <colgroup>
      <col class="col-name">   <!-- Name -->
      <col class="col-ticker"> <!-- Ticker -->
      <col class="col-num">    <!-- ST -->
      <col class="col-num">    <!-- MT -->
      <col class="col-num">    <!-- LT -->
      <col class="col-num">    <!-- ST Chg -->
      <col class="col-num">    <!-- MT Chg -->
      <col class="col-num">    <!-- LT Chg -->
      <col class="col-comment"> <!-- Comment -->
    </colgroup>
    """.strip()
    html_macro = html_macro.replace('<table class="tbl">', f'<table class="tbl">{colgroup_macro}', 1)

    st.markdown(
        f"""
        <div class="card-wrap">
          <div class="card">
            <h3 style="margin:0 0 -6px 0; font-size:16px; font-weight:700; color:#1a1a1a; text-align:center;">
              Macro Orientation — Directional Trends by Timeframe & Changes
            </h3>
            {html_macro}
            <div class="subnote">
               Ticker links open the Deep Dive Dashboard. Green = positive; Red = negative.<br>
                <b>Legend:</b> 
                <b>Buy</b> – Uptrend confirmed · 
                <b>Leaning Bullish</b> – Bullish setup, confirmation pending · 
                <b>Neutral</b> – Crosscurrents / mixed trends · 
                <b>Topping / Bottoming</b> – Transition zones where trends may reverse<br>
                <b>Leaning Bearish</b> – Bearish bias but not fully aligned · 
                <b>Sell</b> – Downtrend confirmed.                
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# little breathing room
st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)

preferred_order = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities",
    "Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]

# =========================================================
# Card 3 — Per-Category Tickers (selector)
# =========================================================
if not df.empty:
    # ordered category dropdown
    cats_present = [c for c in preferred_order if c in df["Category"].dropna().unique().tolist()]
    default_cat = "Sector & Style ETFs" if "Sector & Style ETFs" in cats_present else (cats_present[0] if cats_present else None)
    _, csel, _ = st.columns([1, 1, 1])
    with csel:
        sel = st.selectbox("Category", cats_present, index=(cats_present.index(default_cat) if default_cat else 0))

    d = df.loc[df["Category"] == sel].copy()
    # latest per ticker (if multiple dates)
    d = (
        d.sort_values(["Ticker", "_dt"], ascending=[True, False])
         .drop_duplicates(subset=["Ticker"], keep="first")
         if "_dt" in d.columns else d
    )
    d["Ticker_link"] = d["Ticker"].map(_mk_ticker_link)

    per_tbl = pd.DataFrame({
        "Name":        d["Ticker_name"],
        "Ticker":      d["Ticker_link"],
        "ST":          [tint_cell(v) for v in d["st_trend"]],
        "MT":          [tint_cell(v) for v in d["mt_trend"]],
        "LT":          [tint_cell(v) for v in d["lt_trend"]],
        "Δ ST":   [tint_cell(v) for v in d["st_trend_change"]],
        "Δ MT":   [tint_cell(v) for v in d["mt_trend_change"]],
        "Δ LT":   [tint_cell(v) for v in d["lt_trend_change"]],
        "Tape Bias":     [trend_tag(m2_label(st, mt, lt, stc, mtc)) for st, mt, lt, stc, mtc in
                    zip(d["st_trend"], d["mt_trend"], d["lt_trend"],
                        d["st_trend_change"], d["mt_trend_change"])],
    })

    html_per = per_tbl.to_html(index=False, classes="tbl", escape=False, border=0)
    html_per = html_per.replace('class="dataframe tbl"', 'class="tbl"')
    colgroup_per = """
    <colgroup>
      <col class="col-name">   <!-- Name -->
      <col class="col-ticker"> <!-- Ticker -->
      <col class="col-num">    <!-- ST -->
      <col class="col-num">    <!-- MT -->
      <col class="col-num">    <!-- LT -->
      <col class="col-num">    <!-- ST Chg -->
      <col class="col-num">    <!-- MT Chg -->
      <col class="col-num">    <!-- LT Chg -->
      <col class="col-comment"> <!-- Comment -->
    </colgroup>
    """.strip()
    html_per = html_per.replace('<table class="tbl">', f'<table class="tbl">{colgroup_per}', 1)

    st.markdown(
        f"""
        <div class="card-wrap">
          <div class="card">
            <h3 style="margin:0 0 -6px 0; font-size:16px; font-weight:700; color:#1a1a1a; text-align:center;">
              {sel} — Per Ticker Directional Trends by Timeframe & Changes
            </h3>
            {html_per}
            <div class="subnote">
               Ticker links open the Deep Dive Dashboard. Green = positive; Red = negative.<br>
                <b>Legend:</b> 
                <b>Buy</b> – Uptrend confirmed · 
                <b>Leaning Bullish</b> – Bullish setup, confirmation pending · 
                <b>Neutral</b> – Crosscurrents / mixed trends · 
                <b>Topping / Bottoming</b> – Transition zones where trends may reverse<br> 
                <b>Leaning Bearish</b> – Bearish bias but not fully aligned · 
                <b>Sell</b> – Downtrend confirmed.                
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# All Tickers — Sortable Table (Directional Trends)
# =========================

#flt_col1, flt_col2, flt_col3 = st.columns([3,1,3])
#with flt_col2:
#    q = st.text_input("Filter (name, ticker, category)", "", placeholder="e.g., Energy, XLF, Gold")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# width wrapper so it doesn't span the whole page
pad_l, mid, pad_r = st.columns([1, 2.8, 1])  # tweak 2.2 → wider/narrower
with mid:
    st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align:center; margin:0 0 8px;
                    font-size:16px; font-weight:700; color:#1a1a1a;">
            All Tickers — Sortable Table
        </div>
        <div style="text-align:center; margin:-6px 0 14px;
                    font-size:14px; font-weight:500; color:#6b7280;">
            Current directional trends and timeframe changes across all tickers
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------- dataset (latest row per ticker) --------
    # reuse if already built; else compute
    if "latest" not in locals():
        df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        latest = (
            df.sort_values(["Ticker", "_dt"], ascending=[True, False])
              .drop_duplicates(subset=["Ticker"], keep="first")
        )

    base = latest.copy()

    # optional quick filter
    flt_col1, flt_col2, flt_col3 = st.columns([1,1,1])
    with flt_col2:
        q = st.text_input("Filter (name, ticker, category)", "", placeholder="e.g., Energy, XLF, Gold")
    #q = st.text_input("Filter (name, ticker, category)", "", placeholder="e.g., Energy, XLF, Gold")
    if q:
        ql = q.strip().lower()
        base = base[
            base["Ticker_name"].str.lower().str.contains(ql, na=False)
            | base["Ticker"].str.lower().str.contains(ql, na=False)
            | base["Category"].str.lower().str.contains(ql, na=False)
        ]

    # compute Tape Bias label (text-only for the sortable grid)
    tape = [m2_label(stv, mtv, ltv, stc, mtc)
            for stv, mtv, ltv, stc, mtc in zip(
                base["st_trend"], base["mt_trend"], base["lt_trend"],
                base["st_trend_change"], base["mt_trend_change"]
            )]

    # build display frame (percent values shown as numbers suitable for NumberColumn formatting)
    df_all = pd.DataFrame({
        "Name":     base["Ticker_name"],
        "Ticker":   base["Ticker"],
        "Category": base["Category"],
        "ST":       base["st_trend"] * 100.0,
        "MT":       base["mt_trend"] * 100.0,
        "LT":       base["lt_trend"] * 100.0,
        "ΔST":      base["st_trend_change"] * 100.0,
        "ΔMT":      base["mt_trend_change"] * 100.0,
        "ΔLT":      base["lt_trend_change"] * 100.0,
        "Tape Bias": tape,
    })

    # default sort strongest ST uptrends first (tweak to taste)
    df_all = df_all.sort_values(["Category", "Ticker"], ascending=[True, True]).reset_index(drop=True)

    # render compact, sortable table
    st.dataframe(
        df_all,
        use_container_width=True,   # fits to the middle column width
        height=520,
        hide_index=True,
        column_config={
            "Name":     st.column_config.TextColumn(width="medium"),
            "Ticker":   st.column_config.TextColumn(width="small"),
            "Category": st.column_config.TextColumn(width="medium"),
            "ST":       st.column_config.NumberColumn(format="%.1f%%", width="small", help="Short-term trend"),
            "MT":       st.column_config.NumberColumn(format="%.1f%%", width="small", help="Mid-term trend"),
            "LT":       st.column_config.NumberColumn(format="%.1f%%", width="small", help="Long-term trend"),
            "ΔST":      st.column_config.NumberColumn(format="%.1f%%", width="small", help="Short-term daily change"),
            "ΔMT":      st.column_config.NumberColumn(format="%.1f%%", width="small", help="Mid-term daily change"),
            "ΔLT":      st.column_config.NumberColumn(format="%.1f%%", width="small", help="Long-term daily change"),
            "Tape Bias": st.column_config.TextColumn(width="medium"),
        },
    )

    # Download button centered with the table (same column)
    csv_bytes = df_all.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download current view (CSV)",
        data=csv_bytes,
        file_name=f"Directional_Trends_{date_str.replace('/','-')}.csv",
        mime="text/csv",
        type="secondary",
        key="dl_markmentum_alltickers",
    )

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