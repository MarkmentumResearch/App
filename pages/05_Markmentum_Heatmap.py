import streamlit as st
st.set_page_config(page_title="Markmentum Heatmap", layout="wide")

from utils.auth import verify_proof, make_proof, restore_session_from_cookie2

ADV_VALUE_KEY  = "dd_show_advanced_charts_value"
INFO_VALUE_KEY = "dd_show_information_charts_value"
tickerp = st.query_params.get("ticker")
adv = st.query_params.get("adv")
info = st.query_params.get("info")
proof = st.query_params.get("proof")

if tickerp and adv and info:
    if st.session_state.get("authenticated") is not True:
        if not verify_proof(proof):
            st.query_params.clear()
            home_url = "https://www.markmentumresearch.com/login"
            st.markdown(
            f'<meta http-equiv="refresh" content="0; url={home_url}" />',
            unsafe_allow_html=True
            )
            st.stop()

        st.session_state["authenticated"] = True
                
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

                st.switch_page("pages/08_Deep_Dive_Dashboard.py")
                st.stop()

if not st.session_state.get("authenticated"):
    home_url = "https://www.markmentumresearch.com/reauth"
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={home_url}" />',
        unsafe_allow_html=True
    )
    st.stop()


# 12_Markmentum_Heatmap.py
# Markmentum — Model Score + Δ (Daily/WTD/MTD/QTD)

from pathlib import Path
import base64
import pandas as pd
import numpy as np
import altair as alt

from urllib.parse import quote_plus
#import os

# -------------------------
# Paths
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR   = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"

# Score sources (as specified)
CSV_BASE   = DATA_DIR / "model_score_day_change.csv"            # Ticker, Ticker_name, Category, Date, model_score, previous_model_score, model_score_daily_change (optional)
CSV_WTD    = DATA_DIR / "model_score_wtd_change.csv"       # model_score_wtd_change, current_model_score, previous_model_score
CSV_MTD    = DATA_DIR / "model_score_mtd_change.csv"       # model_score_mtd_change, current_model_score, previous_model_score
CSV_QTD    = DATA_DIR / "model_score_qtd_change.csv"       # model_score_qtd_change, current_model_score, previous_model_score

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

# --- Clickable Deep Dive helper & router (same UX as Performance Heatmap)
#ADV_VALUE_KEY  = "dd_show_advanced_charts_value"
#INFO_VALUE_KEY = "dd_show_information_charts_value"

def _mk_ticker_link(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    if not t:
        return ""

    # current toggle states (default False if not set yet)
    adv_on  = st.session_state.get(ADV_VALUE_KEY, False)
    info_on = st.session_state.get(INFO_VALUE_KEY, False)

    adv_flag  = "1" if adv_on  else "0"
    info_flag = "1" if info_on else "0"

    proof = make_proof()

    return (
        f'<a href="?page=Deep%20Dive'
        f'&ticker={quote_plus(t)}'
        f'&adv={adv_flag}'
        f'&info={info_flag}'
        f'&proof={proof}" '
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

        st.switch_page("pages/08_Deep_Dive_Dashboard.py")

# -------------------------
# Helpers
# -------------------------
def _robust_vmax(series, q=0.98, floor=1.0, step=1.0):
    s = pd.to_numeric(series, errors="coerce").abs().dropna()
    if s.empty:
        return floor
    vmax = float(np.quantile(s, q))
    return max(floor, np.ceil(vmax / step) * step)

def _fmt_num(x, nd=0):
    try:
        if pd.isna(x): return ""
        return f"{float(x):,.{nd}f}"
    except Exception:
        return ""

# Score cell tint: Buy green, Neutral gray, Sell red; stronger beyond ±100
def _score_cell_html(score: float, cap: float = 105.0) -> str:
    if score is None or pd.isna(score):
        return ""
    s = float(score)

    # Classification
    if s >= 25:
        # Buy — green intensity grows with |s|; beyond 100 gets darker
        rel = min(abs(s) / cap, 1.0)
        alpha = 0.12 + 0.28 * rel       # 0.12 → 0.40
        bg = f"rgba(16,185,129,{alpha:.3f})"
        color = "#0b513a"
    elif s <= -25:
        # Sell — red intensity grows with |s|; beyond -100 gets darker
        rel = min(abs(s) / cap, 1.0)
        alpha = 0.12 + 0.28 * rel
        bg = f"rgba(239,68,68,{alpha:.3f})"
        color = "#641515"
    else:
        # Neutral — light gray (fixed)
        bg = "rgba(156,163,175,0.18)"   # gray-400 @ ~18%
        color = "#374151"

    label = _fmt_num(s, 0)
    return f'<span style="display:block; background:{bg}; color:{color}; padding:0 6px; border-radius:2px; text-align:right;">{label}</span>'

# Change column tint (independent scale per timeframe)
def _delta_cell_html(val: float, vmax: float) -> str:
    if val is None or pd.isna(val) or vmax is None or vmax <= 0:
        return ""
    s = min(abs(float(val)) / float(vmax), 1.0)
    alpha = 0.12 + 0.28 * s
    if val > 0:
        bg = f"rgba(16,185,129,{alpha:.3f})"   # green
    elif val < 0:
        bg = f"rgba(239,68,68,{alpha:.3f})"   # red
    else:
        bg = "transparent"
    label = _fmt_num(val, 0)
    return f'<span style="display:block; background:{bg}; padding:0 6px; border-radius:2px; text-align:right;">{label}</span>'

# -------------------------
# Load sources + assemble model-score frame
# -------------------------
@st.cache_data(show_spinner=False)
def load_markmentum_frames():
    # Base / daily
    cols_keep = [
        "Ticker","Ticker_name","Category","Date",
        "model_score","previous_model_score","model_score_daily_change"
    ]
    base = pd.read_csv(CSV_BASE) if CSV_BASE.exists() else pd.DataFrame(columns=cols_keep)
    # hygiene + latest row per ticker
    if not base.empty and "Date" in base.columns:
        base["_dt"] = pd.to_datetime(base["Date"], errors="coerce")
        base = (base.sort_values(["Ticker","_dt"], ascending=[True, False])
                    .drop_duplicates(subset=["Ticker"], keep="first"))
    for c in ["model_score","previous_model_score","model_score_daily_change"]:
        if c in base.columns:
            base[c] = pd.to_numeric(base[c], errors="coerce")
    if "model_score_daily_change" not in base.columns or base["model_score_daily_change"].isna().all():
        if "model_score" in base.columns and "previous_model_score" in base.columns:
            base["model_score_daily_change"] = base["model_score"] - base["previous_model_score"]

    # WTD / MTD / QTD
    def _load_delta(p, delta_col):
        if not p.exists():
            return pd.DataFrame(columns=["Ticker", delta_col])
        df = pd.read_csv(p)
        if "Ticker" not in df.columns:
            return pd.DataFrame(columns=["Ticker", delta_col])
        df[delta_col] = pd.to_numeric(df.get(delta_col), errors="coerce")
        df = df[["Ticker", delta_col]].drop_duplicates("Ticker", keep="first")
        return df

    wtd = _load_delta(CSV_WTD, "model_score_wtd_change")
    mtd = _load_delta(CSV_MTD, "model_score_mtd_change")
    qtd = _load_delta(CSV_QTD, "model_score_qtd_change")

    # Merge
    df = base.copy()
    for add in (wtd, mtd, qtd):
        df = df.merge(add, on="Ticker", how="left")

    # Final schema
    df = df.rename(columns={
        "Ticker_name": "Name",
        "model_score": "Score",
        "model_score_daily_change": "ΔDaily",
        "model_score_wtd_change":   "ΔWTD",
        "model_score_mtd_change":   "ΔMTD",
        "model_score_qtd_change":   "ΔQTD",
    })
    # Type hygiene
    for c in ["Score","ΔDaily","ΔWTD","ΔMTD","ΔQTD"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

scores = load_markmentum_frames()
if scores.empty:
    st.warning("Model-score files not found or missing required columns.")
    st.stop()

# As-of
date_str = ""
if "Date" in scores.columns:
    dmax = pd.to_datetime(scores["Date"], errors="coerce").max()
    if pd.notna(dmax):
        date_str = f"{dmax.month}/{dmax.day}/{dmax.year}"

# -------------------------
# Shared CSS
# -------------------------
st.markdown("""
<style>
.card-wrap { display:flex; justify-content:center; }
.card{
  border:1px solid #cfcfcf; border-radius:8px; background:#fff;
  padding:12px 12px 10px 12px; width:100%;
  max-width:900px;
}
@media (max-width:1100px){
  .card { max-width:100%; }
}
.tbl { border-collapse: collapse; width: 100%; table-layout: fixed; }
.tbl th, .tbl td {
  border:1px solid #d9d9d9; padding:6px 8px; font-size:13px;
  overflow:hidden; text-overflow:ellipsis;
}
.tbl th { background:#f2f2f2; font-weight:700; color:#1a1a1a; text-align:left; }
.tbl th:nth-child(n+3) { text-align:center; } /* numeric headings centered */
.tbl td:nth-child(n+3) { text-align:right; white-space:nowrap; }

/* Center the Ticker column (2nd column) */
.tbl th:nth-child(2),
.tbl td:nth-child(2) { text-align: center; }

/* Make the ticker link fill the cell so the centering is perfect */
.tbl td:nth-child(2) a {
  display: inline-block;
  width: 100%;
}

.tbl col.col-name-wide   { width:22ch; min-width:22ch; max-width:22ch; }
.tbl col.col-ticker-nar  { width:7ch; }
.tbl col.col-num         { width:8ch; }

.tbl th:nth-child(1), .tbl td:nth-child(1) { white-space:normal; overflow:visible; text-overflow:clip; }
.subnote { border-top:1px solid #e5e5e5; margin-top:8px; padding-top:10px; font-size:11px; color:#6c757d; }
.card h3 { margin:0 0 -6px 0; font-size:16px; font-weight:700; color:#1a1a1a; text-align:center; }
.card .subtitle { margin:0 0 8px 0; font-size:14px; font-weight:500; color:#6b7280; text-align:center; }
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

# -------------------------
# Title
# -------------------------
st.markdown(
    f"""
    <div style="text-align:center; margin:-6px 0 14px;
                font-size:18px; font-weight:600; color:#1a1a1a;">
        Markmentum Heatmap – {date_str}
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Macro Orientation (same flow as Performance page)
# -------------------------
macro_list = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]
scores["_dt"] = pd.to_datetime(scores["Date"], errors="coerce")
latest = (
    scores.sort_values(["Ticker","_dt"], ascending=[True, False])
          .drop_duplicates(subset=["Ticker"], keep="first")
)

m = latest[latest["Ticker"].isin(macro_list)].copy()
m["__ord__"] = m["Ticker"].map({t:i for i,t in enumerate(macro_list)})
m = m.sort_values(["__ord__"], kind="stable")
m["Ticker_link"] = m["Ticker"].map(_mk_ticker_link)

# independent scaling for deltas by timeframe (within macro card)
vmaxM = {
    "ΔDaily": _robust_vmax(m["ΔDaily"], q=0.98, floor=1.0, step=1.0),
    "ΔWTD":   _robust_vmax(m["ΔWTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔMTD":   _robust_vmax(m["ΔMTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔQTD":   _robust_vmax(m["ΔQTD"],   q=0.98, floor=1.0, step=1.0),
}

m_render = pd.DataFrame({
    "Name":   m["Name"],
    "Ticker": m["Ticker_link"],
    "Score":  [ _score_cell_html(v) for v in m["Score"] ],
    "Δ Daily":  [ _delta_cell_html(v, vmaxM["ΔDaily"]) for v in m["ΔDaily"] ],
    "Δ WTD":    [ _delta_cell_html(v, vmaxM["ΔWTD"])   for v in m["ΔWTD"]   ],
    "Δ MTD":    [ _delta_cell_html(v, vmaxM["ΔMTD"])   for v in m["ΔMTD"]   ],
    "Δ QTD":    [ _delta_cell_html(v, vmaxM["ΔQTD"])   for v in m["ΔQTD"]   ],
})

html_macro = m_render.to_html(index=False, classes="tbl", escape=False, border=0)
html_macro = html_macro.replace('class="dataframe tbl"', 'class="tbl"')
colgroup_macro = """
<colgroup>
  <col class="col-name-wide">  <!-- Name -->
  <col class="col-ticker-nar"> <!-- Ticker -->
  <col class="col-num">        <!-- Score -->
  <col class="col-num">        <!-- Daily -->
  <col class="col-num">        <!-- WTD -->
  <col class="col-num">        <!-- MTD -->
  <col class="col-num">        <!-- QTD -->
</colgroup>
""".strip()
html_macro = html_macro.replace('<table class="tbl">', f'<table class="tbl">{colgroup_macro}', 1)

st.markdown(
    f"""
    <div class="card-wrap">
      <div class="card">
        <h3>Macro Orientation</h3>
        <div class="subtitle">Current MM Score and Change by timeframe</div>
        {html_macro}
        <div class="subnote">Score cells are Buy/Neutral/Sell (green/gray/red); change columns use independent per-timeframe scales.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)

# -------------------------
# Category Averages card
# -------------------------
grouped = latest.groupby("Category", dropna=True, as_index=False).agg(
    Score=("Score","mean"),
    ΔDaily=("ΔDaily","mean"),
    ΔWTD=("ΔWTD","mean"),
    ΔMTD=("ΔMTD","mean"),
    ΔQTD=("ΔQTD","mean"),
)

preferred_order = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities",
    "Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]
order_map = {name: i for i, name in enumerate(preferred_order)}
grouped["__ord__"] = grouped["Category"].map(order_map)
grouped = grouped.sort_values(["__ord__", "Category"], kind="stable").drop(columns="__ord__")

vmax_cat = {
    "ΔDaily": _robust_vmax(grouped["ΔDaily"], q=0.98, floor=1.0, step=1.0),
    "ΔWTD":   _robust_vmax(grouped["ΔWTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔMTD":   _robust_vmax(grouped["ΔMTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔQTD":   _robust_vmax(grouped["ΔQTD"],   q=0.98, floor=1.0, step=1.0),
}

g_render = pd.DataFrame({
    "Name":  grouped["Category"],
    "Score": [ _score_cell_html(v) for v in grouped["Score"] ],
    "Δ Daily": [ _delta_cell_html(v, vmax_cat["ΔDaily"]) for v in grouped["ΔDaily"] ],
    "Δ WTD":   [ _delta_cell_html(v, vmax_cat["ΔWTD"])   for v in grouped["ΔWTD"]   ],
    "Δ MTD":   [ _delta_cell_html(v, vmax_cat["ΔMTD"])   for v in grouped["ΔMTD"]   ],
    "Δ QTD":   [ _delta_cell_html(v, vmax_cat["ΔQTD"])   for v in grouped["ΔQTD"]   ],
})

html_cat = g_render.to_html(index=False, classes="tbl", escape=False, border=0)
html_cat = html_cat.replace('class="dataframe tbl"', 'class="tbl"')
colgroup = """
<colgroup>
  <col class="col-name-wide">  <!-- Name -->
  <col class="col-num">        <!-- Score -->
  <col class="col-num">        <!-- Daily -->
  <col class="col-num">        <!-- WTD -->
  <col class="col-num">        <!-- MTD -->
  <col class="col-num">        <!-- QTD -->
</colgroup>
""".strip()
html_cat = html_cat.replace('<table class="tbl">', f'<table class="tbl">{colgroup}', 1)

st.markdown(
    f"""
    <div class="card-wrap">
      <div class="card">
        <h3>Category Averages</h3>
        <div class="subtitle">Avg MM score and Change by category and timeframe</div>
        {html_cat}
        <div class="subnote">Each change column uses an independent red/green scale; score cells use Buy/Neutral/Sell shading.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)


# ===== Category Heatmap — ONE matrix (Score + ΔDaily/ΔWTD/ΔMTD/ΔQTD), all blue↔orange =====
glong = grouped.melt(
    id_vars=["Category"],
    value_vars=["Score", "ΔDaily", "ΔWTD", "ΔMTD", "ΔQTD"],
    var_name="Timeframe",
    value_name="Value",
)
glong["Category"] = pd.Categorical(glong["Category"], categories=preferred_order, ordered=True)

# Robust |max| per timeframe INCLUDING Score; cap Score's vmax at 105 so extremes don't dominate
vmax_tf = {}
for tf, sub in glong.groupby("Timeframe"):
    vmax = _robust_vmax(sub["Value"], q=0.98, floor=1.0, step=1.0)
    if tf == "Score":
        vmax = min(105.0, max(vmax, 1.0))
    vmax_tf[tf] = vmax

# Normalize each cell by its timeframe-specific vmax → [-1, 1]
glong["norm"] = glong.apply(
    lambda r: float(np.clip((r["Value"] or 0.0) / (vmax_tf.get(r["Timeframe"], 1.0) or 1.0), -1, 1)),
    axis=1
)

timeframe_order = ["Score", "ΔDaily", "ΔWTD", "ΔMTD", "ΔQTD"]

cat_hm = (
    alt.Chart(glong)
      .mark_rect(stroke="#2b2f36", strokeWidth=0.6, strokeOpacity=0.95)
      .encode(
          x=alt.X("Timeframe:N",
                  sort=timeframe_order,
                  axis=alt.Axis(orient="top", title=None, labelAngle=0,
                                labelColor="#1a1a1a", labelFontSize=12, labelFlush=False)),
          y=alt.Y("Category:N",
                  sort=list(glong["Category"].cat.categories),
                  axis=alt.Axis(title=None, labelColor="#1a1a1a",
                                labelFlush=False, labelFontSize=12, labelLimit=240)),
          color=alt.Color("norm:Q",
                          scale=alt.Scale(scheme="blueorange", domain=[-1, 0, 1]),
                          legend=alt.Legend(orient="bottom",
                                            title="Avg Score and Change",
                                            labelExpr="''")),
          tooltip=[
              alt.Tooltip("Category:N"),
              alt.Tooltip("Timeframe:N"),
              alt.Tooltip("Value:Q", title="Score / Δ", format=",.0f"),
          ],
      )
      .properties(width=510, height=24 * len(preferred_order))
      .configure_view(strokeWidth=0)
)

st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div style="text-align:center; margin:0 0 8px;
                font-size:16px; font-weight:700; color:#1a1a1a;">
        Category Heatmap — MM Score and Changes
    </div>
    <div style="text-align:center; margin:-6px 0 14px;
                font-size:14px; font-weight:500; color:#6b7280;">
        Average MM Score and Change by category and timeframe
    </div>
    """,
    unsafe_allow_html=True,
)
left, center, right = st.columns([1, .8, 1])
with center:
    st.altair_chart(cat_hm, use_container_width=False)


# -------------------------
# Category selector — Table / Heatmap / Both
# -------------------------
cats_available = [c for c in preferred_order if c in latest["Category"].dropna().unique().tolist()]
default_cat = "Sector & Style ETFs" if "Sector & Style ETFs" in cats_available else (cats_available[0] if cats_available else None)

_, csel, _ = st.columns([1, 1, 1])
with csel:
    sel = st.selectbox("Category", cats_available, index=(cats_available.index(default_cat) if default_cat else 0))

col_left, col_center, col_right = st.columns([1, 1, 1])
with col_center:
    view_choice = st.radio(
        "View",
        ["Table", "Heatmap", "Both"],
        index=2,
        horizontal=True,
        label_visibility="visible",
    )

d = latest.loc[latest["Category"] == sel].copy()
d["Ticker_link"] = d["Ticker"].map(_mk_ticker_link)

vmax_sel = {
    "ΔDaily": _robust_vmax(d["ΔDaily"], q=0.98, floor=1.0, step=1.0),
    "ΔWTD":   _robust_vmax(d["ΔWTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔMTD":   _robust_vmax(d["ΔMTD"],   q=0.98, floor=1.0, step=1.0),
    "ΔQTD":   _robust_vmax(d["ΔQTD"],   q=0.98, floor=1.0, step=1.0),
}

d_render = pd.DataFrame({
    "Name":   d["Name"],
    "Ticker": d["Ticker_link"],
    "Score":  [ _score_cell_html(v) for v in d["Score"] ],
    "Δ Daily":  [ _delta_cell_html(v, vmax_sel["ΔDaily"]) for v in d["ΔDaily"] ],
    "Δ WTD":    [ _delta_cell_html(v, vmax_sel["ΔWTD"])   for v in d["ΔWTD"]   ],
    "Δ MTD":    [ _delta_cell_html(v, vmax_sel["ΔMTD"])   for v in d["ΔMTD"]   ],
    "Δ QTD":    [ _delta_cell_html(v, vmax_sel["ΔQTD"])   for v in d["ΔQTD"]   ],
})

html_detail = d_render.to_html(index=False, classes="tbl", escape=False, border=0)
html_detail = html_detail.replace('class="dataframe tbl"', 'class="tbl"')
colgroup2 = """
<colgroup>
  <col class="col-name-wide">  <!-- Name -->
  <col class="col-ticker-nar"> <!-- Ticker -->
  <col class="col-num">        <!-- Score -->
  <col class="col-num">        <!-- Daily -->
  <col class="col-num">        <!-- WTD -->
  <col class="col-num">        <!-- MTD -->
  <col class="col-num">        <!-- QTD -->
</colgroup>
""".strip()
html_detail = html_detail.replace('<table class="tbl">', f'<table class="tbl">{colgroup2}', 1)

if view_choice in ("Table","Both"):
    st.markdown(
        f"""
        <div class="card-wrap">
          <div class="card">
            <h3>{sel} — Per Ticker</h3>
            <div class="subtitle">Current MM Score and Change by ticker and timeframe</div>
            {html_detail}
            <div class="subnote">Ticker links open the Deep Dive Dashboard. Change columns are independently scaled.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
# Per-ticker heatmap (Score + Δ columns, independent scale per timeframe, universe-wide)
# -------------------------
# Long frame across entire universe, now INCLUDING Score
tlong_all = latest.melt(
    id_vars=["Ticker","Name","Category"],          # <- remove Score from id_vars
    value_vars=["Score","ΔDaily","ΔWTD","ΔMTD","ΔQTD"],
    var_name="Timeframe",
    value_name="Value"
)

# Universe-wide robust vmax per timeframe; cap Score at 105 so extremes don’t dominate
vmax_univ_tf = {}
for tf, sub in tlong_all.groupby("Timeframe"):
    vmax = _robust_vmax(sub["Value"], q=0.98, floor=1.0, step=1.0)
    if tf == "Score":
        vmax = min(105.0, max(vmax, 1.0))
    vmax_univ_tf[tf] = vmax

# Selected category long
tlong_sel = tlong_all.loc[tlong_all["Category"] == sel].copy()
tickers_order = sorted(tlong_sel["Ticker"].dropna().unique().tolist())

# Normalize each cell by the universe max for its timeframe → [-1, 1]
tlong_sel["norm"] = tlong_sel.apply(
    lambda r: np.clip(
        (r["Value"] or 0.0) / (vmax_univ_tf.get(r["Timeframe"], 1.0) or 1.0),
        -1, 1
    ),
    axis=1
)

hm_sel = (
    alt.Chart(tlong_sel)
      .mark_rect(stroke="#2b2f36", strokeWidth=0.6, strokeOpacity=0.95)
      .encode(
          x=alt.X("Timeframe:N",
                  sort=["Score","ΔDaily","ΔWTD","ΔMTD","ΔQTD"],
                  axis=alt.Axis(orient="top", title=None, labelAngle=0,
                                labelColor="#1a1a1a", labelFlush=False, labelFontSize=12)),
          y=alt.Y("Ticker:N",
                  sort=tickers_order,
                  axis=alt.Axis(title=None, labelFontSize=12, labelColor="#1a1a1a",
                                labelFlush=False, labelLimit=260)),
          color=alt.Color("norm:Q",
                          scale=alt.Scale(scheme="blueorange", domain=[-1, 0, 1]),
                          legend=alt.Legend(orient="bottom",
                                            title="Score and Change",
                                            labelExpr="''")),
          tooltip=[
              alt.Tooltip("Ticker:N"),
              alt.Tooltip("Timeframe:N", title="Timeframe"),
              alt.Tooltip("Value:Q", title="Score / Δ", format=",.0f"),
          ],
      )
      .properties(width=400, height=max(360, 22*len(tickers_order)+24))
      .configure_view(strokeWidth=0)
)

if view_choice in ("Heatmap","Both"):
    st.markdown('<div class="vspace-16"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="text-align:center; margin:0 0 8px;
                    font-size:16px; font-weight:700; color:#1a1a1a;">
            {sel} — Per Ticker Heatmap MM Score and Changes
        </div>
        <div style="text-align:center; margin:-6px 0 14px;
                    font-size:14px; font-weight:500; color:#6b7280;">
            Current MM Score and Change by ticker and timeframe
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1.4, .8, 1.4])
    with center:
        st.altair_chart(hm_sel, use_container_width=False)


# =========================
# All Tickers — Sortable Table
# =========================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


pad_l, mid, pad_r = st.columns([1, 2.2, 1])  # tweak 2.2 -> wider/narrower as needed
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
            Current MM Score and timeframe changes across all tickers
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filter input
    #q = st.text_input("Filter (name, ticker, category)", "", placeholder="e.g., Energy, XLF, Gold")
    flt_col1, flt_col2, flt_col3 = st.columns([1.5,1,1.5])
    with flt_col2:
        q = st.text_input("Filter (name, ticker, category)", "", placeholder="e.g., Energy, XLF, Gold")


    df_all = latest.copy()
    if q:
        ql = q.strip().lower()
        df_all = df_all[
            df_all["Name"].str.lower().str.contains(ql, na=False)
            | df_all["Ticker"].str.lower().str.contains(ql, na=False)
            | df_all["Category"].str.lower().str.contains(ql, na=False)
        ]

    cols_show = ["Name", "Ticker", "Category", "Score", "ΔDaily", "ΔWTD", "ΔMTD", "ΔQTD"]
    
    df_all = df_all[cols_show].sort_values(["Category", "Ticker"], ascending=True).reset_index(drop=True)
    #df_all = df_all[cols_show].sort_values("Score", ascending=False).reset_index(drop=True)

    st.dataframe(
        df_all,
        use_container_width=True,   # fits to the width of the middle column
        height=520,
        hide_index=True,
        column_config={
            "Name":     st.column_config.TextColumn(width="medium"),
            "Ticker":   st.column_config.TextColumn(width="small"),
            "Category": st.column_config.TextColumn(width="medium"),
            "Score":    st.column_config.NumberColumn(format="%.0f",  width="small", help="Current MM Score"),
            "ΔDaily":   st.column_config.NumberColumn(format="%.0f", width="small", help="Change vs prior close"),
            "ΔWTD":     st.column_config.NumberColumn(format="%.0f", width="small", help="Change week-to-date"),
            "ΔMTD":     st.column_config.NumberColumn(format="%.0f", width="small", help="Change month-to-date"),
            "ΔQTD":     st.column_config.NumberColumn(format="%.0f", width="small", help="Change quarter-to-date"),
        },
    )

 
    # Download button centered with the table (same column)
    csv_bytes = df_all.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download current view (CSV)",
        data=csv_bytes,
        file_name=f"Markmentum_Scores_{date_str.replace('/','-')}.csv",
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