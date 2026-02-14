import streamlit as st
st.set_page_config(page_title="Markmentum – Downloads", layout="wide")

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

from pathlib import Path
from datetime import datetime
from io import BytesIO
import zipfile
import os
import base64
from zoneinfo import ZoneInfo

# ---------- Paths / assets ----------
_here = Path(__file__).resolve().parent
APP_DIR = _here if _here.name != "pages" else _here.parent
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "markmentum_logo.png"
EXPORT_DIR = Path(os.getenv("MARKMENTUM_EXPORT_DIR", APP_DIR / "data")).resolve()

def _image_b64(p: Path) -> str:
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()
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
#st.markdown("## Downloads")


# compact, centered content
#st.set_page_config(page_title="Markmentum - Downloads", layout="centered")


#st.markdown("## Downloads")

def narrow_container(ratio: float = 3.0):
    return st.columns([1, ratio, 1])[1]

with narrow_container(3):

    st.markdown("## Downloads")

    # ---------------- Catalog ----------------
    CATALOG = {
        "stat_box.csv":                    ("Stat Box",                          "stat_box.csv"),
        "signal_box.csv":                  ("Signal Box",                        "signal_box.csv"),
        "qry_graph_data_01.csv":           ("Probable Ranges",                   "Probable Ranges.csv"),
        "qry_graph_data_02.csv":           ("Trend Lines",                       "Trend Lines.csv"),
        "qry_graph_data_03.csv":           ("Probable Anchors",                  "Probable Anchors.csv"),
        "qry_graph_data_04.csv":           ("Price to LT Probable Anchor",       "Price to LT Probable Anchor.csv"),
        "qry_graph_data_05.csv":           ("30-Day Rvol Z-Score",               "30-Day Rvol Z-Score.csv"),
        "qry_graph_data_06.csv":           ("Z-Score Percentile Rank",           "Z-Score Percentile Rank.csv"),
        "qry_graph_data_07.csv":           ("Rvol 30-Day",                       "Rvol 30-Day.csv"),
        "qry_graph_data_08.csv":           ("30-Day Sharpe Ratio",               "30-Day Sharpe Ratio.csv"),
        "qry_graph_data_09.csv":           ("Sharpe Ratio Percentile Rank",      "Sharpe Ratio Percentile Rank.csv"),
        "qry_graph_data_10.csv":           ("IVol Prem/Disc",                    "IVol Prem/Disc.csv"),
        "qry_graph_data_11.csv":           ("MM Score",                          "MM Score.csv"),
        "qry_graph_data_12.csv":           ("IVol/RVol % Spreads",               "IVol-RVol % Spreads.csv"),
        "qry_graph_data_13.csv":           ("Daily Returns",                     "Daily Returns.csv"),
        "qry_graph_data_14.csv":           ("Daily Range",                       "Daily Range.csv"),
        "qry_graph_data_15.csv":           ("Daily Volume",                      "Daily Volume.csv"),
        "qry_graph_data_16.csv":           ("Weekly Returns",                    "Weekly Returns.csv"),
        "qry_graph_data_17.csv":           ("Weekly Range",                      "Weekly Range.csv"),
        "qry_graph_data_18.csv":           ("Weekly Volume",                     "Weekly Volume.csv"),
        "qry_graph_data_19.csv":           ("Monthly Returns",                   "Monthly Returns.csv"),
        "qry_graph_data_20.csv":           ("Monthly Range",                     "Monthly Range.csv"),
        "qry_graph_data_21.csv":           ("Monthly Volume",                    "Monthly Volume.csv"),
        "qry_graph_data_22.csv":           ("Short-Term Trend Line",             "Short-Term Trend Line.csv"),
        "qry_graph_data_23.csv":           ("Mid-Term Trend Line",               "Mid-Term Trend Line.csv"),
        "qry_graph_data_24.csv":           ("Long-Term Trend Line",              "Long-Term Trend Line.csv"),
    }

    # ---------------- Helpers ----------------
    def _human_size(n: int | None) -> str:
        if n is None: return "—"
        for u in ["B","KB","MB","GB","TB"]:
            if n < 1024: return f"{n:.0f} {u}"
            n /= 1024
        return f"{n:.0f} PB"

    APP_TZ = os.getenv("MARKMENTUM_TZ", "America/New_York")  # change if you prefer

    @st.cache_data(show_spinner=False)
    def _file_info(path_str: str):
        """Return (size, updated_date_str, mtime_epoch) if file exists; else (None, None, None)."""
        p = Path(path_str)
        if not p.exists():
            return None, None, None
        s = p.stat()
        ts = s.st_mtime
        dt_local = (
            datetime.utcfromtimestamp(ts)      # treat POSIX ts as UTC
            .replace(tzinfo=ZoneInfo("UTC"))   # make it timezone-aware
            .astimezone(ZoneInfo(APP_TZ))      # convert to display TZ (e.g., America/New_York)
        )
        updated_date_str = dt_local.strftime("%Y-%m-%d")  # date only

        # ✅ return the tuple (size, updated_date_str, mtime_epoch)
        return s.st_size, updated_date_str, int(s.st_mtime)

    @st.cache_data(show_spinner=False)
    def _read_bytes_cached(path_str: str, mtime_epoch: int):
        """Read bytes; cache by mtime so we only re-read when a file changes."""
        with open(path_str, "rb") as f:
            return f.read()

    def _build_zip(files):
        """Build zip NOW (called only when user clicks)."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path_str, outname in files:
                with open(path_str, "rb") as f:
                    zf.writestr(outname, f.read())
        buf.seek(0)
        return buf.getvalue()

    # ---------------- Rows --------------------
    rows = []
    for fname, (title, outname) in CATALOG.items():
        fpath = (EXPORT_DIR / fname).resolve()
        size, updated_str, mtime_epoch = _file_info(str(fpath))
        rows.append({
            "title": title, "outname": outname,
            "path": str(fpath) if mtime_epoch else None,
            "size": size, "updated": updated_str, "mtime": mtime_epoch
        })

    # ---------------- Table (no File col) -----
    st.divider()
    st.markdown("#### Files")

    h1, h3, h4 = st.columns([2, 1.2, 1.4])
    h1.markdown("**Title**")
    #h2.markdown("**Updated**")
    h3.markdown("**Size**")
    h4.markdown("**Download**")

    for r in rows:
        c1, c3, c4 = st.columns([2, 1.2, 1.4])
        c1.write(r["title"])
        #c2.write(r["updated"] or "—")
        c3.write(_human_size(r["size"]))
        if not r["path"]:
            c4.button("Not Available", disabled=True, use_container_width=True, key=f"na-{r['title']}")
        else:
            data = _read_bytes_cached(r["path"], r["mtime"])
            c4.download_button(
                "Download",
                data=data,
                file_name=r["outname"],
                mime="text/csv",
                key=f"dl-{r['outname']}",
                use_container_width=True,
            )

    # ---------------- Download ALL (at bottom; build on click) -----
    st.divider()
    existing = [(r["path"], r["outname"]) for r in rows if r["path"]]
    if existing:
        build = st.button("Prepare Download ALL (.zip)", type="primary", use_container_width=True)
        if build:
            st.session_state["zip_bytes"] = _build_zip(existing)
            st.success("ZIP ready.")
        if "zip_bytes" in st.session_state:
            st.download_button(
                "Download ALL (.zip)",
                data=st.session_state["zip_bytes"],
                file_name="markmentum_downloads.zip",
                mime="application/zip",
                use_container_width=True,
            )
    else:
        st.info("No exports found yet. When the nightly job runs, files will appear here.")


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