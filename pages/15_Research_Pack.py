import streamlit as st
st.set_page_config(page_title="Markmentum – Research Pack", layout="wide")

from utils.auth import verify_proof, make_proof, make_session, verify_session, restore_session_from_cookie2

session = st.session_state.get("session")

# --- Gate Morning Compass ---
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


# 16_Reports_v4.py
from pathlib import Path
import io
import os
import pandas as pd
import numpy as np
# PDF (ReportLab)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, KeepInFrame, KeepTogether
)
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import ListFlowable, ListItem

# Merge PDFs (UI layer only)
from pypdf import PdfReader, PdfWriter

try:
    from docx import Document
except Exception:
    Document = None

# -------------------------
# Paths (match Morning Compass style)
# -------------------------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent

DATA_DIR   = APP_DIR / "data"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH  = ASSETS_DIR / "markmentum_logo.png"


# -------------------------
# Shared helpers (unchanged)
# -------------------------
def fmt_num(x, nd=2):
    try:
        if pd.isna(x):
            return ""
        return f"{float(x):,.{nd}f}"
    except Exception:
        return ""

def fmt_pct(x, nd=2):
    try:
        if pd.isna(x):
            return ""
        return f"{float(x)*100:,.{nd}f}%"
    except Exception:
        return ""

def fmt_int(x):
    try:
        if pd.isna(x):
            return ""
        return f"{int(round(float(x))):,}"
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def load_csv_by_id(n: int, base_dir: Path) -> pd.DataFrame:
    p = base_dir / f"qry_graph_data_{n}.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)

def mo_load_for_timeframe(tf_key: str) -> list[pd.DataFrame]:
    nums = MO_CSV_MAP[tf_key]
    dfs: list[pd.DataFrame] = []
    for n in nums:
        if n is None:
            dfs.append(pd.DataFrame())
        else:
            dfs.append(load_csv_by_id(n, DATA_DIR))
    return dfs

def _mo_asof_from_df(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    date_col = None
    for c in df.columns:
        if str(c).strip().lower() in ("date", "as_of_date", "trade_date"):
            date_col = c
            break
    if not date_col:
        return ""
    asof = pd.to_datetime(df[date_col], errors="coerce").max()
    if pd.isna(asof):
        return ""
    return f"{asof.month}/{asof.day}/{asof.year}"


def clean_text(s: str) -> str:
    """Normalize common unicode punctuation so Helvetica can render it (prevents ■■)."""
    if s is None:
        return ""
    s = str(s)

    # dashes/hyphens
    s = s.replace("\u2011", "-")  # non-breaking hyphen
    s = s.replace("\u2013", "-")  # en dash
    s = s.replace("\u2014", "-")  # em dash

    # quotes/apostrophes
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201C", '"').replace("\u201D", '"')

    # misc invisible/soft
    s = s.replace("\u00ad", "")   # soft hyphen
    s = s.replace("\u200b", "")   # zero-width space

    return s

from xml.sax.saxutils import escape as _xml_escape

def pdf_safe_text(s: str) -> str:
    """
    Make text safe for ReportLab Paragraph (XML-based).
    Escapes &, <, > but leaves quotes alone.
    """
    if s is None:
        return ""
    return _xml_escape(str(s), {"'": "'", '"': '"'})


def _read_docx_plain_text(doc_path: Path) -> str:
    """Return docx text, or empty string if missing/unreadable (never print errors into PDF)."""
    if Document is None:
        return ""

    if not doc_path.exists():
        return ""

    try:
        doc = Document(str(doc_path))
        lines = []
        for p in doc.paragraphs:
            t = (p.text or "").strip()
            if t:
                lines.append(t)
        return clean_text("\n".join(lines).strip())
    except Exception:
        return ""
import re

def _read_txt_plain_text(p: Path) -> str:
    """Return txt content, or empty string if missing/unreadable."""
    try:
        if not p.exists():
            return ""
        return clean_text(p.read_text(encoding="utf-8", errors="ignore").strip())
    except Exception:
        return ""

def _read_html_plain_text(p: Path) -> str:
    """
    HTML -> plain text for your generated Market Read HTML.
    - removes <style>/<script> blocks completely (prevents CSS showing in PDF)
    - preserves bullets from <li>
    - turns <br> and </p> into newlines
    - strips remaining tags
    - normalizes 'Daily/Weekly/Monthly/Quarterly Market Read:' -> 'Market Read:'
    - drops standalone 'Market Read' line (the big centered H2 in HTML)
    """
    try:
        if not p.exists():
            return ""
        html = p.read_text(encoding="utf-8", errors="ignore")

        # 1) REMOVE style/script blocks (this is the key fix)
        html = re.sub(r"(?is)<style[^>]*>.*?</style>", "", html)
        html = re.sub(r"(?is)<script[^>]*>.*?</script>", "", html)

        # 2) normalize breaks
        html = re.sub(r"(?i)<br\s*/?>", "\n", html)
        html = re.sub(r"(?i)</p\s*>", "\n", html)

        # 3) list items -> "- ..."
        html = re.sub(r"(?is)<li[^>]*>\s*", "- ", html)
        html = re.sub(r"(?is)</li\s*>", "\n", html)

        # 4) strip remaining tags
        html = re.sub(r"(?is)<[^>]+>", "", html)

        # 5) decode a couple entities (minimal)
        html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

        # 6) cleanup whitespace
        lines = [ln.strip() for ln in html.splitlines()]
        lines = [ln for ln in lines if ln]

        # 7) normalize header line to match PDF expectation
        #    "Daily Market Read: January 23, 2026" -> "Market Read: January 23, 2026"
        normed = []
        for ln in lines:
            if ln.strip().lower() == "market read":
                continue  # drop the big centered title from HTML
            # Only normalize DAILY -> Market Read. Keep Weekly/Monthly/Quarterly as-is.
            ln = re.sub(r"(?i)^daily\s+market read:\s*", "Market Read: ", ln)
            normed.append(ln)

        return clean_text("\n".join(normed).strip())
    except Exception:
        return ""

def _read_plain_text_any(p: Path) -> str:
    """
    Unified reader:
    - .txt  -> txt
    - .html -> html->text
    - .docx -> docx (existing)
    """
    suf = p.suffix.lower()
    if suf == ".txt":
        return _read_txt_plain_text(p)
    if suf in (".html", ".htm"):
        return _read_html_plain_text(p)
    if suf == ".docx":
        return _read_docx_plain_text(p)
    return ""

def _market_read_to_flowables(mr_text: str) -> list:
    """
    Converts Market Read plain text into PDF flowables with bullets for key lines.
    """
    out = []
    lines = [ln.strip() for ln in (mr_text or "").splitlines()]
    lines = [ln for ln in lines if ln]  # drop blanks

    bullets = []
    in_bullets = False

    for ln in lines:
        low = ln.lower()

        # section headers / labels
        if low.startswith("market read:") or low.startswith("weekly market read:") or low.startswith("monthly market read:") or low.startswith("quarterly market read:"):
            out.append(Spacer(1, 6))
            out.append(Paragraph(clean_text(ln), H2))
            in_bullets = False
            continue

        if low in ("the market is saying:", "the market is saying (all numbers are wtd % returns):", 
                   "the market is saying (all numbers are mtd % returns):","the market is saying (all numbers are qtd % returns):","macro levers:", "macro levers (wtd % returns):", 
                   "macro levers (mtd % returns):", "macro levers (qtd % returns):"):
            # flush existing bullets
            if bullets:
                out.append(ListFlowable(bullets, bulletType="bullet", leftIndent=18))
                bullets = []
            out.append(Spacer(1, 6))
            out.append(Paragraph(clean_text(ln), H2))
            in_bullets = True
            continue

        if low.startswith("bottom line:"):
            if bullets:
                out.append(ListFlowable(bullets, bulletType="bullet", leftIndent=18))
                bullets = []
            out.append(Spacer(1, 10))
            out.append(Paragraph(clean_text(ln), P))
            in_bullets = False
            continue

        # normal lines
        if in_bullets:
            ln2 = ln
            if ln2.startswith("- "):
                ln2 = ln2[2:].lstrip()
            bullets.append(ListItem(Paragraph(clean_text(ln2), P)))
        else:
            out.append(Paragraph(clean_text(ln), P))

    if bullets:
        out.append(ListFlowable(bullets, bulletType="bullet", leftIndent=18))

    return out

def get_last_trading_date() -> str:
    """
    Single source of truth for Research Pack 'Data as of'.
    Uses Daily Macro Orientation CSV.
    """
    df = load_csv_by_id(29, DATA_DIR)  # Daily Macro Orientation
    if df.empty or "Date" not in df.columns:
        return ""
    asof = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(asof):
        return ""
    return f"{asof.month}/{asof.day}/{asof.year}"



DISCLAIMER_TEXT = (
    "© 2026 Markmentum Research LLC. Disclaimer: This content is for informational purposes only. "
    "Nothing herein constitutes an offer to sell, a solicitation of an offer to buy, or a recommendation "
    "regarding any security, investment vehicle, or strategy. It does not represent legal, tax, accounting, "
    "or investment advice by Markmentum Research LLC or its employees. The information is provided without "
    "regard to individual objectives or risk parameters and is general, non-tailored, and non-specific. "
    "Sources are believed to be reliable, but accuracy and completeness are not guaranteed. "
    "Markmentum Research LLC is not responsible for errors, omissions, or losses arising from use of this material. "
    "Investments involve risk, and financial markets are subject to fluctuation. Consult your financial professional "
    "before making investment decisions."
)

# Timeframe config (aligned with Morning Compass)
TIMEFRAMES = {
    "Daily": {
        "ids": {"main": 73, "leaders": 74, "mm": 75, "delta": 77},
        "cols": {"ret": "daily_Return", "pr_low": "day_pr_low", "pr_high": "day_pr_high", "rr": "day_rr_ratio"},
        "docx_macro": "bottom_line_daily.txt",
        "title_macro": "Daily Macro Orientation",
        "title_leaders": "Daily Top Five Leaders/Laggards by % Change",
        "title_mm": "Daily Top Five Leaders/Laggards by MM Score",
        "title_delta": "Daily Top Five Leaders/Laggards by MM Score Change",
    },
    "Weekly": {
        "ids": {"main": 78, "leaders": 79, "mm": 80, "delta": 82},
        "cols": {"ret": "weekly_Return", "pr_low": "week_pr_low", "pr_high": "week_pr_high", "rr": "week_rr_ratio"},
        "docx_macro": "bottom_line_weekly.txt",
        "title_macro": "Weekly Macro Orientation",
        "title_leaders": "Weekly Top Five Leaders/Laggards by % Change",
        "title_mm": "Weekly Top Five Leaders/Laggards by MM Score",
        "title_delta": "Weekly Top Five Leaders/Laggards by MM Score Change",
    },
    "Monthly": {
        "ids": {"main": 83, "leaders": 84, "mm": 85, "delta": 87},
        "cols": {"ret": "monthly_Return", "pr_low": "month_pr_low", "pr_high": "month_pr_high", "rr": "month_rr_ratio"},
        "docx_macro": "bottom_line_monthly.txt",
        "title_macro": "Monthly Macro Orientation",
        "title_leaders": "Monthly Top Five Leaders/Laggards by % Change",
        "title_mm": "Monthly Top Five Leaders/Laggards by MM Score",
        "title_delta": "Monthly Top Five Leaders/Laggards by MM Score Change",
    },
}

# =========================
# Market Overview config (from 03_Market_Overview.py)
# =========================
MO_TF_LABELS = ["Daily", "Weekly", "Monthly", "Quarterly"]

MO_CSV_MAP = {
    "Daily":     [26, 27, 28, 70, 71, 72, 29, 30, 31],
    "Weekly":    [52, 53, 54, 55, 56, 57, None, None, None],
    "Monthly":   [58, 59, 60, 61, 62, 63, None, None, None],
    "Quarterly": [64, 65, 66, 67, 68, 69, None, None, None],
}

# Market Read docx (same filenames as Market Overview page)
MO_MARKET_READ_DOCX = {
    "Daily":     "Market_Read_daily.html",
    "Weekly":    "Market_Read_weekly.html",
    "Monthly":   "Market_Read_monthly.html",
    "Quarterly": "Market_Read_quarterly.html",
}

# Opportunity Density (daily only in your page)
MO_OPPORTUNITY_DENSITY_CSV_ID = 92


# -------------------------
# PDF styling + builders (unchanged)
# -------------------------
styles = getSampleStyleSheet()
STYLES = {
    "Title": styles["Title"],
    "Heading2": styles["Heading2"],
    "Heading3": styles["Heading3"],
    "Normal": styles["BodyText"],
}
H1 = ParagraphStyle("H1", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], alignment=TA_LEFT, fontSize=12, spaceBefore=10, spaceAfter=6)
P  = ParagraphStyle("P", parent=styles["BodyText"], fontSize=9, leading=12)
NOTE = ParagraphStyle("NOTE", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.grey)
TH = ParagraphStyle(
    "TH",
    parent=styles["BodyText"],
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=9,
    alignment=TA_CENTER,
)

def th(text: str) -> Paragraph:
    return Paragraph(clean_text(text), TH)

def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillGray(0.45)

    available_width = doc.width
    lines = simpleSplit(DISCLAIMER_TEXT.strip(), "Helvetica", 7, available_width)

    x = doc.leftMargin
    y = 0.25 * inch
    max_lines = 6

    for i, line in enumerate(lines[:max_lines]):
        canvas.drawString(x, y + (max_lines - 1 - i) * 9, line)

    canvas.restoreState()

def _rr_bg_color(v: float, cap: float = 3.0):
    """
    PDF-friendly shading for Risk/Reward:
    - uses the same green/red family as Sharpe Rank
    - blends into white so it prints cleaner (esp. B/W)
    - intensity scales with |v| up to cap
    """
    try:
        v = float(v)
    except Exception:
        return colors.white

    # Normalize magnitude
    s = min(abs(v) / float(cap), 1.0)

    # lighter overall (Sharpe-style, but restrained for print)
    alpha = 0.05 + 0.14 * s  # 0.06 .. 0.22

    def _blend(rgb_255, a):
        r, g, b = [c / 255.0 for c in rgb_255]
        return colors.Color(
            1.0 * (1.0 - a) + r * a,
            1.0 * (1.0 - a) + g * a,
            1.0 * (1.0 - a) + b * a,
        )

    if v > 0:
        return _blend((16, 185, 129), alpha)   # green
    if v < 0:
        return _blend((239, 68, 68), alpha)    # red

    return colors.white

def _mm_bg_color(v: float, cap: float = 150.0):
    """
    PDF-friendly shading for MM Score:
    - consistent with Sharpe Rank palette (green/red/neutral gray)
    - blends into white (less bold, prints better)
    - intensity scales with |score| beyond a neutral band
    """
    try:
        score = float(v)
    except Exception:
        return colors.white

    # Clamp for stability
    score = max(-float(cap), min(float(cap), score))

    def _blend(rgb_255, a):
        r, g, b = [c / 255.0 for c in rgb_255]
        return colors.Color(
            1.0 * (1.0 - a) + r * a,
            1.0 * (1.0 - a) + g * a,
            1.0 * (1.0 - a) + b * a,
        )

    # Neutral band around 0: very light gray tint
    neutral_band = 25.0
    if -neutral_band <= score <= neutral_band:
        return _blend((156, 163, 175), 0.10)

    # Scale intensity outside neutral band
    s = (abs(score) - neutral_band) / (float(cap) - neutral_band)
    s = max(0.0, min(s, 1.0))

    alpha = 0.08 + 0.18 * s  # 0.08 .. 0.26

    if score > 0:
        return _blend((16, 185, 129), alpha)   # green
    else:
        return _blend((239, 68, 68), alpha)    # red

def _build_table(data_rows, col_widths, shade_rr=False, shade_mm=False, rr_col=None, mm_col=None):
    tbl = Table(data_rows, colWidths=col_widths, repeatRows=1)

    base = TableStyle([
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#d9d9d9")),
        ("FONT", (0,1), (-1,-1), "Helvetica", 8),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (1,0), (-1,0), "CENTER"),
        ("ALIGN", (1,1), (1,-1), "CENTER"),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,0), 6),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("TOPPADDING", (0,1), (-1,-1), 4),
        ("BOTTOMPADDING", (0,1), (-1,-1), 4),
    ])
    tbl.setStyle(base)

    if shade_rr and rr_col is not None:
        for r in range(1, len(data_rows)):
            raw = data_rows[r][rr_col]
            try:
                v = float(str(raw).replace(",", ""))
            except Exception:
                continue
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (rr_col, r), (rr_col, r), _rr_bg_color(v))
            ]))

    if shade_mm and mm_col is not None:
        for r in range(1, len(data_rows)):
            raw = data_rows[r][mm_col]
            try:
                v = float(str(raw).replace(",", ""))
            except Exception:
                continue
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (mm_col, r), (mm_col, r), _mm_bg_color(v))
            ]))

    return tbl

def _asof_date_from_main(tf_key: str) -> str:
    cfg = TIMEFRAMES[tf_key]
    df = load_csv_by_id(cfg["ids"]["main"], DATA_DIR)
    if df.empty or "Date" not in df.columns:
        return ""
    asof = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(asof):
        return ""
    return f"{asof.month}/{asof.day}/{asof.year}"

def _section_correlations(flowables):
    df_usd = load_csv_by_id(93, DATA_DIR)
    df_tnx = load_csv_by_id(94, DATA_DIR)

    if df_usd.empty:
        flowables.append(Paragraph("USD Correlations (missing qry_graph_data_93.csv)", NOTE))
        return
    if df_tnx.empty:
        flowables.append(Paragraph("Rates Correlations (missing qry_graph_data_94.csv)", NOTE))
        return

    def corr_table(df, title, bottom_docx, note_text):
        flowables.append(Paragraph(title, H2))

        cols = [c for c in ["Metric", "15D", "30D", "90D"] if c in df.columns]
        d = df[cols].copy()
        for c in ["15D", "30D", "90D"]:
            if c in d.columns:
                d[c] = d[c].map(lambda v: fmt_num(v, 2))

        data_rows = [cols] + d.values.tolist()

        w_metric = 3.6 * inch
        w_num = 1.1 * inch
        col_widths = [w_metric] + [w_num]*(len(cols)-1)

        t = _build_table(data_rows, col_widths)
        flowables.append(t)

        bl = _read_plain_text_any(DATA_DIR / bottom_docx)
        if bl:
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(pdf_safe_text(clean_text(bl)).replace("\n", "<br/>"), P))

        flowables.append(Spacer(1, 4))
        flowables.append(Paragraph(note_text, NOTE))
        flowables.append(Spacer(1, 10))

    corr_table(
        df_usd,
        "USD Correlations",
        "usd_correlation_bottom_line.docx",
        "Note: USD correlations use the U.S. Dollar Index (DXY), a trade-weighted FX index. 15D/30D/90D are trading-day windows. "
        "Correlation ranges from -1 to +1. Negative = tends to move opposite. Positive = tends to move together."
    )

    flowables.append(PageBreak())

    corr_table(
        df_tnx,
        "Rates Correlations",
        "tnx_correlation_bottom_line.docx",
        "Note: Rate correlations use the 10-Year U.S. Treasury yield (TNX) as the rates proxy. 15D/30D/90D are trading-day windows. "
        "Correlation ranges from -1 to +1. Negative = tends to move opposite. Positive = tends to move together."
    )

def _section_macro_table(flowables, tf_key: str, title: str, csv_id: int, bottom_docx: str):
    cfg = TIMEFRAMES[tf_key]
    cols = cfg["cols"]

    df = load_csv_by_id(csv_id, DATA_DIR)
    req = ["Ticker_name", "Ticker", "Close", cols["ret"], cols["pr_low"], cols["pr_high"], cols["rr"], "model_score", "model_score_delta"]
    if df.empty or not all(c in df.columns for c in req):
        flowables.append(Paragraph(f"{title} (missing or incomplete qry_graph_data_{csv_id}.csv)", NOTE))
        flowables.append(Spacer(1, 8))
        return

    #flowables.append(Paragraph(title, H2))

    d = df.copy()

    out = pd.DataFrame({
        "Name": d["Ticker_name"],
        "Ticker": d["Ticker"],
        "Close": d["Close"].map(lambda v: fmt_num(v, 2)),
        "% Change": d[cols["ret"]].map(lambda v: fmt_pct(v, 2)),
        "Probable Low": d[cols["pr_low"]].map(lambda v: fmt_num(v, 2)),
        "Probable High": d[cols["pr_high"]].map(lambda v: fmt_num(v, 2)),
        "Risk / Reward": d[cols["rr"]].map(lambda v: fmt_num(v, 1)),
        "MM Score": d["model_score"].map(lambda v: fmt_int(v)),
        "Δ MM Score": d["model_score_delta"].map(lambda v: fmt_int(v)),
    })

    header = [
        th("Name"),
        th("Ticker"),
        th("Close"),
        th("% Change"),
        th("Probable<br/>Low"),
        th("Probable<br/>High"),
        th("Risk /<br/>Reward"),
        th("MM<br/>Score"),
        th("Δ MM<br/>Score"),
    ]
    data_rows = [header] + out.values.tolist()

    col_widths = [
        2.35*inch,
        0.70*inch,
        0.75*inch,
        0.80*inch,
        0.85*inch,
        0.85*inch,
        0.75*inch,
        0.70*inch,
        0.85*inch,
    ]

    rr_col = 6
    mm_col = 7

    t = _build_table(
        data_rows=data_rows,
        col_widths=col_widths,
        shade_rr=True, shade_mm=True,
        rr_col=rr_col, mm_col=mm_col
    )
    block = []
    block.append(Paragraph(title, H2))
    block.append(t)
    flowables.append(KeepTogether(block))

    bl = _read_plain_text_any(DATA_DIR / bottom_docx) if bottom_docx else ""
    if bl:
        flowables.append(Spacer(1, 6))
        flowables.append(Paragraph(clean_text(bl).replace("\n", "<br/>"), P))

    flowables.append(Spacer(1, 4))
    flowables.append(Paragraph(
        "Note: MM Score → Rules-based contrarian score designed to avoid chasing stretch, identify crowding, and size conviction sensibly.",
        NOTE
    ))
    flowables.append(Spacer(1, 10))

import numpy as np
from reportlab.lib import colors

def _robust_vmax(series, q=0.98, floor=1.0, step=1.0):
    s = pd.to_numeric(pd.Series(series), errors="coerce").abs().dropna()
    if s.empty:
        return float(floor)
    vmax = float(np.quantile(s, q))
    return max(float(floor), float(np.ceil(vmax / step) * step))

def _blend_with_white(rgb_255, alpha):
    """
    Simulate CSS rgba(rgb, alpha) on white background.
    rgb_255: (R,G,B) 0-255
    alpha: 0..1
    """
    a = float(max(0.0, min(alpha, 1.0)))
    r, g, b = [c / 255.0 for c in rgb_255]
    # white is (1,1,1)
    rr = 1.0 * (1.0 - a) + r * a
    gg = 1.0 * (1.0 - a) + g * a
    bb = 1.0 * (1.0 - a) + b * a
    return colors.Color(rr, gg, bb)

def _sr_rank_bg(score, cap=100.0):
    """
    Match portal Rank shading:
    - >=70 green (stronger as approaches 100)
    - <=30 red (stronger as approaches 0)
    - else neutral gray tint
    """
    if score is None or pd.isna(score):
        return None

    s = float(np.clip(float(score), 0.0, float(cap)))

    if s >= 70.0:
        rel = (s - 70.0) / 30.0
        alpha = 0.05 + 0.14 * max(0.0, min(rel, 1.0))
        return _blend_with_white((16, 185, 129), alpha)   # green
    elif s <= 30.0:
        rel = (30.0 - s) / 30.0
        alpha = 0.05 + 0.14 * max(0.0, min(rel, 1.0))
        return _blend_with_white((239, 68, 68), alpha)    # red
    else:
        return _blend_with_white((156, 163, 175), 0.08)   # neutral gray

def _sr_delta_bg(val, vmax):
    """
    Match portal delta shading:
    alpha = 0.05 + 0.14 * min(abs(val)/vmax, 1)
    green if val>0, red if val<0, transparent if 0
    """
    if val is None or pd.isna(val) or vmax is None or float(vmax) <= 0:
        return None

    v = float(val)
    s = min(abs(v) / float(vmax), 1.0)
    alpha = 0.05 + 0.14 * s

    if v > 0:
        return _blend_with_white((16, 185, 129), alpha)
    elif v < 0:
        return _blend_with_white((239, 68, 68), alpha)
    else:
        return None

# -------------------------
# !!! DO NOT CHANGE OUTPUT LOGIC !!!
# Morning Compass PDF builder stays intact; we wrap it as a module.
# -------------------------
def build_title_page_pdf(trading_session: str, data_asof: str) -> bytes:
    """
    Creates a simple title page:
    - centered logo
    - centered title: "Markmentum Research Pack"
    - date line
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch
    )

    flow = []

    # Spacer down a bit so it feels like a cover
    flow.append(Spacer(1, 0.6 * inch))

    if LOGO_PATH.exists():
        img = RLImage(str(LOGO_PATH))
        img.drawHeight = 0.9 * inch
        img.drawWidth = 7.2 * inch
        img.hAlign = "CENTER"
        flow.append(img)

    flow.append(Spacer(1, 0.5 * inch))
    flow.append(Spacer(1, 0.5 * inch))

    # Big centered title
    cover_title = Paragraph("Research Pack", ParagraphStyle(
        "COVER_TITLE",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=22,
        spaceAfter=12
    ))
    flow.append(cover_title)

    flow.append(Spacer(1, 0.5 * inch))
    
    if trading_session:
        flow.append(Paragraph(
            f"<b>Trading Session:</b> {trading_session}",
            ParagraphStyle(
                "COVER_SESSION",
                parent=styles["BodyText"],
                alignment=TA_CENTER,
                fontSize=14,
                spaceAfter=6
            )
        ))
    
    flow.append(Spacer(1, 0.5 * inch))

    data_asof = get_last_trading_date()

    if data_asof:
        flow.append(Paragraph(
            f"Data as of: {data_asof}",
            ParagraphStyle(
                "COVER_ASOF",
                parent=styles["BodyText"],
                alignment=TA_CENTER,
                fontSize=11,
                textColor=colors.HexColor("#666666")
            )
        ))

    # IMPORTANT: no disclaimer/footer on title page
    doc.build(flow)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_morning_compass_pdf(
    include_correlations: bool,
    include_macro: bool,
    include_pct: bool,
    include_mm: bool,
    include_delta: bool,
    tf_key: str
) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.45*inch, rightMargin=0.45*inch,
        topMargin=0.50*inch, bottomMargin=0.95*inch
    )

    flow = []

    # Logo + title only for Daily (matches your current behavior)
    if tf_key == "Daily":
        #if LOGO_PATH.exists():
        #    img = RLImage(str(LOGO_PATH))
        #    img.drawHeight = 0.55 * inch
        #    img.drawWidth = 4.8 * inch
        #    img.hAlign = "CENTER"
        #    flow.append(img)
        #    flow.append(Spacer(1, 8))
        #else:
        #    flow.append(Paragraph("Markmentum Research", H1))

        asof = _asof_date_from_main(tf_key)
        title = f"Morning Compass" if asof else "Morning Compass"
        flow.append(Paragraph(title, H1))
        #flow.append(Spacer(1, 3))


    cfg = TIMEFRAMES[tf_key]

    if include_macro:
        _section_macro_table(
            flowables=flow,
            tf_key=tf_key,
            title=cfg["title_macro"],
            csv_id=cfg["ids"]["main"],
            bottom_docx=cfg["docx_macro"]
        )
        if not (tf_key == "Daily" and include_correlations):
            flow.append(PageBreak())

    # Correlations (Daily only)
    if include_correlations and tf_key == "Daily":
        _section_correlations(flow)
        flow.append(PageBreak())


    if include_pct:
        _section_macro_table(
            flowables=flow,
            tf_key=tf_key,
            title=cfg["title_leaders"],
            csv_id=cfg["ids"]["leaders"],
            bottom_docx=""
        )
        flow.append(PageBreak())

    if include_mm:
        _section_macro_table(
            flowables=flow,
            tf_key=tf_key,
            title=cfg["title_mm"],
            csv_id=cfg["ids"]["mm"],
            bottom_docx=""
        )
        flow.append(PageBreak())

    if include_delta:
        _section_macro_table(
            flowables=flow,
            tf_key=tf_key,
            title=cfg["title_delta"],
            csv_id=cfg["ids"]["delta"],
            bottom_docx=""
        )
        flow.append(PageBreak())

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_market_overview_pdf(
    tf_key: str,
    include_top_cards: bool = True,
    include_score_change_cards: bool = True,
    include_daily_extras: bool = True,      # highest/lowest/hist + opp density (Daily only)
    include_market_read: bool = True
) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.45*inch, rightMargin=0.45*inch,
        topMargin=0.50*inch, bottomMargin=0.95*inch
    )

    flow: list = []

    dfs = mo_load_for_timeframe(tf_key)
    asof = _mo_asof_from_df(dfs[0])

    # Header
    title = f"{tf_key} Market Overview" 
    flow.append(Paragraph(clean_text(title), H1))
    flow.append(Spacer(1, 6))

    def _simple_card(title_txt: str, df: pd.DataFrame, value_header: str = "Value"):
        if df.empty:
            flow.append(Paragraph(f"{title_txt} (no data)", NOTE))
            flow.append(Spacer(1, 8))
            return

        # Try to map columns robustly (tolerant like your page)
        cols_lower = {str(c).lower(): c for c in df.columns}
        tcol = cols_lower.get("ticker", None)
        ncol = cols_lower.get("ticker_name", None) or cols_lower.get("company", None)
        ccol = cols_lower.get("category", None) or cols_lower.get("exposure", None)

        # pick the "value" column: last numeric-ish column that isn't the known text columns
        known = {tcol, ncol, ccol}
        value_col = None
        for c in df.columns[::-1]:
            if c in known:
                continue
            value_col = c
            break

        # Build output with 4 columns max (Name/Ticker/Category/Value)
        use_cols = []
        if ncol: use_cols.append(ncol)
        if tcol: use_cols.append(tcol)
        if ccol: use_cols.append(ccol)
        if value_col: use_cols.append(value_col)

        d = df[use_cols].copy() if use_cols else df.copy()

        # rename
        rename_map = {}
        if ncol: rename_map[ncol] = "Name"
        if tcol: rename_map[tcol] = "Ticker"
        if ccol: rename_map[ccol] = "Category"
        if value_col: rename_map[value_col] = value_header
        d = d.rename(columns=rename_map)

        # formatting: if looks like percent (0.xx), show %; else int
        if value_header in d.columns:
            def _fmt_val(v):
                try:
                    fv = float(v)
                except Exception:
                    return str(v) if v is not None else ""

                # Formatting by type
                if value_header.lower() == "percent":
                    return fmt_pct(fv, 2)
                if value_header.lower() == "shares":
                    return fmt_num(fv, 2)  # you can switch to fmt_int if you want no decimals
                if value_header.lower() in ("change", "score"):
                    return fmt_int(fv)
                return fmt_num(fv, 2)

            d[value_header] = d[value_header].map(_fmt_val)

        header = [th(c) for c in d.columns.tolist()]
        data_rows = [header] + d.values.tolist()

        # widths
        widths = []
        for col in d.columns.tolist():
            if col == "Name":
                widths.append(2.8*inch)
            elif col == "Ticker":
                widths.append(0.8*inch)
            elif col == "Category":
                widths.append(1.7*inch)
            else:
                widths.append(1.0*inch)

        flow.append(Paragraph(clean_text(title_txt), H2))
        flow.append(_build_table(data_rows, widths))
        flow.append(Spacer(1, 10))

    # -------------------------
    # Row 1: gainers/decliners/most active
    # -------------------------
    if include_top_cards:
        _simple_card(f"{tf_key} – Top Ten Percentage Gainers", dfs[0], value_header="Percent")
        flow.append(PageBreak())
        _simple_card(f"{tf_key} – Top Ten Percentage Decliners", dfs[1], value_header="Percent")
        flow.append(PageBreak())
        _simple_card(f"{tf_key} – Most Active (Shares)", dfs[2], value_header="Shares")
        flow.append(PageBreak())

    # -------------------------
    # Row 2: Score gainers/decliners + score change distribution
    # -------------------------
    if include_score_change_cards:
        _simple_card(f"{tf_key} – Top Ten Markmentum Score Gainers", dfs[3], value_header="Change")
        _simple_card(f"{tf_key} – Top Ten Markmentum Score Decliners", dfs[4], value_header="Change")

        # Dist table (Score Bin / Ticker Count)
        df_dist = dfs[5].copy()
        flow.append(Paragraph(clean_text(f"{tf_key} – Markmentum Score Change Distribution"), H2))
        if df_dist.empty:
            flow.append(Paragraph("No data.", NOTE))
        else:
            # normalize columns
            cols_lower = {str(c).lower(): c for c in df_dist.columns}
            score_bin_col = cols_lower.get("score_bin") or cols_lower.get("score bin")
            count_col = cols_lower.get("tickercount") or cols_lower.get("ticker_count") or cols_lower.get("ticker count")
            if score_bin_col and count_col:
                d = df_dist[[score_bin_col, count_col]].copy()
                d.columns = ["Score Bin", "Ticker Count"]
                data_rows = [[th("Score Bin"), th("Ticker Count")]] + d.values.tolist()
                flow.append(_build_table(data_rows, [2.2*inch, 1.4*inch]))
            else:
                flow.append(Paragraph("Missing Score Bin / Count columns.", NOTE))
        flow.append(Spacer(1, 10))
        flow.append(PageBreak())

    # -------------------------
    # Daily extras: highest/lowest/hist + opportunity density
    # -------------------------
    if tf_key == "Daily" and include_daily_extras:
        _simple_card("Daily – Highest Markmentum Score", dfs[6], value_header="Score")
        _simple_card("Daily – Lowest Markmentum Score", dfs[7], value_header="Score")

        # Histogram table
        df_hist = dfs[8].copy()
        flow.append(Paragraph("Daily – Markmentum Score Histogram", H2))
        if df_hist.empty:
            flow.append(Paragraph("No data.", NOTE))
        else:
            cols_lower = {str(c).lower(): c for c in df_hist.columns}
            score_bin_col = cols_lower.get("score_bin") or cols_lower.get("score bin")
            count_col = cols_lower.get("tickercount") or cols_lower.get("ticker_count") or cols_lower.get("ticker count")

            if score_bin_col and count_col:
                mapping = {
                    "Below -100": "Strong Sell",
                    "-100 to -26": "Sell",
                    "-25 to 25": "Neutral",
                    "26 to 100": "Buy",
                    "Above 100": "Strong Buy",
                }
                df_hist["Classification"] = df_hist[score_bin_col].map(mapping)
                d = df_hist[["Classification", score_bin_col, count_col]].copy()
                d.columns = ["Classification", "Score Bin", "Ticker Count"]
                data_rows = [[th("Classification"), th("Score Bin"), th("Ticker Count")]] + d.values.tolist()
                flow.append(_build_table(data_rows, [2.2*inch, 1.6*inch, 1.4*inch]))
            else:
                flow.append(Paragraph("Missing histogram columns.", NOTE))

        flow.append(Spacer(1, 10))
        flow.append(PageBreak())

        # Opportunity Density (qry_graph_data_92.csv)
        df_od = load_csv_by_id(MO_OPPORTUNITY_DENSITY_CSV_ID, DATA_DIR).copy()
        flow.append(Paragraph("Opportunity Density", H2))
        if df_od.empty:
            flow.append(Paragraph("No data.", NOTE))
        else:
            # format percent columns if present
            for col in ["Buy %", "Neutral %", "Sell %"]:
                if col in df_od.columns:
                    df_od[col] = df_od[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
            header = [th(c) for c in df_od.columns.tolist()]
            data_rows = [header] + df_od.values.tolist()

            # widths: first column wide
            widths = [2.3*inch] + [0.70*inch]*(len(df_od.columns)-1)
            flow.append(_build_table(data_rows, widths))
            flow.append(Spacer(1, 6))
            flow.append(Paragraph(
                "Note: Buy classifications require Risk/Reward ≥ 3 and MM Score > 25. "
                "Sell classifications require Risk/Reward ≤ −3 and MM Score < −25.",
                NOTE
            ))

        flow.append(Spacer(1, 10))
        flow.append(PageBreak())

    # -------------------------
    # Market Read (docx)
    # -------------------------
    if include_market_read:
        docx_name = MO_MARKET_READ_DOCX.get(tf_key, "")
        mr_text = _read_plain_text_any(DATA_DIR / docx_name) if docx_name else ""

        if not mr_text:
            flow.append(Paragraph(f"Market Read missing or empty: {docx_name}", NOTE))
        else:
            mr_items = _market_read_to_flowables(mr_text)

            mr_box = KeepInFrame(
                maxWidth=doc.width,
                maxHeight=doc.height,
                content=mr_items,
                mode="shrink",
                hAlign="LEFT",
                vAlign="TOP",
            )
            flow.append(mr_box)

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# =========================================================
# PERFORMANCE HEATMAP (PDF)
# =========================================================

PH_CSV = DATA_DIR / "ticker_data.csv"   # same source as the portal page

PH_COL_MAP = {
    "Daily": "day_pct_change",
    "WTD": "week_pct_change",
    "MTD": "month_pct_change",
    "QTD": "quarter_pct_change",
}

PH_MACRO_LIST = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

PH_CATEGORY_ORDER = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities","Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]

def _ph_load_latest() -> tuple[pd.DataFrame, str]:
    """Loads ticker_data.csv and returns latest row per ticker + as-of date string."""
    if not PH_CSV.exists():
        return pd.DataFrame(), ""

    df = pd.read_csv(PH_CSV)
    if df.empty or "Date" not in df.columns or "Ticker" not in df.columns:
        return pd.DataFrame(), ""

    df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values(["Ticker", "_dt"], ascending=[True, False]).drop_duplicates("Ticker", keep="first")

    # as-of date (max date present)
    asof = df["_dt"].max()
    asof_str = asof.strftime("%-m/%-d/%Y") if pd.notna(asof) else ""
    return df, asof_str


def _ph_interp_color(val: float, vmax: float):
    """
    Use Sharpe Rank delta shading philosophy for Performance Heatmap:
    alpha = 0.05 + 0.14 * min(abs(val)/vmax, 1)
    green if val>0, red if val<0, white if 0/NA.
    """
    from reportlab.lib import colors

    c = _sr_delta_bg(pd.to_numeric(val, errors="coerce"), vmax)
    return c if c is not None else colors.white

def _ph_fmt_pct(x) -> str:
    """Format values like the portal: 2 decimals + %.
    Handles either fractions (0.0043) or already-percent values (0.43).
    """
    try:
        v = float(x)
    except Exception:
        return ""

    # If it's likely a fraction (like 0.0043), convert to percent
    if abs(v) <= 2.0:
        v = v * 100.0

    return f"{v:.2f}%"

def _ph_make_colored_table(df: pd.DataFrame, vmax: dict[str, float], title: str) -> list:
    """ReportLab flowables for a titled % table with per-column shading."""
    flow = []
    #flow.append(Paragraph(f"<b>{title}</b>", STYLES["Heading3"]))
    flow.append(Paragraph(clean_text(title), H2))
    flow.append(Spacer(1, 6))

    # build table data
    cols = list(df.columns)
    data = [cols]
    for r in range(len(df)):
        row = []
        for c in cols:
            v = df.loc[df.index[r], c]
            if c in ("Δ Daily", "Δ WTD", "Δ MTD", "Δ QTD"):
                row.append(_ph_fmt_pct(v))
            else:
                row.append(v)
        data.append(row)

    # base table
    t = Table(data, hAlign="CENTER")

    # table styling
    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # apply per-column shading for % columns
    for j, c in enumerate(cols):
        if c in ("Δ Daily", "Δ WTD", "Δ MTD", "Δ QTD"):
            col_vmax = vmax.get(c.replace("Δ ", ""), 0.0) or 0.0
            for i in range(1, len(data)):
                raw = df.iloc[i-1, j]
                ts.add("BACKGROUND", (j, i), (j, i), _ph_interp_color(raw, col_vmax))

    t.setStyle(ts)
    flow.append(t)
    flow.append(Spacer(1, 14))
    return flow


def build_performance_heatmap_pdf(
    include_macro_orientation: bool = True,
    include_category_averages: bool = True,
    include_category_heatmap: bool = False,
) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.60*inch, rightMargin=0.60*inch,
        topMargin=0.60*inch, bottomMargin=0.85*inch
    )

    perf, asof_str = _ph_load_latest()
    flow = []

    # Header
    flow.append(Paragraph("<b>Performance Heatmap</b>", STYLES["Title"]))
    #if asof_str:
    #    flow.append(Paragraph(asof_str, STYLES["Normal"]))
    flow.append(Spacer(1, 10))

    if perf.empty:
        flow.append(Paragraph("No performance data available (ticker_data.csv missing or empty).", STYLES["Normal"]))
        doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
        return buffer.getvalue()

    # ---- Macro Orientation (subset of tickers) ----
    if include_macro_orientation:
        m = perf[perf["Ticker"].isin(PH_MACRO_LIST)].copy()
        m["__ord__"] = m["Ticker"].map({t:i for i, t in enumerate(PH_MACRO_LIST)})
        m = m.sort_values("__ord__", kind="stable")

        # build table frame
        def _col(tf): return PH_COL_MAP[tf]
        macro_df = pd.DataFrame({
            "Name": m.get("Ticker_name", m["Ticker"]),
            "Ticker": m["Ticker"],
            "Δ Daily": m[_col("Daily")],
            "Δ WTD":   m[_col("WTD")],
            "Δ MTD":   m[_col("MTD")],
            "Δ QTD":   m[_col("QTD")],
        })


        # numeric vmax per column (independent scaling)
        vmax = {
            "Daily": float(m[_col("Daily")].abs().max(skipna=True) or 0.0),
            "WTD":   float(m[_col("WTD")].abs().max(skipna=True) or 0.0),
            "MTD":   float(m[_col("MTD")].abs().max(skipna=True) or 0.0),
            "QTD":   float(m[_col("QTD")].abs().max(skipna=True) or 0.0),
        }

        flow.extend(_ph_make_colored_table(macro_df, vmax, "Macro Orientation"))

    # ---- Category Averages ----
    if include_category_averages:
        if "Category" in perf.columns:
            g = (
                perf.groupby("Category", dropna=False)[
                    [PH_COL_MAP["Daily"], PH_COL_MAP["WTD"], PH_COL_MAP["MTD"], PH_COL_MAP["QTD"]]
                ]
                .mean(numeric_only=True)
                .reset_index()
            )
            g = g.rename(columns={
                PH_COL_MAP["Daily"]: "Daily",
                PH_COL_MAP["WTD"]: "WTD",
                PH_COL_MAP["MTD"]: "MTD",
                PH_COL_MAP["QTD"]: "QTD",
            })

            order_map = {name: i for i, name in enumerate(PH_CATEGORY_ORDER)}
            g["__ord__"] = g["Category"].map(order_map)
            g = g.sort_values(["__ord__", "Category"], kind="stable").drop(columns="__ord__")

            cat_df = pd.DataFrame({
                "Name": g["Category"],
                "Δ Daily": g["Daily"],
                "Δ WTD": g["WTD"],
                "Δ MTD": g["MTD"],
                "Δ QTD": g["QTD"],
            })

            vmaxC = {
                "Daily": float(pd.to_numeric(cat_df["Δ Daily"], errors="coerce").abs().max(skipna=True) or 0.0),
                "WTD":   float(pd.to_numeric(cat_df["Δ WTD"],   errors="coerce").abs().max(skipna=True) or 0.0),
                "MTD":   float(pd.to_numeric(cat_df["Δ MTD"],   errors="coerce").abs().max(skipna=True) or 0.0),
                "QTD":   float(pd.to_numeric(cat_df["Δ QTD"],   errors="coerce").abs().max(skipna=True) or 0.0),
            }

            flow.append(PageBreak())

            flow.extend(_ph_make_colored_table(cat_df, vmaxC, "Category Averages"))

            # Optional: a second page “heatmap” (matrix) — default OFF to control page count
            if include_category_heatmap:
                flow.append(PageBreak())
                flow.append(Paragraph("<b>Category Heatmap – Avg % Change</b>", STYLES["Heading2"]))
                flow.append(Spacer(1, 8))

                # Build matrix table: rows=Category, cols=Daily/WTD/MTD/QTD
                matrix = g[["Category","Daily","WTD","MTD","QTD"]].copy()
                data = [["Category","Daily","WTD","MTD","QTD"]] + matrix.values.tolist()

                t = Table(data, hAlign="CENTER")
                ts = TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ])

                # column shading
                for col_idx, col_name in enumerate(["Daily","WTD","MTD","QTD"], start=1):
                    col_vmax = vmaxC.get(col_name, 0.0) or 0.0
                    for row in range(1, len(data)):
                        v = matrix.iloc[row-1][col_name]
                        ts.add("BACKGROUND", (col_idx, row), (col_idx, row), _ph_interp_color(v, col_vmax))

                t.setStyle(ts)
                flow.append(t)

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()

# =========================================================
# SHARPE RANK HEATMAP (PDF)
#   - Macro Orientation + Category Averages ONLY
#   - Uses existing global styles + same red/green delta shading logic
# =========================================================

SR_CSV_BASE = DATA_DIR / "qry_graph_data_48.csv"  # Sharpe_Rank + daily change (and/or previous)
SR_CSV_WTD  = DATA_DIR / "qry_graph_data_49.csv"  # Sharpe_Rank_wtd_change
SR_CSV_MTD  = DATA_DIR / "qry_graph_data_50.csv"  # Sharpe_Rank_mtd_change
SR_CSV_QTD  = DATA_DIR / "qry_graph_data_51.csv"  # Sharpe_Rank_qtd_change

# Reuse the same ordering you use on the portal page (05_Sharpe_Rank_Heatmap.py)
SR_MACRO_LIST = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

SR_CATEGORY_ORDER = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities","Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]

def _sr_load_latest() -> tuple[pd.DataFrame, str]:
    """
    Build a single Sharpe Rank frame similar to the portal page:
      - Latest row per ticker
      - Columns: Name, Ticker, Category, Rank, Daily, WTD, MTD, QTD
    """
    if not SR_CSV_BASE.exists():
        return pd.DataFrame(), ""

    base = pd.read_csv(SR_CSV_BASE)
    if base.empty or "Ticker" not in base.columns:
        return pd.DataFrame(), ""

    # as-of date (best effort)
    asof_str = ""
    if "Date" in base.columns:
        dtmax = pd.to_datetime(base["Date"], errors="coerce").max()
        if pd.notna(dtmax):
            asof_str = f"{dtmax.month}/{dtmax.day}/{dtmax.year}"

    # latest per ticker
    if "Date" in base.columns:
        base["_dt"] = pd.to_datetime(base["Date"], errors="coerce")
        base = (
            base.sort_values(["Ticker", "_dt"], ascending=[True, False])
                .drop_duplicates(subset=["Ticker"], keep="first")
        )

    # ensure numerics
    for c in ["Sharpe_Rank", "previous_Sharpe_Rank", "Sharpe_Rank_daily_change"]:
        if c in base.columns:
            base[c] = pd.to_numeric(base[c], errors="coerce")

    # compute daily change if missing
    if ("Sharpe_Rank_daily_change" not in base.columns) or base["Sharpe_Rank_daily_change"].isna().all():
        if "Sharpe_Rank" in base.columns and "previous_Sharpe_Rank" in base.columns:
            base["Sharpe_Rank_daily_change"] = base["Sharpe_Rank"] - base["previous_Sharpe_Rank"]

    # helper to load a delta file, latest-per-ticker
    def _load_delta(path: Path, colname: str) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=["Ticker", colname])

        d = pd.read_csv(path)
        if d.empty or "Ticker" not in d.columns or colname not in d.columns:
            return pd.DataFrame(columns=["Ticker", colname])

        if "Date" in d.columns:
            d["_dt"] = pd.to_datetime(d["Date"], errors="coerce")
            d = (
                d.sort_values(["Ticker", "_dt"], ascending=[True, False])
                 .drop_duplicates(subset=["Ticker"], keep="first")
            )

        d[colname] = pd.to_numeric(d[colname], errors="coerce")
        return d[["Ticker", colname]].drop_duplicates("Ticker", keep="first")

    wtd = _load_delta(SR_CSV_WTD, "Sharpe_Rank_wtd_change")
    mtd = _load_delta(SR_CSV_MTD, "Sharpe_Rank_mtd_change")
    qtd = _load_delta(SR_CSV_QTD, "Sharpe_Rank_qtd_change")

    df = base.copy()
    for add in (wtd, mtd, qtd):
        df = df.merge(add, on="Ticker", how="left")

    # normalize schema to match PDF table labels
    df = df.rename(columns={
        "Ticker_name": "Name",
        "Sharpe_Rank": "Rank",
        "Sharpe_Rank_daily_change": "Daily",
        "Sharpe_Rank_wtd_change":   "WTD",
        "Sharpe_Rank_mtd_change":   "MTD",
        "Sharpe_Rank_qtd_change":   "QTD",
    })

    # keep only the fields we need (Category may be absent in some bad exports)
    keep = [c for c in ["Name","Ticker","Category","Rank","Daily","WTD","MTD","QTD"] if c in df.columns]
    df = df[keep].copy()

    # enforce numeric on the number columns if present
    for c in ["Rank","Daily","WTD","MTD","QTD"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df, asof_str


def _sr_rank_bg_color(rank_val: float) -> colors.Color:
    """
    Rank tint: High=green, Neutral=gray, Low=red (same concept as portal page).
    """
    try:
        if rank_val is None or pd.isna(rank_val):
            return colors.white
        v = float(rank_val)
    except Exception:
        return colors.white

    # simple bands: 0-30 low, 30-70 neutral, 70-100 high
    if v >= 70:
        return colors.Color(0.90, 0.98, 0.95)  # light green
    if v <= 30:
        return colors.Color(0.99, 0.92, 0.92)  # light red
    return colors.Color(0.95, 0.95, 0.95)      # neutral gray


def _sr_fmt_int(x) -> str:
    try:
        if x is None or pd.isna(x):
            return ""
        v = int(round(float(x)))
        # avoid "-0"
        return "0" if v == 0 else str(v)
    except Exception:
        return ""


def _sr_vmax(series: pd.Series, floor: float = 1.0) -> float:
    s = pd.to_numeric(series, errors="coerce").abs().dropna()
    if s.empty:
        return floor
    return max(floor, float(s.max()))


def _sr_make_colored_table(df: pd.DataFrame, vmax_map: dict[str, float], include_ticker: bool) -> Table:
    """
    Match Performance Heatmap look:
      - centered table (hAlign="CENTER")
      - same header style/padding/grid weights as _ph_make_colored_table
      - Rank column uses rank shading
      - change columns use _ph_interp_color with per-column vmax
    """
    cols = df.columns.tolist()

    # display headers (PDF only)
    display_headers = []
    for c in cols:
        if c == "Daily":
            display_headers.append("Δ Daily")
        elif c == "WTD":
            display_headers.append("Δ WTD")
        elif c == "MTD":
            display_headers.append("Δ MTD")
        elif c == "QTD":
            display_headers.append("Δ QTD")
        else:
            display_headers.append(c)

    # build table data (header row as strings, like Performance)
    data = [display_headers]
    for _, r in df.iterrows():
        row = []
        for c in cols:
            if c in ("Rank", "Daily", "WTD", "MTD", "QTD"):
                row.append(_sr_fmt_int(r.get(c)))
            else:
                row.append("" if pd.isna(r.get(c)) else str(r.get(c)))
        data.append(row)

    # IMPORTANT: match Performance alignment behavior
    t = Table(data, hAlign="CENTER")

    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),      # Name left
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),   # rest centered like Performance
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # Rank shading
    if "Rank" in cols:
        j = cols.index("Rank")
        for i in range(1, len(data)):
            rv = pd.to_numeric(df.iloc[i-1].get("Rank"), errors="coerce")
            ts.add("BACKGROUND", (j, i), (j, i), _sr_rank_bg(rv))

    # Change shading (independent per timeframe)
    for c in ("Daily", "WTD", "MTD", "QTD"):
        if c not in cols:
            continue
        j = cols.index(c)
        col_vmax = vmax_map.get(c, 1.0) or 1.0
        for i in range(1, len(data)):
            v = pd.to_numeric(df.iloc[i-1].get(c), errors="coerce")
            ts.add("BACKGROUND", (j, i), (j, i), _sr_delta_bg(v, col_vmax))

    t.setStyle(ts)
    return t


def build_sharpe_rank_heatmap_pdf(
    include_macro_orientation: bool = True,
    include_category_averages: bool = True,
) -> bytes:
    ranks, asof_str = _sr_load_latest()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=36, rightMargin=36,
        topMargin=36, bottomMargin=40
    )

    flow: list = []
    flow.append(Paragraph("<b>Sharpe Rank Heatmap</b>", STYLES["Title"]))
    # If you later want the date line like the portal, uncomment:
    # if asof_str:
    #     flow.append(Paragraph(asof_str, STYLES["Normal"]))
    flow.append(Spacer(1, 10))

    if ranks.empty:
        flow.append(Paragraph("No sharpe rank data available (qry_graph_data_48–51.csv missing or empty).", STYLES["Normal"]))
        doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    # -------------------------
    # Macro Orientation
    # -------------------------
    if include_macro_orientation:
        flow.append(Paragraph("Macro Orientation", H2))
        flow.append(Spacer(1, 6))

        m = ranks[ranks.get("Ticker").isin(SR_MACRO_LIST) if "Ticker" in ranks.columns else False].copy()
        if not m.empty and "Ticker" in m.columns:
            order = {t: i for i, t in enumerate(SR_MACRO_LIST)}
            m["__ord__"] = m["Ticker"].map(order)
            m = m.sort_values(["__ord__"], kind="stable")

        # columns for the PDF table
        want = ["Name", "Ticker", "Rank", "Daily", "WTD", "MTD", "QTD"]
        m = m[[c for c in want if c in m.columns]].copy()

        if m.empty:
            flow.append(Paragraph("No macro orientation rows found.", NOTE))
        else:
            vmax = {c: _robust_vmax(m[c], q=0.98, floor=1.0, step=1.0)
                for c in ["Daily", "WTD", "MTD", "QTD"] if c in m.columns}
            flow.append(_sr_make_colored_table(m, vmax, include_ticker=("Ticker" in m.columns)))

        flow.append(Spacer(1, 12))

    # -------------------------
    # Category Averages
    # -------------------------
    if include_category_averages and ("Category" in ranks.columns):
        flow.append(PageBreak())
        flow.append(Paragraph("Category Averages", H2))
        flow.append(Spacer(1, 6))

        g = (
            ranks.dropna(subset=["Category"])
                 .groupby("Category", as_index=False)
                 .agg(
                     Rank=("Rank", "mean"),
                     Daily=("Daily", "mean"),
                     WTD=("WTD", "mean"),
                     MTD=("MTD", "mean"),
                     QTD=("QTD", "mean"),
                 )
        )

        # enforce preferred order
        order_map = {name: i for i, name in enumerate(SR_CATEGORY_ORDER)}
        g["__ord__"] = g["Category"].map(order_map).fillna(10_000).astype(int)
        g = g.sort_values(["__ord__", "Category"], kind="stable")

        cat = g.rename(columns={"Category": "Name"})[["Name", "Rank", "Daily", "WTD", "MTD", "QTD"]].copy()

        vmax = {c: _robust_vmax(cat[c], q=0.98, floor=1.0, step=1.0)
            for c in ["Daily", "WTD", "MTD", "QTD"] if c in cat.columns}
        flow.append(_sr_make_colored_table(cat, vmax, include_ticker=False))

    elif include_category_averages:
        # Category column missing in export
        flow.append(PageBreak())
        flow.append(Paragraph("Category Averages", H2))
        flow.append(Spacer(1, 6))
        flow.append(Paragraph("Category data not available (missing 'Category' column).", NOTE))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# =========================================================
# MARKMENTUM HEATMAP (PDF)
#   - Macro Orientation + Category Averages ONLY
#   - Uses Sharpe-style blended shading for deltas
#   - Uses existing _mm_bg_color for Score shading (neutral ±25 band)
# =========================================================

MM_CSV_BASE = DATA_DIR / "model_score_day_change.csv"
MM_CSV_WTD  = DATA_DIR / "model_score_wtd_change.csv"
MM_CSV_MTD  = DATA_DIR / "model_score_mtd_change.csv"
MM_CSV_QTD  = DATA_DIR / "model_score_qtd_change.csv"

# Reuse the same macro list + category order already used across the portal
MM_MACRO_LIST = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

MM_CATEGORY_ORDER = [
    "Sector & Style ETFs","Indices","Futures","Currencies","Commodities","Bonds","Yields","Volatility","Foreign",
    "Communication Services","Consumer Discretionary","Consumer Staples",
    "Energy","Financials","Health Care","Industrials","Information Technology",
    "Materials","Real Estate","Utilities","MR Discretion"
]

def _mmhm_load_latest() -> tuple[pd.DataFrame, str]:
    """
    Build a single Markmentum Heatmap frame similar to the portal page:
      - Latest row per ticker (from MM_CSV_BASE)
      - Columns: Name, Ticker, Category, Score, ΔDaily, ΔWTD, ΔMTD, ΔQTD
    """
    if not MM_CSV_BASE.exists():
        return pd.DataFrame(), ""

    base = pd.read_csv(MM_CSV_BASE)
    if base.empty or "Ticker" not in base.columns:
        return pd.DataFrame(), ""

    # as-of date (best effort)
    asof_str = ""
    if "Date" in base.columns:
        dtmax = pd.to_datetime(base["Date"], errors="coerce").max()
        if pd.notna(dtmax):
            asof_str = f"{dtmax.month}/{dtmax.day}/{dtmax.year}"

    # latest per ticker
    if "Date" in base.columns:
        base["_dt"] = pd.to_datetime(base["Date"], errors="coerce")
        base = (
            base.sort_values(["Ticker", "_dt"], ascending=[True, False])
                .drop_duplicates(subset=["Ticker"], keep="first")
        )

    # normalize expected columns (tolerant)
    cols_lower = {str(c).lower(): c for c in base.columns}
    name_col = cols_lower.get("ticker_name") or cols_lower.get("name") or cols_lower.get("company")
    cat_col  = cols_lower.get("category")
    score_col = (
        cols_lower.get("current_model_score")
        or cols_lower.get("model_score")
        or cols_lower.get("score")
    )
    dd_col = (
        cols_lower.get("model_score_daily_change")
        or cols_lower.get("daily_change")
        or cols_lower.get("score_daily_change")
    )

    out = pd.DataFrame({
        "Ticker": base["Ticker"].astype(str).str.strip(),
        "Name": base[name_col] if name_col else base["Ticker"].astype(str),
        "Category": base[cat_col] if cat_col else "",
        "Score": pd.to_numeric(base[score_col], errors="coerce") if score_col else np.nan,
        "ΔDaily": pd.to_numeric(base[dd_col], errors="coerce") if dd_col else np.nan,
    })

    # Helper to merge in WTD/MTD/QTD deltas if available
    def _merge_delta(p: Path, delta_key: str):
        nonlocal out
        if not p.exists():
            out[delta_key] = np.nan
            return

        d = pd.read_csv(p)
        if d.empty or "Ticker" not in d.columns:
            out[delta_key] = np.nan
            return

        dcols = {str(c).lower(): c for c in d.columns}
        delta_col = None
        # look for any column containing "change" but not "previous"
        for c in d.columns:
            low = str(c).lower()
            if "change" in low and "previous" not in low:
                delta_col = c
                break
        if not delta_col:
            out[delta_key] = np.nan
            return

        d2 = d[["Ticker", delta_col]].copy()
        d2["Ticker"] = d2["Ticker"].astype(str).str.strip()
        d2[delta_col] = pd.to_numeric(d2[delta_col], errors="coerce")
        d2 = d2.rename(columns={delta_col: delta_key})

        out = out.merge(d2, on="Ticker", how="left")

    _merge_delta(MM_CSV_WTD, "ΔWTD")
    _merge_delta(MM_CSV_MTD, "ΔMTD")
    _merge_delta(MM_CSV_QTD, "ΔQTD")

    # enforce preferred category order (stable)
    order_map = {name: i for i, name in enumerate(MM_CATEGORY_ORDER)}
    out["__ord__"] = out["Category"].map(order_map).fillna(10_000).astype(int)
    out = out.sort_values(["__ord__", "Category", "Ticker"], kind="stable").drop(columns="__ord__")

    return out, asof_str


def _mmhm_make_colored_table(df: pd.DataFrame, vmax: dict, include_ticker: bool) -> Table:
    """
    PDF table:
      - Score column shaded via _mm_bg_color
      - Δ columns shaded via _sr_delta_bg with provided vmax per column
    """
    cols = ["Name"]
    if include_ticker:
        cols.append("Ticker")
    cols += ["Score", "Δ Daily", "Δ WTD", "Δ MTD", "Δ QTD"]

    # header row as plain strings (Sharpe-style sizing/behavior)
    data = [cols]

    # rows
    for _, r in df.iterrows():
        row = [clean_text(r.get("Name", ""))]
        if include_ticker:
            row.append(clean_text(r.get("Ticker", "")))

        row += [
            fmt_int(r.get("Score")),
            fmt_int(r.get("Daily")),
            fmt_int(r.get("WTD")),
            fmt_int(r.get("MTD")),
            fmt_int(r.get("QTD")),
        ]
        data.append(row)

    # Sharpe Rank Heatmap sizing approach (NO fixed colWidths)
    t = Table(data, hAlign="CENTER")

    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),      # Name left
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),   # rest centered
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # column indices
    c_score = 1 if not include_ticker else 2
    c_d0 = c_score + 1  # Δ Daily
    c_d1 = c_score + 2  # Δ WTD
    c_d2 = c_score + 3  # Δ MTD
    c_d3 = c_score + 4  # Δ QTD

    # Score shading
    for i in range(1, len(data)):
        v = pd.to_numeric(df.iloc[i-1].get("Score"), errors="coerce")
        ts.add("BACKGROUND", (c_score, i), (c_score, i), _mm_bg_color(v))

    # Delta shading (independent per timeframe, same as Sharpe logic)
    for (col_idx, key, src_col) in [
        (c_d0, "Daily", "ΔDaily"),
        (c_d1, "WTD",   "ΔWTD"),
        (c_d2, "MTD",   "ΔMTD"),
        (c_d3, "QTD",   "ΔQTD"),
    ]:
        col_vmax = vmax.get(key, 1.0) or 1.0
        for i in range(1, len(data)):
            v = pd.to_numeric(df.iloc[i-1].get(key), errors="coerce")
            ts.add("BACKGROUND", (col_idx, i), (col_idx, i), _sr_delta_bg(v, col_vmax))

    t.setStyle(ts)
    return t


def build_markmentum_heatmap_pdf(
    include_macro_orientation: bool = True,
    include_category_averages: bool = True,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=36, rightMargin=36,
        topMargin=36, bottomMargin=40
    )

    flow: list = []

    df, asof = _mmhm_load_latest()
    title = "Markmentum Heatmap" #+ (f" – {asof}" if asof else "")
    flow.append(Paragraph(clean_text(title), H1))
    flow.append(Spacer(1, 6))

    if df.empty:
        flow.append(Paragraph("Markmentum Heatmap data missing or empty.", NOTE))
        doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    # -------------------------
    # Macro Orientation
    # -------------------------
    if include_macro_orientation:
        m = df[df["Ticker"].isin(MM_MACRO_LIST)].copy()
        if not m.empty:
            # keep macro order
            m["__ord__"] = m["Ticker"].map({t:i for i,t in enumerate(MM_MACRO_LIST)})
            m = m.sort_values(["__ord__"], kind="stable").drop(columns="__ord__")

            flow.append(Paragraph("Macro Orientation", H2))
            flow.append(Spacer(1, 6))

            vmax = {
                "Daily": _robust_vmax(m["ΔDaily"], q=0.98, floor=1.0, step=1.0),
                "WTD":   _robust_vmax(m["ΔWTD"],   q=0.98, floor=1.0, step=1.0),
                "MTD":   _robust_vmax(m["ΔMTD"],   q=0.98, floor=1.0, step=1.0),
                "QTD":   _robust_vmax(m["ΔQTD"],   q=0.98, floor=1.0, step=1.0),
            }
            m_tbl = m.rename(columns={"ΔDaily":"Daily","ΔWTD":"WTD","ΔMTD":"MTD","ΔQTD":"QTD"})[
                ["Name","Ticker","Score","Daily","WTD","MTD","QTD"]
            ].copy()
            flow.append(_mmhm_make_colored_table(m_tbl, vmax, include_ticker=True))
            flow.append(Spacer(1, 10))
            flow.append(PageBreak())

    # -------------------------
    # Category Averages
    # -------------------------
    if include_category_averages and "Category" in df.columns and df["Category"].astype(str).str.len().gt(0).any():
        g = (
            df.groupby("Category", as_index=False)
              .agg(
                  Score=("Score", "mean"),
                  Daily=("ΔDaily", "mean"),
                  WTD=("ΔWTD", "mean"),
                  MTD=("ΔMTD", "mean"),
                  QTD=("ΔQTD", "mean"),
              )
        )

        # enforce preferred order
        order_map = {name: i for i, name in enumerate(MM_CATEGORY_ORDER)}
        g["__ord__"] = g["Category"].map(order_map).fillna(10_000).astype(int)
        g = g.sort_values(["__ord__", "Category"], kind="stable")

        cat = g.rename(columns={"Category":"Name"})[["Name","Score","Daily","WTD","MTD","QTD"]].copy()

        vmax = {
            "Daily": _robust_vmax(cat["Daily"], q=0.98, floor=1.0, step=1.0),
            "WTD":   _robust_vmax(cat["WTD"],   q=0.98, floor=1.0, step=1.0),
            "MTD":   _robust_vmax(cat["MTD"],   q=0.98, floor=1.0, step=1.0),
            "QTD":   _robust_vmax(cat["QTD"],   q=0.98, floor=1.0, step=1.0),
        }

        flow.append(Paragraph("Category Averages", H2))
        flow.append(Spacer(1, 6))
        flow.append(_mmhm_make_colored_table(cat, vmax, include_ticker=False))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

# =========================================================
# DIRECTIONAL TRENDS (PDF) — MACRO ORIENTATION ONLY
# Source: qry_graph_data_88.csv
# =========================================================

DT_CSV = DATA_DIR / "qry_graph_data_88.csv"

DT_MACRO_LIST = [
    "SPX","NDX","DJI","RUT",
    "XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY",
    "GLD","DXY","TLT","BTC=F"
]

def _dt_load_latest() -> tuple[pd.DataFrame, str]:
    """Loads qry_graph_data_88.csv and returns latest row per ticker + as-of date string."""
    if not DT_CSV.exists():
        return pd.DataFrame(), ""

    df = pd.read_csv(DT_CSV)
    if df.empty or "Date" not in df.columns or "Ticker" not in df.columns:
        return pd.DataFrame(), ""

    df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values(["Ticker", "_dt"], ascending=[True, False]).drop_duplicates("Ticker", keep="first")

    asof = df["_dt"].max()
    asof_str = f"{asof.month}/{asof.day}/{asof.year}" if pd.notna(asof) else ""
    return df, asof_str


def _dt_tape_bias_label(st, mt, lt, stc, mtc) -> str:
    """Exact tape-bias logic from 07_Directional_Trends.py (m2_label)."""
    vals = [st, mt, lt, stc, mtc]
    if any(pd.isna(v) for v in vals):
        return "Insufficient data"
    try:
        st, mt, lt, stc, mtc = map(float, vals)
    except Exception:
        return "Insufficient data"

    threshold = 0.0005  # = 0.05%
    both_up        = (stc >= threshold and mtc >= threshold)
    both_down      = (stc <= -threshold and mtc <= -threshold)
    st_up_mt_down  = (stc >= threshold and mtc <= -threshold)
    st_down_mt_up  = (stc <= -threshold and mtc >= threshold)

    if abs(stc) <= threshold or abs(mtc) <= threshold:
        return "Neutral"

    # A) Confirmed bullish stack: ST < MT < LT
    if st < mt < lt:
        if both_up:
            return "Buy"
        if st_up_mt_down:
            return "Bottoming"
        if st_down_mt_up:
            return "Bottoming"
        if both_down:
            return "Sell"
        return "Neutral"

    # B) LT in the middle (ST < LT < MT)
    if st < lt < mt:
        if both_up:
            return "Leaning Bullish"
        if st_up_mt_down:
            return "Neutral"
        if st_down_mt_up:
            return "Leaning Bullish"
        if both_down:
            return "Leaning Bearish"
        return "Neutral"

    # C) Bullish half, not the stack (MT < ST < LT)
    if mt < st < lt:
        if both_up:
            return "Leaning Bullish"
        if st_up_mt_down:
            return "Neutral"
        if st_down_mt_up:
            return "Neutral"
        if both_down:
            return "Leaning Bearish"
        return "Neutral"

    # D) LT in the middle (MT < LT < ST)
    if mt < lt < st:
        if both_up:
            return "Leaning Bullish"
        if st_up_mt_down:
            return "Neutral"
        if st_down_mt_up:
            return "Neutral"
        if both_down:
            return "Leaning Bearish"
        return "Neutral"

    # E) Bearish half, not the stack (LT < ST < MT)
    if lt < st < mt:
        if both_up:
            return "Leaning Bullish"
        if st_up_mt_down:
            return "Leaning Bearish"
        if st_down_mt_up:
            return "Neutral"
        if both_down:
            return "Leaning Bearish"
        return "Neutral"

    # F) Confirmed bearish stack (LT < MT < ST)
    if lt < mt < st:
        if both_up:
            return "Buy"
        if st_up_mt_down:
            return "Topping"
        if st_down_mt_up:
            return "Topping"
        if both_down:
            return "Sell"
        return "Neutral"

    return "Neutral"


def _dt_make_colored_table(df: pd.DataFrame, vmax: dict) -> Table:
    """Macro table with Sharpe-rank delta shading philosophy."""
    cols = [
        "Name", "Ticker",
        "ST", "MT", "LT",
        "ST Change", "MT Change", "LT Change",
        "Tape Bias",
    ]

    # ✅ Display labels (only affect header text, not dataframe keys)
    header_labels = [
        "Name", "Ticker",
        "ST", "MT", "LT",
        "Δ ST", "Δ MT", "Δ LT",
        "Tape Bias",
    ]

    header = [th(c) for c in header_labels]
    #header = [th(c) for c in cols]

    data = [header]
    for _, r in df.iterrows():
        data.append([
            clean_text(r.get("Name", "")),
            pdf_safe_text(r.get("Ticker", "")),
            fmt_pct(r.get("ST"), 1),
            fmt_pct(r.get("MT"), 1),
            fmt_pct(r.get("LT"), 1),
            fmt_pct(r.get("ST Change"), 1),
            fmt_pct(r.get("MT Change"), 1),
            fmt_pct(r.get("LT Change"), 1),
            pdf_safe_text(r.get("Tape Bias", "")),
        ])

    widths = [
        2.6*inch, 0.75*inch,
        0.78*inch, 0.78*inch, 0.78*inch,
        0.90*inch, 0.90*inch, 0.90*inch,
        1.20*inch,
    ]

    t = Table(data, colWidths=widths, repeatRows=1)

    ts = TableStyle([
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#d9d9d9")),
        ("FONT", (0,1), (-1,-1), "Helvetica", 9),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("ALIGN", (1,0), (1,-1), "CENTER"),
        ("ALIGN", (2,0), (7,-1), "RIGHT"),
        ("ALIGN", (8,0), (8,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ])

    # Shade numeric columns with _sr_delta_bg (same philosophy as Sharpe Rank)
    shade_cols = ["ST", "MT", "LT", "ST Change", "MT Change", "LT Change"]
    col_index = {c: i for i, c in enumerate(cols)}
    for c in shade_cols:
        j = col_index[c]
        col_vmax = float(vmax.get(c) or 1e-6)
        for i in range(1, len(data)):
            v = pd.to_numeric(df.iloc[i-1].get(c), errors="coerce")
            bg = _sr_delta_bg(v, col_vmax)
            if bg is not None:
                ts.add("BACKGROUND", (j, i), (j, i), bg)

    t.setStyle(ts)
    return t


def build_directional_trends_pdf() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=36, rightMargin=36,
        topMargin=36, bottomMargin=40,
    )

    flow: list = []

    df, asof = _dt_load_latest()
    title = "Directional Trends"
    flow.append(Paragraph(clean_text(title), H1))
    flow.append(Spacer(1, 6))

    if df.empty:
        flow.append(Paragraph("Directional Trends data missing or empty (qry_graph_data_88.csv).", NOTE))
        doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    # Macro Orientation only
    m = df[df["Ticker"].isin(DT_MACRO_LIST)].copy()
    if m.empty:
        flow.append(Paragraph("Directional Trends Macro Orientation is empty.", NOTE))
        doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    # keep macro order
    m["__ord__"] = m["Ticker"].map({t:i for i, t in enumerate(DT_MACRO_LIST)})
    m = m.sort_values(["__ord__"], kind="stable").drop(columns=["__ord__"], errors="ignore")

    for c in ["st_trend","mt_trend","lt_trend","st_trend_change","mt_trend_change","lt_trend_change"]:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c], errors="coerce")

    m_tbl = pd.DataFrame({
        "Name": m.get("Ticker_name", ""),
        "Ticker": m.get("Ticker", ""),
        "ST": m.get("st_trend"),
        "MT": m.get("mt_trend"),
        "LT": m.get("lt_trend"),
        "ST Change": m.get("st_trend_change"),
        "MT Change": m.get("mt_trend_change"),
        "LT Change": m.get("lt_trend_change"),
    })
    m_tbl["Tape Bias"] = [
        _dt_tape_bias_label(st, mt, lt, stc, mtc)
        for st, mt, lt, stc, mtc in zip(
            m_tbl["ST"], m_tbl["MT"], m_tbl["LT"],
            m_tbl["ST Change"], m_tbl["MT Change"],
        )
    ]

    flow.append(Paragraph("Macro Orientation", H2))
    flow.append(Spacer(1, 6))

    vmax = {
        "ST":        _robust_vmax(m_tbl["ST"],        q=0.98, floor=1e-6, step=1e-6),
        "MT":        _robust_vmax(m_tbl["MT"],        q=0.98, floor=1e-6, step=1e-6),
        "LT":        _robust_vmax(m_tbl["LT"],        q=0.98, floor=1e-6, step=1e-6),
        "ST Change": _robust_vmax(m_tbl["ST Change"], q=0.98, floor=1e-6, step=1e-6),
        "MT Change": _robust_vmax(m_tbl["MT Change"], q=0.98, floor=1e-6, step=1e-6),
        "LT Change": _robust_vmax(m_tbl["LT Change"], q=0.98, floor=1e-6, step=1e-6),
    }

    flow.append(_dt_make_colored_table(m_tbl, vmax))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(
        "Legend: Buy – Uptrend confirmed · Leaning Bullish – Bullish setup, confirmation pending · "
        "Neutral – Crosscurrents / mixed trends · Topping / Bottoming – Transition zones where trends may reverse · "
        "Leaning Bearish – Bearish bias but not fully aligned · Sell – Downtrend confirmed.",
        NOTE,
    ))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

# =========================================================
# MODULAR PACKET ARCHITECTURE (NEW)
# =========================================================
def merge_pdf_bytes_in_order(pdf_blobs: list[bytes]) -> bytes:
    """Merge already-built PDFs into one PDF (order preserved)."""
    writer = PdfWriter()
    for blob in pdf_blobs:
        reader = PdfReader(io.BytesIO(blob))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

def normalize_timeframes(selected: list[str]) -> list[str]:
    """Enforce your current behavior: Daily always included for Morning Compass packet."""
    if not selected:
        return ["Daily"]
    # ensure Daily first if included
    s = list(dict.fromkeys(selected))
    if "Daily" in s:
        s = ["Daily"] + [x for x in s if x != "Daily"]
    return s

class ReportModuleBase:
    key: str = "base"
    label: str = "Base Module"

    def ui(self) -> dict:
        """
        Render module UI and return an options dict.
        Must be deterministic given Streamlit state.
        """
        return {}

    def build(self, options: dict) -> tuple[list[bytes], str]:
        """
        Return (pdfs_in_order, filename_stub)
        - pdfs_in_order: list of pdf bytes blobs
        - filename_stub: used to name download file
        """
        return ([], "report")


class MorningCompassModule(ReportModuleBase):
    key = "morning_compass"
    label = "Morning Compass"

    def ui(self) -> dict:
        left, mid, right = st.columns([1, 1, 1])

        with left:
            extra_tfs = st.multiselect(
                "Add Timeframes (Optional)",
                ["Weekly", "Monthly"],
                default=[]
            )

            # If user picked any extra timeframe, let them exclude Daily
            allow_exclude_daily = len(extra_tfs) > 0
            include_daily = st.checkbox(
                "Include Daily",
                value=True,
                disabled=not allow_exclude_daily,
                help="Daily is required unless you select Weekly and/or Monthly."
            )

            tf_keys = (["Daily"] if include_daily else []) + extra_tfs

        # Safety: never allow empty selection
        if not tf_keys:
            tf_keys = ["Daily"]

        st.caption(
            "Select Weekly and/or Monthly to add them to the report. "
            "If you select another timeframe, you may uncheck 'Include Daily' to exclude Daily."
        )

        daily_selected = "Daily" in tf_keys

        with mid:
            st.markdown("**Include Sections**")
            include_macro = st.checkbox("Macro Orientation (by timeframe)", value=True)

            corr_key = f"{self.key}_include_correlations"

            # If Daily isn't in tf_keys, force correlations OFF (prevents stale True)
            if not daily_selected:
                st.session_state[corr_key] = False

            include_correlations = st.checkbox(
                "Correlations (USD + Rates) (Daily only)",
                value=st.session_state.get(corr_key, True),
                key=corr_key,
                disabled=not daily_selected,
            )
            
        with right:
            st.markdown("**Top Five Cards (by timeframe)**")
            include_pct   = st.checkbox("Top Five Leaders/Laggards by % Change", value=True)
            include_mm    = st.checkbox("Top Five Leaders/Laggards by MM Score", value=True)
            include_delta = st.checkbox("Top Five Leaders/Laggards by MM Score Change", value=True)

        # Preview metadata (show all selected timeframes)
        preview_parts = []
        for k in tf_keys:
            asof_k = _asof_date_from_main(k)
            preview_parts.append(f"{k}: {asof_k if asof_k else '(date not found)'}")
        st.markdown("**Preview:** Morning Compass – " + " | ".join(preview_parts))

        return {
            "tf_keys": tf_keys,
            "include_correlations": include_correlations,
            "include_macro": include_macro,
            "include_pct": include_pct,
            "include_mm": include_mm,
            "include_delta": include_delta,
        }

    def build(self, options: dict) -> tuple[list[bytes], str]:
        tf_keys = options.get("tf_keys", ["Daily"])
        # already Daily-first; keep as-is
        blobs: list[bytes] = []

        for tf_key in tf_keys:
            blobs.append(
                build_morning_compass_pdf(
                    include_correlations=options.get("include_correlations", True),
                    include_macro=options.get("include_macro", True),
                    include_pct=options.get("include_pct", True),
                    include_mm=options.get("include_mm", True),
                    include_delta=options.get("include_delta", True),
                    tf_key=tf_key
                )
            )

        # naming: matches your current logic using Daily date if present
        tf_for_date = "Daily" if "Daily" in tf_keys else tf_keys[0]
        asof = _asof_date_from_main(tf_for_date)
        tf_slug = "-".join([t.lower() for t in tf_keys])
        filename_stub = f"markmentum_morning_compass_{tf_slug}_{asof.replace('/','-') if asof else 'report'}"
        return (blobs, filename_stub)


class MarketOverviewModule(ReportModuleBase):
    key = "market_overview"
    label = "Market Overview"

    #def ui(self) -> dict:
    #    tf_key = st.selectbox(
    #        "Timeframe",
    #        MO_TF_LABELS,
    #        index=0
    #    )

    def ui(self) -> dict:
        extra_tfs = st.multiselect(
            "Add Timeframes (Optional)",
            ["Weekly", "Monthly", "Quarterly"],
            default=[]
        )

        allow_exclude_daily = len(extra_tfs) > 0
        include_daily = st.checkbox(
            "Include Daily",
            value=True,
            disabled=not allow_exclude_daily,
            help="Daily is required unless you select Weekly, Monthly, or Quarterly."
        )

        tf_keys = (["Daily"] if include_daily else []) + extra_tfs

        if not tf_keys:
            tf_keys = ["Daily"]

        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            include_top_cards = st.checkbox("Include Top % Gainers / Top % Decliners / Most Active", value=True)
            include_score_change_cards = st.checkbox("Include MM Score Gainers / Decliners / Change Distribution", value=True)

        with c2:
#            include_daily_extras = st.checkbox(
#                "Include Daily extras (Highest/Lowest/Histogram + Opportunity Density)",
#                value=True,
#                disabled=(tf_key != "Daily")
#            )
            daily_selected = "Daily" in tf_keys

            extras_key = f"{self.key}_include_daily_extras"

            # If Daily isn't in tf_keys, force extras OFF (prevents stale True)
            if not daily_selected:
                st.session_state[extras_key] = False
            
            include_daily_extras = st.checkbox(
                "Include Daily extras (Highest/Lowest/Histogram + Opportunity Density)",
                value=st.session_state.get(extras_key, True),
                key=extras_key,
                disabled=not daily_selected,
            )
            

        with c3:
            include_market_read = st.checkbox("Include Market Read", value=True)

        st.caption(
            "Select Weekly, Monthly, Quarterly to add them to the report. "
            "If you select another timeframe, you may uncheck 'Include Daily' to exclude Daily."
        )

        # Preview
        preview_parts = []
        for k in tf_keys:
            dfs = mo_load_for_timeframe(k)
            asof = _mo_asof_from_df(dfs[0])
            preview_parts.append(f"{k}: {asof if asof else '(date not found)'}")
        st.markdown("**Preview:** Market Overview – " + " | ".join(preview_parts))

        return {
            "tf_keys": tf_keys,
            "include_top_cards": include_top_cards,
            "include_score_change_cards": include_score_change_cards,
            "include_daily_extras": include_daily_extras,   # applies to Daily only in build()
            "include_market_read": include_market_read,
        }

    def build(self, options: dict) -> tuple[list[bytes], str]:
        tf_keys = options.get("tf_keys", ["Daily"])

        # enforce order: Daily, Weekly, Monthly, Quarterly
        order = ["Daily", "Weekly", "Monthly", "Quarterly"]
        tf_keys = [t for t in order if t in tf_keys]

        blobs: list[bytes] = []

        for tf_key in tf_keys:
            blobs.append(
                build_market_overview_pdf(
                    tf_key=tf_key,
                    include_top_cards=options.get("include_top_cards", True),
                    include_score_change_cards=options.get("include_score_change_cards", True),
                    include_daily_extras=(tf_key == "Daily" and options.get("include_daily_extras", True)),
                    include_market_read=options.get("include_market_read", True),
                )
            )

        # filename stub
        tf_for_date = "Daily" if "Daily" in tf_keys else tf_keys[0]
        asof = _mo_asof_from_df(mo_load_for_timeframe(tf_for_date)[0])
        date_slug = asof.replace("/", "-") if asof else "report"
        tf_slug = "-".join([t.lower() for t in tf_keys])
        stub = f"market_overview_{tf_slug}_{date_slug}"

        return (blobs, stub)


class PerformanceHeatmapModule(ReportModuleBase):
    key = "performance_heatmap"
    label = "Performance Heatmap"

    def ui(self) -> dict:
        # defaults: keep it tight; table shading already conveys “heatmap”
        include_macro = st.checkbox(
            "Include Macro Orientation",
            value=True,
            key=f"{self.key}_include_macro",
        )
        include_cat = st.checkbox(
            "Include Category Averages",
            value=True,
            key=f"{self.key}_include_cat",
        )
        include_heatmap = False #skip for now

        # preview date
        _, asof = _ph_load_latest()
        if asof:
            st.markdown(f"**Preview:** Performance Heatmap – {asof}")

        st.caption("Note: Per-ticker category breakouts are intentionally excluded from the report pack.")
        return {
            "include_macro": include_macro,
            "include_cat": include_cat,
            "include_heatmap": include_heatmap,
        }

    def build(self, options: dict) -> tuple[list[bytes], str]:
        blob = build_performance_heatmap_pdf(
            include_macro_orientation=options.get("include_macro", True),
            include_category_averages=options.get("include_cat", True),
            include_category_heatmap=options.get("include_heatmap", False),
        )
        # filename stub
        return ([blob], "performance_heatmap")

class SharpeRankHeatmapModule(ReportModuleBase):
    key = "sharpe_rank_heatmap"
    label = "Sharpe Rank Heatmap"

    def ui(self) -> dict:
        include_macro = st.checkbox(
            "Include Macro Orientation",
            value=True,
            key=f"{self.key}_include_macro",
        )
        include_cat = st.checkbox(
            "Include Category Averages",
            value=True,
            key=f"{self.key}_include_cat",
        )

        # preview date
        _, asof = _sr_load_latest()
        if asof:
            st.markdown(f"**Preview:** Sharpe Rank Heatmap – {asof}")

        st.caption("Note: Per-ticker category breakouts are intentionally excluded from the report pack.")
        return {
            "include_macro": include_macro,
            "include_cat": include_cat,
        }

    def build(self, options: dict) -> tuple[list[bytes], str]:
        blob = build_sharpe_rank_heatmap_pdf(
            include_macro_orientation=options.get("include_macro", True),
            include_category_averages=options.get("include_cat", True),
        )
        return ([blob], "sharpe_rank_heatmap")


class MarkmentumHeatmapModule(ReportModuleBase):
    key = "markmentum_heatmap"
    label = "Markmentum Heatmap"

    def ui(self) -> dict:
        include_macro = st.checkbox(
            "Include Macro Orientation",
            value=True,
            key=f"{self.key}_include_macro",
        )
        include_cat = st.checkbox(
            "Include Category Averages",
            value=True,
            key=f"{self.key}_include_cat",
        )

        # preview date
        _, asof = _mmhm_load_latest()
        if asof:
            st.markdown(f"**Preview:** Markmentum Heatmap – {asof}")

        st.caption("Note: Per-ticker category breakouts are intentionally excluded from the report pack.")
        return {
            "include_macro": include_macro,
            "include_cat": include_cat,
        }

    def build(self, options: dict) -> tuple[list[bytes], str]:
        blob = build_markmentum_heatmap_pdf(
            include_macro_orientation=options.get("include_macro", True),
            include_category_averages=options.get("include_cat", True),
        )
        return ([blob], "markmentum_heatmap")


class PlaceholderModule(ReportModuleBase):
    """Safe placeholder so you can turn on modules without breaking the packet builder."""
    def __init__(self, key: str, label: str):
        self.key = key
        self.label = label

    def ui(self) -> dict:
        st.info(f"{self.label} module is not wired to PDF yet. (Placeholder)")
        return {}

    def build(self, options: dict) -> tuple[list[bytes], str]:
        # returns no pdfs; packet builder will skip it
        return ([], self.key)


class DirectionalTrendsModule(ReportModuleBase):
    key = "directional_trends"
    label = "Directional Trends"

    def ui(self) -> dict:
        # No options: research pack includes Macro Orientation only.
        st.caption("Macro Orientation only (no options)")

        # preview date
        _, asof = _dt_load_latest()
        if asof:
            st.markdown(f"**Preview:** Directional Trends – {asof}")

        return {}

    def build(self, options: dict) -> tuple[list[bytes], str]:
        blob = build_directional_trends_pdf()
        return ([blob], "directional_trends")


REGISTERED_MODULES: list[ReportModuleBase] = [
    MorningCompassModule(),
    MarketOverviewModule(),
    PerformanceHeatmapModule(),
    SharpeRankHeatmapModule(),
    MarkmentumHeatmapModule(),
    DirectionalTrendsModule(),
    #PlaceholderModule("vantage_point", "Vantage Point"),
]

MODULE_BY_KEY = {m.key: m for m in REGISTERED_MODULES}



# =========================================================
# UI (MODULAR)
# =========================================================
st.markdown(
    "<div style='text-align:center; font-size:22px; font-weight:700; margin-top:8px;'>Research Pack</div>",
    unsafe_allow_html=True
)
st.markdown(
    "<div style='text-align:center; color:#6c757d; margin-bottom:16px;'>Build a curated research pack from portal sections</div>",
    unsafe_allow_html=True
)

st.divider()

# ---- Module selection ----
# Default only Morning Compass ON (same as your current behavior)
default_selected = ["morning_compass"]

selected_keys = []
for m in REGISTERED_MODULES:
    checked = st.checkbox(
        m.label,
        value=(m.key in default_selected),
        key=f"select_{m.key}",
    )
    if checked:
        selected_keys.append(m.key)

# ---- Module options blocks ----
module_options: dict[str, dict] = {}

# Separator between selection list and builder options
st.divider()

for key in selected_keys:
    module = MODULE_BY_KEY[key]
    with st.expander(f"{module.label} Options", expanded=(key in selected_keys)):
        module_options[key] = module.ui()

st.divider()

# ---- Generate packet ----
gen = st.button("Generate Research Pack", type="primary", disabled=(len(selected_keys) == 0))

if gen:
    pdf_parts: list[bytes] = []
    filename_parts: list[str] = []

    for key in selected_keys:
        module = MODULE_BY_KEY[key]
        blobs, stub = module.build(module_options.get(key, {}))
        if blobs:
            pdf_parts.extend(blobs)
            filename_parts.append(stub)

    if not pdf_parts:
        st.warning("No PDFs were generated (selected modules are placeholders or missing data).")
        st.stop()

    # If only one part, keep exact “single blob” behavior; else merge.
    #if len(pdf_parts) == 1:
    #    final_pdf = pdf_parts[0]
    #else:
    #    final_pdf = merge_pdf_bytes_in_order(pdf_parts)

    # Build cover page using Daily as-of (best effort)
    # Trading session = next calendar day
    from datetime import datetime, timedelta

    trading_session = ""
    data_asof = ""

    session_str = _asof_date_from_main("Daily")  # this is your "Trading Session" date
    if session_str:
        dt_session = datetime.strptime(session_str, "%m/%d/%Y")

        # Data-as-of = prior trading day (simple weekday fallback)
        dt_asof = dt_session - timedelta(days=1)
        while dt_asof.weekday() >= 5:  # 5=Sat, 6=Sun
            dt_asof -= timedelta(days=1)

        # Windows-safe formatting (no %-m / %-d)
        trading_session = f"{dt_session.month}/{dt_session.day}/{dt_session.year}"
        data_asof = f"{dt_asof.month}/{dt_asof.day}/{dt_asof.year}"

    cover_pdf = build_title_page_pdf(trading_session, data_asof)

    # Always prepend cover page
    pdf_parts_with_cover = [cover_pdf] + pdf_parts

    # Merge into one PDF (cover + content)
    final_pdf = merge_pdf_bytes_in_order(pdf_parts_with_cover)


    # Filename:
    # - If only Morning Compass, the stub already matches your v3 naming.
    # - If multiple modules, create a clean packet name.
    #if len(filename_parts) == 1:
    #    filename = f"{filename_parts[0]}.pdf"
    #else:
        # include Daily as-of if possible (best-effort)
    #    asof = _asof_date_from_main("Daily")
    #    date_slug = asof.replace("/", "-") if asof else "report"
    #    filename = f"markmentum_packet_{date_slug}.pdf"

    asof = _asof_date_from_main("Daily")
    date_slug = trading_session.replace("/", "-") if trading_session else "report"
    filename = f"Markmentum Research Pack - {date_slug}.pdf"


    st.success("Research Pack ready.")
    st.download_button(
        label="Download Research Pack",
        data=final_pdf,
        file_name=filename,
        mime="application/pdf"
    )

st.markdown("---")
st.markdown(
    f"<div style='font-size: 12px; color: gray;'>{DISCLAIMER_TEXT}</div>",
    unsafe_allow_html=True
)