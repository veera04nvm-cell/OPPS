from datetime import datetime

import pandas as pd
import streamlit as st

from utils import config as CFG
from utils import data_loader as dl
from utils import geo_utils
from utils import report_builder as rb
from utils import theme

st.set_page_config(page_title="Download Report", page_icon="🔅", layout="wide")
theme.inject_theme()
theme.masthead(
    title="🔅 Download Report",
    subtitle="Generate a printable PDF for one deployment day - every model's officer "
             "placement map, coverage-gap map, zone data, and the demand-misalignment "
             "rose map, all in one document.",
)

gis_all = dl.load_gis_alloc_all()
zone_gdf, gdf_is_real = geo_utils.load_zone_gdf()
zone_gdf_native = geo_utils.load_zone_gdf_native()
gap_long = dl.build_uniform_gap_long()

if gis_all.empty:
    st.error("No allocation data found. Check that gis_alloc_*.csv files are in the data/ folder.")
    st.stop()

combos = dl.gis_alloc_available_dates_shifts()
dates_available = sorted(set(c[0] for c in combos))
date_labels = {d: pd.Timestamp(d).strftime("%A, %b %d, %Y") for d in dates_available}
day_names = {d: pd.Timestamp(d).strftime("%A") for d in dates_available}

st.header("🔅 Choose a deployment day")
with st.container(key="report_filters"):
    sel_date = st.selectbox("Date", options=dates_available, format_func=lambda d: date_labels[d])

shifts_for_date = sorted(set(c[2] for c in combos if c[0] == sel_date))
shift_labels_present = [CFG.SHIFT_LABELS.get(s.split("_")[-1], s) for s in shifts_for_date]
st.caption(f"This report will include every shift with data on this date: {', '.join(shift_labels_present)}.")

st.divider()

st.subheader("✨ What's included")
st.markdown(
    "- **Recommended Officer Placement** maps for Uniform, Static, and Dynamic plans, for each shift\n"
    "- **Coverage Gap vs. Demand** maps for all three plans, for each shift\n"
    "- A **zone data table** (officer counts, demand share, gap) for each shift\n"
    "- The **demand-misalignment rose map** for the day, showing where the current Uniform Plan "
    "misses actual demand across Day/Evening/Night shifts"
)

st.divider()

if st.button("🔅 Generate Report", type="primary"):
    with st.spinner("Building report - this renders every map fresh, so it can take a minute..."):
        try:
            day_name = day_names[sel_date]
            pdf_bytes = rb.build_daily_report_pdf(
                sel_date, gis_all, zone_gdf, zone_gdf_native, gap_long, day_name,
            )
            st.session_state["opps_report_pdf"] = pdf_bytes
            st.session_state["opps_report_filename"] = f"OPPS_Report_{sel_date}.pdf"
            st.success("Report ready.")
        except Exception as e:
            st.error(f"Report generation failed: {e}")

if "opps_report_pdf" in st.session_state:
    st.download_button(
        "⬇️ Download PDF",
        data=st.session_state["opps_report_pdf"],
        file_name=st.session_state["opps_report_filename"],
        mime="application/pdf",
        type="primary",
    )
