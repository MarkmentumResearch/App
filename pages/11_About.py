

import base64
from pathlib import Path
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import os
import streamlit.components.v1 as components


# --- NO-REDIRECT LANDING GUARD (place at the top of 01_About.py) ---
# 1) Absolute safe mode (via secret or ?safe=1) — never leave About.
safe_mode = bool(st.secrets.get("SAFE_MODE", False)) or st.query_params.get("safe", ["0"])[0] == "1"
if safe_mode:
    # Pin the session to About and clear params that some routers use
    st.session_state["_disable_redirects"] = True
    st.session_state["_last_route"] = "about"
    if st.query_params:
        st.query_params.clear()
    # Optional: a tiny note while testing (remove if you like)
    st.caption("Safe mode: redirects disabled on landing.")
    # Stop here so nothing else can trigger a reroute
    st.stop()

# 2) For normal visitors, still pin the initial route to 'about' and normalize params.
#    This doesn't stop the page; it just makes your routers idempotent.
if not st.session_state.get("_last_route"):
    st.session_state["_last_route"] = "about"
# If you use a query-param router elsewhere, neutralize it on About:
if st.query_params:
    st.query_params.clear()
# -------------------------------------------------------------------



# -------------------------
# Page & shared style
# -------------------------
st.cache_data.clear()
st.set_page_config(page_title="Markmentum – About", layout="wide", initial_sidebar_state="expanded")

# Always expand sidebar on page load (safe: only clicks if collapsed control is present)
components.html("""
<script>
(function () {
  function tryOpen() {
    const doc = window.parent.document;
    const ctrl = doc.querySelector('div[data-testid="stSidebarCollapsedControl"] button');
    if (ctrl) { ctrl.click(); return true; }  // only present when sidebar is collapsed
    return false;
  }
  let n = 0;
  const t = setInterval(() => { if (tryOpen() || n++ > 10) clearInterval(t); }, 100);
})();
</script>
""", height=0, width=0)


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

# -------------------------
# About content (hard-coded from "MR About v2")
# -------------------------
st.markdown(
    """
<div style="max-width:900px; margin: 0 auto;">

<p style="font-weight:600; margin:12px 0 18px;">
Markets + Momentum = Markmentum Research.  The equation to achieve trading, investing, and portfolio management success.
</p>

<p style="font-weight:600; margin:12px 0 18px;">
We deliver volatility-adjusted probable ranges, proprietary scoring, and AI-generated market reads that frame growth and inflation expectations — plus probability-driven signals across major market tickers and indices—through a sleek, modern portal. Actionable data. Focused insights. Zero noise.
</p>

<p style="font-weight:600; margin:12px 0 18px;">You're the captain. We provide the coordinates. Let us help you navigate markets with clarity and confidence.</p>

<h3>Why Markmentum Research</h3>
<p>
  Traditional buy-and-hold investing has long been taught as the optimal strategy for long-term wealth creation. While it can still play a role, today’s markets are more volatile, more cyclical, and more sensitive to macro forces than in the past. 
  As a result, investors increasingly need tools that help manage risk dynamically while seeking consistent compounding over multiple time horizons.
</p>
<p>
  Markmentum Research provides a volatility-adjusted, probability-driven market framework designed to help investors better understand risk and reward across daily, weekly, and longer-term timeframes. 
  By combining price behavior, trend structure, and quantitative signals, our approach helps users tilt exposure toward asymmetric opportunities where upside potential outweighs downside risk—while avoiding crowded, stretched setups.
</p>
<p>
  Rather than relying on narratives or predictions, Markmentum emphasizes disciplined, data-driven decision-making to support capital preservation and repeatable outcomes across changing market regimes.
</p>

<h3>What we publish</h3>
<ul>
  <li><b>Probable Ranges &amp; Probable Anchors</b> – Forward ranges that frame upside/downside by day, week, and month, plus long-term probable anchor levels to gauge extension and mean-reversion risk.</li>
  <li><b>Directional Trends</b> – Short, mid, and long-term trend lines alongside their changes with tape bias cues (Buy/Sell, Leaning Bullish/Bearish, Neutral, Topping/Bottoming).</li>
  <li><b>Volatility Stats</b> – Implied (Ivol) vs. Realized (Rvol) spreads, percentile ranks, and Z-Scores to spot crowding and regime shifts.</li>
  <li><b>Markmentum Score</b> – a rules-based, volatility-adjusted risk–reward score — the navigator allowing you, the captain, to steer the ship to your destination with clarity and confidence.</li>
  <li><b>Heatmaps</b> – Data tables and heatmaps for broad performance distribution, risk-adjusted performance layer, and core signal distribution to surface opportunity and risk fast.</li>
  <li><b>Signals</b> – Curated tactical lists designed to highlight near-term opportunities and crowding dynamics across the instrument universe. Each list distills probabilistic signals into actionable context for different trading styles.</li>
  <li><b>Updates</b> – Nightly refresh after market close (typically 8:15PM ET).</li>
</ul>

<h3>How to use the app</h3>
<ul>
  <li><b>Morning Compass</b> – Your orientation dashboard across major indices, sectors, and macro levers — with a one-click Daily / Weekly / Monthly selector. 
  Displays probable ranges, risk/reward bias, and Markmentum Scores for key macro exposures (Indices, S&P 500 sectors, Gold, USD, TLT, BTC Futures), plus top 5 gainers and laggards by % change and by Markmentum Score, 
  along with an optional category snapshot for deeper drill-downs. On the Daily view, Morning Compass also includes USD and Rates Correlation snapshots, showing how equities, sectors, commodities, and other assets have recently moved 
  relative to the U.S. Dollar (via DXY) and 10-Year Treasury yields — helping frame near-term sensitivity and cross-asset influences. Auto-refreshed for a concise, data-first read on market direction, sector leadership and risk sentiment.</li>
  <li><b>Market Overview</b> – A single, unified page with a timeframe selector (Daily / Weekly / Monthly / Quarterly). Each view displays the top percentage gainers and decliners, Most Active (Shares), and Markmentum Score change distribution.
    The Daily view additionally includes the Top-10 Highest and Lowest Markmentum Scores, a Markmentum Score histogram, and the Opportunity Density report, which summarizes the distribution of Buy, Neutral, and Sell setups across categories based on Risk/Reward and Markmentum Score thresholds.
      At the bottom of the page, each timeframe features an AI-generated Market Read summarizing key market dynamics and macro context.</li>
  <li><b>Performance Heatmap</b> – Multi-layered view of realized market performance across categories and tickers. Begins with key macro tickers and category-level averages, then allows a drill-down by category to explore per-ticker percentage changes. 
  Displays Daily, WTD, MTD, and QTD returns, with each timeframe independently scaled for clarity. The layout combines table and heatmap views to show where performance strength or weakness has already occurred, complementing the forward-looking insights from the Markmentum Heatmap. 
  Includes a sortable, searchable, and downloadable table at the bottom.</li>
  <li><b>Sharpe Rank Heatmap</b> – Multi-layered view of risk-adjusted performance across categories and tickers. Begins with key macro tickers and category-level averages, then allows a drill-down by category to explore per-ticker Sharpe Percentile Ranks. 
  Displays current rank alongside Daily, WTD, MTD, and QTD changes, with each timeframe independently scaled for clarity. The layout combines table and heatmap views to highlight where relative performance strength or weakness is emerging across the market. 
  Includes a sortable, searchable, and downloadable table at the bottom.</li>
  <li><b>Markmentum Heatmap</b> – Multi-layered view of opportunity and risk across the entire instrument universe. Begins with key macro tickers and category-level averages, then allows a drill-down by category to see detailed per-ticker positioning. 
  Displays the current score alongside Daily, WTD, MTD, and QTD changes, with each timeframe independently scaled for clarity. Together, the table and heatmap reveal where opportunity and risk are shifting over time. 
  Includes a sortable, searchable, and downloadable table at the bottom.</li>
  <li><b>Directional Trends</b> – Multi-timeframe dashboard visualizing short-, mid-, and long-term directional trends alongside their changes. Displays key macro exposures (Indices, S&P 500 sectors, Gold, USD, TLT, BTC Futures) to highlight trend alignment or divergence across time horizons. 
  Includes per-ticker drill-downs by category to show how leadership and rotation are evolving beneath the surface. Color-coded for quick recognition of positive (green) and negative (red) shifts. 
  Each row includes a Tape Bias field summarizing overall market bias (e.g., Buy/Sell, Leaning Bullish/Bearish, Neutral, Topping/Bottoming). Includes a sortable, searchable, and downloadable table at the bottom. </li>
  <li><b>Vantage Point</b> – Unified snapshot of Sharpe Rank, Markmentum Score, and Tape Bias by timeframe. Starts with macro orientation, then averages by category, and finally drills down to per-ticker detail. 
  Highlights where performance, risk, and sentiment are aligning or diverging across the market.</li>
  <li><b>Deep Dive Dashboard</b> – Full per instrument view: probable ranges, probable anchors, trend lines, gap-to-anchor, volatility stats, Sharpe percentile ranks, Markmentum Score, and more.</li>
  <li><b>Signals</b> – Tactical screens for chase/no chase, watch, up-cycle, crowding, and upside/downside lists to surface where conviction and risk are shifting.</li>
  <li><b>Universe</b> – Full list of instruments with ticker, name, category, last close, and day/week/month/quarter percent changes. 
  Quick filter and CSV export. Coverage includes major indices, sector/style ETFs, currencies, commodities, bonds, and yields, plus full S&P 500 coverage and selected single names (including Bitcoin, ES, and NQ futures).</li>
  <li><b>Education</b> – Structured, plain-English walkthrough of the Markmentum framework and underlying signals. Covers probable ranges, trend lines, probable anchors, volatility regimes, crowding, asymmetry vs. stretch, and key guardrails used throughout the platform. 
  Designed to help users understand why the tools behave the way they do, so insights can be applied with clarity, confidence, and discipline. Includes visual examples and a downloadable PDF reference.</li> 
  <li><b>Contact</b> – Have questions or feedback? Send us a note and we’ll get back to you as soon as possible.</li>  
  <li><b>Downloads</b> – Central hub for exporting the same data that powers the Markmentum portal. Includes full-history CSVs for the Stat Box (all tickers, all dates), the latest Signal Box (all tickers, most recent date), and all datasets used in the Deep Dive Dashboard charts. 
  Each file displays its size, with one-click download options or a consolidated download ALL (.zip) built on demand. 
  Exports refresh nightly and mirror the calculations shown throughout the app—ideal for back-testing, research notes, and integrating Markmentum data into custom models and reports.</li>  
  <li><b>Research Pack Generator</b> – Build a customized, exportable PDF Research Pack from the Markmentum Research portal — designed for offline review, sharing, and archival, and repeatable institutional-style research workflows.</li>  
</ul>

<h3>Methodology</h3>
<ul>
  <li><b>Probable Ranges</b> – Calculated independently for highs and lows using: (1) the high or low price series, (2) realized volatility on that series, (3) volatility-of-volatility on that series, and (4) volume volatility. 
  These inputs generate the probable high and low across daily, weekly, and monthly horizons. By building the model on highs and lows—rather than just closes—the ranges capture more information about market behavior. </li>
  <li><b>Directional Trends</b> – Short-, mid-, and long-term composites derived by netting the volatility-adjusted factors behind probable highs and lows, providing a directional trend signal.</li>
  <li><b>Probable Anchors</b> – Anchor levels are extrapolated by aligning short-term trend structure with long-term trend structure, creating a probabilistic reference to gauge extension and mean-reversion risk.</li>
  <li><b>Volatility Stats</b> – 30-day Z-scores, Percentile Ranks, Ivol/Rvol Spreads, and Regime Flags.</li>
  <li><b>Markmentum Score</b> – A proprietary, rules-based, volatility-adjusted risk/reward framework that blends multiple market signals into a single intuitive scale. A high positive score favors the long side; a negative score favors the short side.</li>
</ul>

<h3>Our Why</h3>
<p>
  Markmentum Research was born from a passion for markets and numbers — but it’s guided by faith. 
  All glory and honor to the Lord, who makes every step possible.
</p>
<p>
  Our mission is to deliver actionable, probability-driven insights without noise or narratives, 
  helping market participants steward their resources with clarity and confidence.
</p>
</div>
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