# 15_Vantage_Point.py — Vantage Point (Market Orientation only)
from pathlib import Path
import base64
import pandas as pd
import numpy as np
import streamlit as st
from urllib.parse import quote_plus
from html import escape

# ---------- Page ----------
st.set_page_config(page_title="Vantage Point – Market Orientation", layout="wide")
st.cache_data.clear()

# ---------- Paths ----------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent
DATA_DIR   = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"
CSV_PATH   = DATA_DIR / "signal_box.csv"      # <- single source file

# ---------- Header (centered logo) ----------
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

# --- Clickable Deep Dive helper & router (same UX as Heatmap)
# keys used on the Deep Dive page
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

        st.switch_page("pages/08_Deep_Dive_Dashboard.py")

# ---------- Reused formatters & tints ----------
def _fmt_int(x):
    try:
        if pd.isna(x): return ""
        return f"{int(round(float(x))):,}"
    except Exception: return ""

def _fmt_pct(x, nd=2):
    try:
        if pd.isna(x): return ""
        return f"{float(x)*100:,.{nd}f}%"
    except Exception: return ""

def _robust_vmax(series, q=0.98, floor=1.0, step=1.0):
    s = pd.to_numeric(series, errors="coerce").abs().dropna()
    if s.empty: return floor
    vmax = float(np.quantile(s, q))
    return max(floor, float(int(np.ceil(vmax / step) * step)))

# === % Return tint (Performance Heatmap pattern) ===
def _divergent_pct_cell(val: float, vmax: float) -> str:
    if val is None or pd.isna(val) or vmax is None or vmax <= 0: return ""
    s = min(abs(float(val)) / float(vmax), 1.0)
    alpha = 0.12 + 0.28 * s
    bg = "transparent"
    if val > 0:   bg = f"rgba(16,185,129,{alpha:.3f})"  # green
    elif val < 0: bg = f"rgba(239,68,68,{alpha:.3f})"  # red
    label = _fmt_pct(val, 2)
    return f'<span style="display:block; background:{bg}; padding:0 4px; border-radius:1px; text-align:right;">{label}</span>'  # :contentReference[oaicite:4]{index=4}

# === Sharpe Rank cell (Sharpe Heatmap pattern) ===
def _rank_cell(score: float, cap: float = 100.0) -> str:
    if score is None or pd.isna(score): return ""
    s = float(np.clip(score, 0, cap))
    if s >= 70:   # high -> greener with intensity
        rel = (s - 70.0) / 30.0
        alpha = 0.12 + 0.28 * max(0.0, min(rel, 1.0))
        bg, color = f"rgba(16,185,129,{alpha:.3f})", "#0b513a"
    elif s <= 30: # low -> redder with intensity
        rel = (30.0 - s) / 30.0
        alpha = 0.12 + 0.28 * max(0.0, min(rel, 1.0))
        bg, color = f"rgba(239,68,68,{alpha:.3f})", "#641515"
    else:
        bg, color = "rgba(156,163,175,0.18)", "#374151"
    return f'<span style="display:block; background:{bg}; color:{color}; padding:0 6px; border-radius:2px; text-align:right;">{_fmt_int(s)}</span>'  # :contentReference[oaicite:5]{index=5}

# === MM Score cell (Markmentum Heatmap pattern) ===
def _score_cell(score: float, cap: float = 105.0) -> str:
    if score is None or pd.isna(score): return ""
    s = float(score)
    if s >= 25:
        rel = min(abs(s) / cap, 1.0); alpha = 0.12 + 0.28 * rel
        bg, color = f"rgba(16,185,129,{alpha:.3f})", "#0b513a"
    elif s <= -25:
        rel = min(abs(s) / cap, 1.0); alpha = 0.12 + 0.28 * rel
        bg, color = f"rgba(239,68,68,{alpha:.3f})", "#641515"
    else:
        bg, color = "rgba(156,163,175,0.18)", "#374151"
    return f'<span style="display:block; background:{bg}; color:{color}; padding:0 6px; border-radius:2px; text-align:right;">{_fmt_int(s)}</span>'  # :contentReference[oaicite:6]{index=6}

# === Delta tint (Sharpe/MM change columns) ===
def _delta_cell(val: float, vmax: float) -> str:
    if val is None or pd.isna(val) or vmax is None or vmax <= 0: return ""
    s = min(abs(float(val)) / float(vmax), 1.0)
    alpha = 0.12 + 0.28 * s
    bg = "transparent"
    if val > 0:   bg = f"rgba(16,185,129,{alpha:.3f})"
    elif val < 0: bg = f"rgba(239,68,68,{alpha:.3f})"
    return f'<span style="display:block; background:{bg}; padding:0 6px; border-radius:2px; text-align:right;">{_fmt_int(val)}</span>'  # 

# === Tape Bias pill (reuse Directional Trends styling) ===
def _tape_pill(label: str) -> str:
    if not isinstance(label, str):
        return ""
    l = label.strip()

    bg = "transparent"
    color = "#1a1a1a"
    pad = "2px 8px"
    radius = "3px"
    weight = 500

    if l == "Buy":
        bg = "rgba(16,185,129,0.42)"
    elif l == "Leaning Bullish":
        bg = "rgba(16,185,129,0.12)"
    elif l in ("Topping", "Bottoming"):
        bg = "rgba(107,114,128,0.12)"
    elif l == "Leaning Bearish":
        bg = "rgba(239,68,68,0.12)"
    elif l == "Sell":
        bg = "rgba(239,68,68,0.42)"

    return (
        f'<span style="background:{bg}; color:{color}; '
        f'padding:{pad}; border-radius:{radius}; font-weight:{weight};">{l}</span>'
    )

# ---------- Timeframe mapping (exact signal_box fields) ----------
TIMEFRAMES = {
    "Daily": {
        "ret":  "day_pct_change",
        "d_sh": "Sharpe_Rank_daily_change",
        "d_mm": "MM_Score_daily_change",
        "title": "Daily"
    },
    "Weekly":   {
        "ret":  "week_pct_change",
        "d_sh": "Sharpe_Rank_wtd_change",
        "d_mm": "MM_Score_wtd_change",
        "title": "Weekly"
    },
    "Monthly":   {
        "ret":  "month_pct_change",
        "d_sh": "Sharpe_Rank_mtd_change",
        "d_mm": "MM_Score_mtd_change",
        "title": "Monthly"
    },
    "Quarterly":   {
        "ret":  "quarter_pct_change",
        "d_sh": "Sharpe_Rank_qtd_change",
        "d_mm": "MM_Score_qtd_change",
        "title": "Quarterly"
    },
}

CURRENT = {
    "rank": "Sharpe_Rank",
    "mm":   "MM_Score",
    "tape": "Tape_Bias",
}

# ---------- Load source ----------
@st.cache_data(show_spinner=False)
def load_signal_box(p: Path) -> pd.DataFrame:
    if not p.exists(): return pd.DataFrame()
    df = pd.read_csv(p)
    needed = [
        "Date","Ticker","Ticker_name","Category",
        CURRENT["rank"], CURRENT["mm"], CURRENT["tape"],
        "day_pct_change","week_pct_change","month_pct_change","quarter_pct_change",
        "Sharpe_Rank_daily_change","Sharpe_Rank_wtd_change","Sharpe_Rank_mtd_change","Sharpe_Rank_qtd_change",
        "MM_Score_daily_change","MM_Score_wtd_change","MM_Score_mtd_change","MM_Score_qtd_change",
    ]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()  # enforce schema
    for c in needed:
        if c not in ("Date","Ticker","Ticker_name","Category",CURRENT["tape"]):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

sb = load_signal_box(CSV_PATH)

# ---------- Title + timeframe dropdown (centered like Morning Compass) ----------
#st.markdown("<h1 style='margin-bottom:2px;'>Vantage Point</h1><div style='color:#667; font-size:13px;'>All signals. One view.</div>", unsafe_allow_html=True)

# --- Page title with date (centered, like Morning Compass) ---
date_str = ""
if not sb.empty and "Date" in sb.columns:
    asof = pd.to_datetime(sb["Date"], errors="coerce").max()
    if pd.notna(asof):
        date_str = f"{asof.month}/{asof.day}/{asof.year}"


st.markdown(
    f"""
    <div style="text-align:center; margin:-6px 0 8px;
                font-size:18px; font-weight:600; color:#1a1a1a;">
        Vantage Point – {date_str}
    </div>
    """,
    unsafe_allow_html=True,
)

def _centered_select(label: str, options: list[str], default: str):
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        return st.selectbox(label, options, index=options.index(default), label_visibility="collapsed")

timeframe = _centered_select("Timeframe", list(TIMEFRAMES.keys()), "Daily")  # :contentReference[oaicite:8]{index=8}
tf = TIMEFRAMES[timeframe]

# ---------- Styling (card + table; same class names you already use) ----------
st.markdown("""
<style>
.card-wrap { display:flex; justify-content:center; }
.card{
  border:1px solid #cfcfcf; border-radius:8px; background:#fff;
  padding:12px 12px 10px 12px; width:100%;
  max-width:1200px;
}
.tbl { border-collapse: collapse; width: 100%; table-layout: fixed; }
.tbl th, .tbl td {
  border:1px solid #d9d9d9; padding:6px 8px; font-size:13px;
  overflow:hidden; text-overflow:ellipsis;
}
.tbl th { background:#f2f2f2; font-weight:700; color:#1a1a1a; text-align:left; }
.tbl th:nth-child(n+2) { text-align:center; }
.tbl td:nth-child(n+2) { text-align:right; white-space:nowrap; }

/* columns */
.tbl col.col-name { width:35ch; min-width:35ch; max-width:35ch; }
.tbl col.col-ticker { width:7ch; }
.tbl col.col-spacer { width:8px; background:#f8f8f8; }

/* allow name wrap */
.tbl th:nth-child(1), .tbl td:nth-child(1) { white-space:normal; overflow:visible; text-overflow:clip; }

/* center the Ticker col */
.tbl th:nth-child(2), .tbl td:nth-child(2) { text-align:center; }

/* make ticker link fill the cell for perfect centering */
.tbl td:nth-child(2) a { display:inline-block; width:100%; }

/* Left-align Tape Bias column (5th) */
.tbl th:nth-child(5), .tbl td:nth-child(5) { text-align:left; }
            

/* shared typography for all cards */
.card h3{
  margin:0 0 -4px 0; font-size:16px; font-weight:700; text-align:center; color:#1a1a1a;
}
.card .subtitle{
  text-align:center; color:#6b7280; font-size:13.5px; margin-bottom:8px;
}

/* ── Table-specific rules ───────────────────────────────────────── */

/* Macro table (has Tape Bias and spacer at col 6) */
.tbl-macro th:nth-child(5), .tbl-macro td:nth-child(5){ text-align:left; }  /* Tape Bias */
.tbl-macro th:nth-child(6), .tbl-macro td:nth-child(6){
  border:none !important; background:transparent !important; padding:0 !important; /* spacer col */
}

/* Category table (no Tape Bias; spacer is col 4) */
.tbl-cat th:nth-child(4), .tbl-cat td:nth-child(4){
  border:none !important; background:transparent !important; padding:0 !important; /* spacer col */
}
            
</style>
""", unsafe_allow_html=True)

# ---------- Macro list ----------
macro_list = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

# ---------- Build card ----------
def _build_macro_card(df: pd.DataFrame):
    if df.empty:
        st.info("`signal_box.csv` missing or columns incomplete.")
        return

    # latest per ticker
    df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
    latest = (df.sort_values(["Ticker","_dt"], ascending=[True, False])
                .drop_duplicates(subset=["Ticker"], keep="first"))

    m = latest[latest["Ticker"].isin(macro_list)].copy()
    m["__ord__"] = m["Ticker"].map({t:i for i,t in enumerate(macro_list)})
    m = m.sort_values(["__ord__"], kind="stable")

    # vmax per timeframe (for % return and deltas)
    vmax_ret = _robust_vmax(m[tf["ret"]], q=0.98, floor=0.5, step=0.5)
    vmax_dsh = _robust_vmax(m[tf["d_sh"]], q=0.98, floor=1.0, step=1.0)
    vmax_dmm = _robust_vmax(m[tf["d_mm"]], q=0.98, floor=1.0, step=1.0)

    # HTML table (Current | spacer | timeframe changes)
    render = pd.DataFrame({
        "Name":    m["Ticker_name"],
        "Ticker":  m["Ticker"].map(_mk_ticker_link),
        "MM Score":      m[CURRENT["mm"]].map(_score_cell),
        "Sharpe Rank":  m[CURRENT["rank"]].map(_rank_cell),
        "Tape Bias": m[CURRENT["tape"]].fillna("").map(_tape_pill),
        "":        [""] * len(m),  # spacer col
        "Δ %":   [ _divergent_pct_cell(v, vmax_ret) for v in m[tf["ret"]] ],
        "Δ MM Score": [ _delta_cell(v, vmax_dmm)         for v in m[tf["d_mm"]] ],
        "Δ Sharpe Rank":   [ _delta_cell(v, vmax_dsh)         for v in m[tf["d_sh"]] ],
    })

    html = render.to_html(index=False, classes="tbl", escape=False, border=0)
    html = html.replace('class="dataframe tbl"', 'class="tbl"')
    colgroup = """
    <colgroup>
      <col class="col-name">     <!-- Name -->
      <col class="col-ticker">   <!-- Ticker -->
      <col> <col> <col>          <!-- Sharpe | MM | Tape -->
      <col class="col-spacer">   <!-- spacer -->
      <col> <col> <col>          <!-- %Ret | Sharpe▲ | MM▲ -->
    </colgroup>
    """.strip()
    html = html.replace('<table class="tbl">', f'<table class="tbl">{colgroup}', 1)

    # As-of date
    date_str = ""
    if "Date" in m.columns:
        dmax = pd.to_datetime(m["Date"], errors="coerce").max()
        if pd.notna(dmax):
            date_str = f"{dmax.month}/{dmax.day}/{dmax.year}"

    st.markdown(
        f"""
        <div class="card-wrap">
          <div class="card">
            <h3>Macro Orientation — {escape(TIMEFRAMES[timeframe]["title"])} Changes</h3>
            <div class="subtitle">
                Current MM Score / Sharpe Rank and {tf['title']} Changes
            </div>
            {html}
            <div style="border-top:1px solid #e5e5e5; margin-top:8px; padding-top:10px; font-size:11px; color:#6c757d;">
              MM Score/Rank cells use green/gray/red tints; Δ columns use independent per-timeframe scales. Tape Bias from Directional Trends page.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Render ----------
_build_macro_card(sb)

# =========================
# Category Averages (card)
# =========================
st.markdown("<br>", unsafe_allow_html=True)

st.markdown("""
<style>
.card2-wrap { display:flex; justify-content:center; }
.card2{
  border:1px solid #cfcfcf; border-radius:8px; background:#fff;
  padding:12px 12px 10px 12px; width:100%;
  max-width:950px;
}
.tbl2 { border-collapse: collapse; width: 100%; table-layout: fixed; }
.tbl2 th, .tbl2 td {
  border:1px solid #d9d9d9; padding:6px 8px; font-size:13px;
  overflow:hidden; text-overflow:ellipsis;
}
.tbl2 th { background:#f2f2f2; font-weight:700; color:#1a1a1a; text-align:left; }
.tbl2 th:nth-child(n+2) { text-align:center; }
.tbl2 td:nth-child(n+2) { text-align:right; white-space:nowrap; }

/* columns */
.tbl2 col.col-name { width:35ch; min-width:35ch; max-width:35ch; }
.tbl2 col.col-ticker { width:7ch; }
.tbl2 col.col-spacer { width:8px; background:#f8f8f8; }

/* allow name wrap */
.tbl2 th:nth-child(1), .tbl2 td:nth-child(1) { white-space:normal; overflow:visible; text-overflow:clip; }

/* center the Ticker col */
.tbl2 th:nth-child(2), .tbl2 td:nth-child(2) { text-align:center; }

/* make ticker link fill the cell for perfect centering */
.tbl2 td:nth-child(2) a { display:inline-block; width:100%; }

       

/* shared typography for all card2s */
.card2 h3{
  margin:0 0 -4px 0; font-size:16px; font-weight:700; text-align:center; color:#1a1a1a;
}
.card2 .subtitle{
  text-align:center; color:#6b7280; font-size:13.5px; margin-bottom:8px;
}

/* ── Table-specific rules ───────────────────────────────────────── */

/* Macro table (has Tape Bias and spacer at col 6) */
.tbl2-macro th:nth-child(5), .tbl2-macro td:nth-child(5){ text-align:left; }  /* Tape Bias */
.tbl2-macro th:nth-child(6), .tbl2-macro td:nth-child(6){
  border:none !important; background:transparent !important; padding:0 !important; /* spacer col */
}

/* Category table (no Tape Bias; spacer is col 4) */
.tbl2-cat th:nth-child(4), .tbl2-cat td:nth-child(4){
  border:none !important; background:transparent !important; padding:0 !important; /* spacer col */
}
            
</style>
""", unsafe_allow_html=True)



# Use the latest row per ticker (in case the CSV ever has multiple dates)
sb["_dt"] = pd.to_datetime(sb["Date"], errors="coerce")
latest = (
    sb.sort_values(["Ticker", "_dt"], ascending=[True, False])
      .drop_duplicates(subset=["Ticker"], keep="first")
)

# Average by Category: current Sharpe/Score + timeframe changes (% return, ΔSharpe, ΔMM)
grp = (
    latest.groupby("Category", dropna=True, as_index=False)
    .agg(
        Sharpe=(CURRENT["rank"], "mean"),
        MMScore=(CURRENT["mm"], "mean"),
        Ret=(tf["ret"], "mean"),
        dSharpe=(tf["d_sh"], "mean"),
        dMM=(tf["d_mm"], "mean"),
    )
)

# Preferred row order (same taxonomy you use elsewhere)
preferred_order = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities",
    "Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion",
]
order_map = {name: i for i, name in enumerate(preferred_order)}
grp["__ord__"] = grp["Category"].map(order_map)
grp = grp.sort_values(["__ord__", "Category"], kind="stable").drop(columns="__ord__")

# Independent, robust scales for the tinted columns
vmax_ret = _robust_vmax(grp["Ret"],     q=0.98, floor=1.0, step=1.0)
vmax_dsh = _robust_vmax(grp["dSharpe"], q=0.98, floor=1.0, step=1.0)
vmax_dmm = _robust_vmax(grp["dMM"],     q=0.98, floor=1.0, step=1.0)

# Build render frame (keep the blank spacer column)
cat_render = pd.DataFrame({
    "Name":      grp["Category"],
    "Avg MM Score":  [ _score_cell(v)              for v in grp["MMScore"]  ],
    "Avg Sharpe Rank":    [ _rank_cell(v)               for v in grp["Sharpe"]   ],
    "":          [ ""                          for _ in range(len(grp)) ],  # spacer
    "Δ Avg %":       [ _divergent_pct_cell(v, vmax_ret) for v in grp["Ret"]     ],
    "Δ Avg MM Score":[ _delta_cell(v, vmax_dmm)         for v in grp["dMM"]     ],
    "Δ Avg Sharpe Rank":  [ _delta_cell(v, vmax_dsh)         for v in grp["dSharpe"] ],
})

# HTML + colgroup (spacer column uses .col-spacer which you already zero-border in CSS)
html_cat = cat_render.to_html(index=False, classes="tbl2", escape=False, border=0)
html_cat = html_cat.replace('class="dataframe tbl2"', 'class="tbl2"')

colgroup_cat = """
<colgroup>
  <col class="col-name">     <!-- Name -->
  <col class="col-num">      <!-- Avg Sharpe Rank -->
  <col class="col-num">      <!-- Avg MM Score -->
  <col class="col-spacer">   <!-- Spacer (no borders) -->
  <col class="col-num">      <!-- Avg % Δ -->
  <col class="col-num">      <!-- Avg Sharpe Rank Δ -->
  <col class="col-num">      <!-- Avg MM Score Δ -->
</colgroup>
""".strip()

html_cat = html_cat.replace('<table class="tbl2">', f'<table class="tbl2">{colgroup_cat}', 1)

st.markdown(
    f"""
    <div class="card2-wrap">
      <div class="card2">
        <h3>Category Averages — {tf['title']} Changes</h3>
        <div class="subtitle">
          Avg MM Score / Current Sharpe Rank and {tf['title']} Avg Changes
        </div>
        {html_cat}
            <div style="border-top:1px solid #e5e5e5; margin-top:8px; padding-top:10px; font-size:11px; color:#6c757d;">
              MM Score/Rank cells use green/gray/red tints; Δ columns use independent per-timeframe scales.
            </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================
# Per-Ticker Card (within Category)
# ============================

st.markdown("<br>", unsafe_allow_html=True)

# ========= Category selector =========
preferred_order = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities",
    "Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]
cat_list = [c for c in preferred_order if c in latest["Category"].unique()]

_, csel, _ = st.columns([1, 1, 1])
with csel:
    selected_cat = st.selectbox("Select Category", cat_list, index=0)


tcat = latest[latest["Category"] == selected_cat].copy()

# --- Add local timeframe selector for per-ticker section ---
st.markdown("<br>", unsafe_allow_html=True)
_, ctf, _ = st.columns([2, 1, 2])
with ctf:
    local_tf = st.selectbox(
        "Select Timeframe (Per-Ticker)",
        list(TIMEFRAMES.keys()),
        index=list(TIMEFRAMES.keys()).index(timeframe),
        label_visibility="collapsed"
    )

# Re-map tf to the locally selected timeframe
tf = TIMEFRAMES[local_tf]



if not tcat.empty:
    # Alphabetical by ticker
    tcat = tcat.sort_values("Ticker", kind="stable")
    tcat["Ticker_link"] = tcat["Ticker"].map(_mk_ticker_link)

    # Robust per-card scales (use exact schema fields for the selected timeframe)
    vmaxC_ret = _robust_vmax(tcat[tf["ret"]],  q=0.98, floor=1.0, step=1.0)
    vmaxC_dsh = _robust_vmax(tcat[tf["d_sh"]], q=0.98, floor=1.0, step=1.0)
    vmaxC_dmm = _robust_vmax(tcat[tf["d_mm"]], q=0.98, floor=1.0, step=1.0)

    # Build render frame (current | spacer | timeframe changes)
    t_render = pd.DataFrame({
        "Name":        tcat["Ticker_name"],                             # <- was "Name"
        "Ticker":      tcat["Ticker_link"],
        "MM Score":    [ _score_cell(v) for v in tcat[CURRENT["mm"]]   ],
        "Sharpe Rank": [ _rank_cell(v)  for v in tcat[CURRENT["rank"]] ],
        "Tape Bias": tcat[CURRENT["tape"]].fillna("").map(_tape_pill),
        "":            [ "" for _ in range(len(tcat)) ],               # spacer
        "Δ %":         [ _divergent_pct_cell(v, vmaxC_ret) for v in tcat[tf["ret"]]  ],
        "Δ MM Score":  [ _delta_cell(v, vmaxC_dmm)      for v in tcat[tf["d_mm"]]  ],
        "Δ Sharpe Rank":[ _delta_cell(v, vmaxC_dsh)     for v in tcat[tf["d_sh"]] ],
    })

    html_t = t_render.to_html(index=False, classes="tbl", escape=False, border=0)
    html_t = html_t.replace('class="dataframe tbl"', 'class="tbl"')

    colgroup_t = """
    <colgroup>
      <col class="col-name">      <!-- Name -->
      <col class="col-ticker">    <!-- Ticker -->
      <col class="col-num">       <!-- Sharpe Rank -->
      <col class="col-num">       <!-- MM Score -->
      <col class="col"> 
      <col class="col-spacer">    <!-- Spacer -->
      <col class="col-num">       <!-- % Δ -->
      <col class="col-num">       <!-- Sharpe Rank Δ -->
      <col class="col-num">       <!-- MM Score Δ -->
    </colgroup>
    """.strip()
    html_t = html_t.replace('<table class="tbl">', f'<table class="tbl">{colgroup_t}', 1)

    st.markdown(
        f"""
        <div class="card-wrap">
          <div class="card">
            <h3>{selected_cat} — Per Ticker {escape(TIMEFRAMES[timeframe]["title"])} Changes</h3>
            <div class="subtitle">Current MM Score / Sharpe Rank and {tf['title']} Changes</div>
            {html_t}
            <div style="border-top:1px solid #e5e5e5; margin-top:8px; padding-top:10px; font-size:11px; color:#6c757d;">
              MM Score/Rank cells use green/gray/red tints; Δ columns use independent per-timeframe scales. 
              Tape Bias from Directional Trends page
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info(f"No tickers found for {selected_cat}.")




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