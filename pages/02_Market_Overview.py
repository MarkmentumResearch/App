from pathlib import Path
import base64
import textwrap
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from urllib.parse import quote_plus
import os




st.set_page_config(page_title="Markmentum – Market Overview", layout="wide")

from utils.auth import restore_session_from_cookie2

if not st.session_state.get("authenticated"):
    if not restore_session_from_cookie2():
        home_url = "https://www.markmentumresearch.com"
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={home_url}" />',
            unsafe_allow_html=True
        )
        st.stop()


st.cache_data.clear()

# -------------------------
# Page & shared style
# -------------------------


st.markdown("""
<style>
/* ---------------- Base layout ---------------- */
div[data-testid="stHorizontalBlock"]{
  display:flex;
  flex-wrap: wrap;
  gap: 28px;
}

/* Each Streamlit column acts like a grid item */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
  flex: 1 1 32%;
  min-width: 300px;
}

/* App container width */
[data-testid="stAppViewContainer"] .main .block-container,
section.main > div {
  width: 95vw;
  max-width: 2100px;
  margin-left: auto;
  margin-right: auto;
}

/* Typography + card shell */
html, body, [class^="css"], .stMarkdown, .stDataFrame, .stTable, .stText, .stButton {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}
.card {
  border:1px solid #cfcfcf;
  border-radius:8px;
  background:#fff;
  padding:12px 12px 8px 12px;
}

/* Choose a STANDARD width for all non-desktop cards */
.card {
  max-width: 720px;
  width: 100%;
}
.card h3 { margin:0 0 8px 0; font-size:16px; font-weight:700; color:#1a1a1a; }

/* Tables */
.tbl { border-collapse: collapse; width: 100%; table-layout: fixed; }
.tbl th, .tbl td { border:1px solid #d9d9d9; padding:6px 8px; font-size:13px; overflow:hidden; text-overflow:ellipsis; }
.tbl th { background:#f2f2f2; font-weight:700; text-align:left; }
.center { text-align:center; }
.right  { text-align:right; white-space:nowrap; }
/* Center ONLY the table headers for Ticker and Percent/Shares */
.tbl thead th.col-ticker { text-align: center; }
.tbl thead th.col-value  { text-align: center; }

/* Column widths (desktop defaults) */
th.col-company, td.col-company { white-space:nowrap; min-width:11ch; width:39ch; max-width:39ch; }
th.col-category, td.col-category { white-space:nowrap; min-width:6ch;  width:22ch; max-width:22ch; }
th.col-ticker,   td.col-ticker   { width:74px; }

/* Shares column (Row 1 / Card 3) */
.shares-wide th.col-value, .shares-wide td.col-value { width:100px !important; white-space:nowrap; }

/* ---------------- Breakpoints ---------------- */

/* DESKTOP (>=1700px): force 3-up */
@media (min-width: 1700px){
  div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    flex: 0 0 32%;
    min-width: 300px;
  }
  .card { max-width: none; }
}

/* NON-DESKTOP (<1699.98px): ALWAYS 1-up, centered, fixed standard width */
@media (max-width: 1699.98px){
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    flex: 0 0 100%;
  }
  .card{
    max-width: 720px;
    margin-left: auto;
    margin-right: auto;
  }
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

# -------------------------
# Paths (portable for Cloud)
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR   = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"

# -------------------------
# Helpers
# -------------------------
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

def row_spacer(height_px: int = 14):
    st.markdown(f"<div style='height:{height_px}px'></div>", unsafe_allow_html=True)

def _image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

def _fmt_pct(val):
    try:
        v = float(val) * 100
        return f"{v:,.2f}%"
    except Exception:
        return "—"

def _fmt_millions(val):
    try:
        v = float(val)
        return f"{v:,.2f} M"
    except Exception:
        return "—"

def _fmt_num(val):
    try:
        return f"{float(val):,.0f}"
    except Exception:
        return "—"

def _pick(df: pd.DataFrame, candidates: list[str], default: str | None = None):
    for c in candidates:
        if c in df.columns:
            return c
        for col in df.columns:
            if col.lower() == c.lower():
                return col
    return default

def _table_html(title: str, df: pd.DataFrame, value_col: str, value_label: str, value_fmt, value_width_px: int = 90, extra_class: str = ""):
    # tolerant column mapping
    cmap = {c.lower(): c for c in df.columns}
    tcol = cmap.get("ticker") or "Ticker"
    ncol = cmap.get("ticker_name") or cmap.get("company") or "Company"
    ccol = cmap.get("category") or cmap.get("exposure") or "Exposure"

    rows = []
    for _, r in df.iterrows():
        rows.append(f"""
<tr>
  <td class="col-company">{r.get(ncol, "")}</td>
  <td class="center col-ticker">{_mk_ticker_link(r.get(tcol, ""))}</td>
  <td class="col-category">{r.get(ccol, "")}</td>
  <td class="right col-value" style="width:{value_width_px}px">{value_fmt(r.get(value_col))}</td>
</tr>""")

    return textwrap.dedent(f"""
<div class="card {extra_class}">
  <h3>{title}</h3>
  <table class="tbl">
    <thead>
      <tr>
        <th class="col-company">Name</th>
        <th class="col-ticker">Ticker</th>
        <th class="col-category">Category</th>
        <th class="right col-value" style="width:{value_width_px}px">{value_label}</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</div>
""").strip()

def render_card(slot, title: str, df: pd.DataFrame, value_col: str, value_label: str, value_fmt, value_width_px: int = 90, extra_class: str = ""):
    with slot:
        if df.empty or value_col is None:
            st.info(f"No data for {title}.")
            return
        st.markdown(_table_html(title, df, value_col, value_label, value_fmt, value_width_px, extra_class), unsafe_allow_html=True)

# ------------- Helper for plain table-in-card -------------
def render_table_card(container, title: str, df):
    with container:
        table_html = df.to_html(index=False, classes="tbl", escape=False)
        st.markdown(
            f"""
            <div class="card">
              <h3>{title}</h3>
              {table_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

# -------------------------
# Timeframe selector & wiring
# -------------------------
TF_LABELS = ["Daily", "Weekly", "Monthly", "Quarterly"]
tf = st.session_state.get("tf_select", TF_LABELS[0])

# CSV map per card (by timeframe)
CSV_MAP = {
    "Daily":    [26, 27, 28, 70, 71, 72, 29, 30, 31],
    "Weekly":   [52, 53, 54, 55, 56, 57, None, None, None],
    "Monthly":  [58, 59, 60, 61, 62, 63, None, None, None],
    "Quarterly":[64, 65, 66, 67, 68, 69, None, None, None],
}
# Value column candidates by card index (0-based)
RET_CANDIDATES = ["Percent","daily_return_pct","wtd_return_pct","mtd_return_pct","qtd_return_pct","percent","value"]
VOL_CANDIDATES = ["Shares","Volume","shares","volume","value"]
CHG_CANDIDATES = ["model_score_day_change","model_score_wtd_change","model_score_mtd_change","model_score_qtd_change","Change","change","value"]
SCORE_CANDIDATES = ["Score","model_score","value"]

# Titles per card (base, we’ll prefix timeframe)
TITLES = [
    "Top Ten Percentage Gainers",
    "Top Ten Percentage Decliners",
    "Most Active (Shares)",
    "Top Ten Markmentum Score Gainers",
    "Top Ten Markmentum Score Decliners",
    "Markmentum Score Change Distribution",
    "Highest Markmentum Score",
    "Lowest Markmentum Score",
    "Markmentum Score Histogram",
]

def tf_prefix(title: str) -> str:
    return f"{tf} – {title}"

@st.cache_data(show_spinner=False)
def load_for_timeframe(tf_key: str, data_dir: Path):
    nums = CSV_MAP[tf_key]
    dfs = []
    for num in nums:
        if num is None:
            dfs.append(pd.DataFrame())
        else:
            dfs.append(load_csv(data_dir / f"qry_graph_data_{num}.csv"))
    return dfs

dfs = load_for_timeframe(tf, DATA_DIR)

# -------------------------
# Header (logo centered) + as of date + page title
# -------------------------
if LOGO_PATH.exists():
    st.markdown(
        f"""
        <div style="text-align:center; margin: 8px 0 16px;">
            <img src="data:image/png;base64,{_image_to_base64(LOGO_PATH)}" width="440">
        </div>
        """,
        unsafe_allow_html=True,
    )

# Date under the logo from the first CSV for this timeframe
df_date = dfs[0].copy()
date_col = next((c for c in df_date.columns if c.lower() in ("date","as_of_date","trade_date")), None)
asof = pd.to_datetime(df_date[date_col], errors="coerce").max() if (date_col and not df_date.empty) else pd.NaT
date_str = f"{asof.month}/{asof.day}/{asof.year}" if pd.notna(asof) else ""

if date_str:
    st.markdown(
        f"""
        <div style="text-align:center; margin:-6px 0 14px;
                    font-size:18px; font-weight:600; color:#1a1a1a;">
            {tf} Market Overview – {date_str}
        </div>
        """,
        unsafe_allow_html=True,
    )

#row_spacer(2)

# Center the dropdown under the title
c1, c2, c3 = st.columns([1, .8, 1])  # middle column slightly narrower

with c2:
    st.markdown(
        """
        <style>
        /* Cap the FIRST selectbox (the timeframe picker) on smaller screens */
        @media (max-width: 1699.98px){
          div[data-testid="stSelectbox"]:first-of-type{
            max-width: 600px !important;   /* set to your card width */
            margin: 0 auto !important;     /* center it */
          }
          /* Ensure the BaseWeb control inside respects the cap */
          div[data-testid="stSelectbox"]:first-of-type [data-baseweb="select"],
          div[data-testid="stSelectbox"]:first-of-type div[role="combobox"]{
            width: 100% !important;
            max-width: 600px !important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    selected_tf = st.selectbox(
        "Select timeframe",
        TF_LABELS,
        index=TF_LABELS.index(tf),
        key="tf_select",
        label_visibility="collapsed",  # hides the "Select timeframe" label
    )

# Rerun if changed so titles/tables refresh
if selected_tf != tf:
    st.rerun()

#row_spacer(3)

# -------------------------
# ROW 1 (3 cards): gainers / decliners / most active
# -------------------------
c1, c2, c3 = st.columns([1,1,1], gap="large")

df1 = dfs[0].copy()
col_pct = _pick(df1, RET_CANDIDATES, default=None)
render_card(c1, tf_prefix(TITLES[0]), df1, col_pct, "Percent", _fmt_pct)

df2 = dfs[1].copy()
col_pct2 = _pick(df2, RET_CANDIDATES, default=None)
render_card(c2, tf_prefix(TITLES[1]), df2, col_pct2, "Percent", _fmt_pct)

df3 = dfs[2].copy()
col_shares = _pick(df3, VOL_CANDIDATES, default=None)
render_card(c3, tf_prefix(TITLES[2]), df3, col_shares, "Shares", _fmt_millions, value_width_px=120, extra_class="shares-wide")

row_spacer(14)

# -------------------------
# ROW 2 (3 cards): Score Gainers / Decliners / Score Change Dist
# -------------------------
d1, d2, d3 = st.columns([1,1,1], gap="large")

df4 = dfs[3].copy()
col_change_hi = _pick(df4, CHG_CANDIDATES, default=None)
render_card(d1, tf_prefix(TITLES[3]), df4, col_change_hi, "Change", _fmt_num)

df5 = dfs[4].copy()
col_change_lo = _pick(df5, CHG_CANDIDATES, default=None)
render_card(d2, tf_prefix(TITLES[4]), df5, col_change_lo, "Change", _fmt_num)

with d3:
    df_dist = dfs[5].copy()
    if df_dist.empty:
        st.info(f"No data for {tf_prefix(TITLES[5])}.")
    else:
        score_bin_col = "Score_Bin" if "Score_Bin" in df_dist.columns else "score_bin"
        count_col = "TickerCount" if "TickerCount" in df_dist.columns else "ticker_count"
        df_dist = df_dist[[score_bin_col, count_col]].copy()
        df_dist.columns = ["Score Bin", "Ticker Count"]
        table_html = df_dist.to_html(index=False, classes="tbl", escape=False)
        st.markdown(
            f"""
            <div class="card">
              <h3>{tf_prefix(TITLES[5])}</h3>
              {table_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

row_spacer(14)

# -------------------------
# ROW 3 (3 cards): Highest Score / Lowest Score / Score Distribution (hist)
# Daily only for Cards 7-9
# -------------------------
show_daily_extra = (tf == "Daily")

if show_daily_extra:
    e1, e2, e3 = st.columns([1,1,1], gap="large")

    df6 = dfs[6].copy()
    col_score_hi = _pick(df6, SCORE_CANDIDATES, default=None)
    render_card(e1, tf_prefix(TITLES[6]), df6, col_score_hi, "Score", _fmt_num)

    df7 = dfs[7].copy()
    col_score_lo = _pick(df7, SCORE_CANDIDATES, default=None)
    render_card(e2, tf_prefix(TITLES[7]), df7, col_score_lo, "Score", _fmt_num)

    with e3:
        df_hist = dfs[8].copy()
        if df_hist.empty:
            st.info(f"No data for {tf_prefix(TITLES[8])}.")
        else:
            mapping = {
                "Below -100": "Strong Sell",
                "-100 to -26": "Sell",
                "-25 to 25": "Neutral",
                "26 to 100": "Buy",
                "Above 100": "Strong Buy",
            }
            score_bin_col = "Score_Bin" if "Score_Bin" in df_hist.columns else "score_bin"
            count_col = "TickerCount" if "TickerCount" in df_hist.columns else "ticker_count"

            df_hist["Classification"] = df_hist[score_bin_col].map(mapping)
            df_hist = df_hist[["Classification", score_bin_col, count_col]].copy()
            df_hist.columns = ["Classification", "Score Bin", "Ticker Count"]

            table_html = df_hist.to_html(index=False, classes="tbl", escape=False)
            st.markdown(
                f"""
                <div class="card">
                  <h3>{tf_prefix(TITLES[8])}</h3>
                  {table_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
            
    row_spacer(14)

    df_od = load_csv(DATA_DIR / "qry_graph_data_92.csv").copy()

    # ---- FORMAT PERCENTAGE COLUMNS (display only) ----
    for col in ["Buy %", "Neutral %", "Sell %"]:
        if col in df_od.columns:
            df_od[col] = df_od[col].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else ""
            )

    if df_od.empty:
        st.info("No data for Opportunity Density.")
    else:
        # Force column widths via HTML <colgroup> since render_table_card() uses df.to_html()
        ncols = df_od.shape[1]

        colgroup = (
            "<colgroup>"
            + '<col style="width:220px;">'  # Category wide
            + "".join('<col style="width:50px;">' for _ in range(ncols - 1))  # all other cols tight
            + "</colgroup>"
        )

        table_html = df_od.to_html(index=False, classes="tbl", escape=False)
        # --- IMPORTANT: remove pandas "dataframe" class so Streamlit/pandas default CSS can't override .tbl ---
        table_html = table_html.replace('class="dataframe tbl"', 'class="tbl"')
        table_html = table_html.replace('class="dataframe"', 'class="tbl"')  # safety fallback
        table_html = table_html.replace('border="1"', 'border="0"')          # optional: keeps borders controlled by .tbl CSS

        # Inject <colgroup> right after the opening <table ...> tag
        table_html = table_html.replace(">", ">" + colgroup, 1)

        st.markdown(
            f"""
<style>
/* Opportunity Density card width only */
#od_card {{
  max-width: 1450px !important;
  width: 100% !important;
  margin-left: auto !important;
  margin-right: auto !important;
}}

/* Contain wide table */
#od_card .od_table_wrap {{
  overflow-x: auto;
}}

/* ---- TYPOGRAPHY MATCH ---- */
#od_card, #od_card * {{
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}}

/* ---- FORCE TABLE FONT SIZE MATCH ---- */
#od_card table.tbl th,
#od_card table.tbl td {{
  font-size: 13px !important;
}}


/* ---- ALIGNMENT FIXES ONLY (no font changes) ---- */

/* Center ALL headers */
#od_card table thead th {{
  text-align: center !important;
}}

/* Left-align Category column */
#od_card table th:first-child,
#od_card table td:first-child {{
  text-align: left !important;
}}

/* Right-align ALL numeric cells */
#od_card table tbody td:not(:first-child) {{
  text-align: right !important; 
}}

/* Opportunity Density footnote */
#od_card .od_note {{
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}}
#od_card .od_note {{ padding-left: 2px; }}
</style>

<div class="card" id="od_card">
  <h3>Opportunity Density</h3>

  <div class="od_table_wrap">
    {table_html}
  </div>

  <div class="od_note">
    <strong>Note:</strong>
    Buy classifications require <em>Risk/Reward ≥ 3</em> <strong>and</strong> <em>MM Score &gt; 25</em>.
    Sell classifications require <em>Risk/Reward ≤ −3</em> <strong>and</strong> <em>MM Score &lt; −25</em>.
  </div>
</div>
""",
unsafe_allow_html=True,
        )

# ========= Market Read (per timeframe) =========
import os
import streamlit.components.v1 as components
MR_HTML = {
    "Daily":     "Market_Read_daily.html",
    "Weekly":    "Market_Read_weekly.html",
    "Monthly":   "Market_Read_monthly.html",
    "Quarterly": "Market_Read_quarterly.html",
}

def load_market_read_html(path: Path) -> str:
    if not path.exists():
        return f"<div style='text-align:center;color:#b91c1c;'>⚠️ Market Read HTML not found: {path.name}</div>"
    return path.read_text(encoding="utf-8")

mr_path = DATA_DIR / MR_HTML[tf]
mr_html = load_market_read_html(mr_path)

note_html = (
    "<div class='market-read-note'>Note: Indices are excluded from Highest/Lowest Markmentum Score lists.</div>"
    if show_daily_extra else ""
)

# Compose HTML, then dedent to remove leading spaces that can trigger Markdown code blocks
mr_html = f"""
<div class="market-read-wrapper">
  
  {mr_html}
  {note_html}
</div>
"""
# Render the full HTML doc inside the Streamlit page
row_spacer(14)
components.html(mr_html, height=900, scrolling=True)
#st.markdown(textwrap.dedent(mr_html), unsafe_allow_html=True)

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