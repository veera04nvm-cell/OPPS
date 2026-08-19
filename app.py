import streamlit as st
import pandas as pd

from utils import config as CFG
from utils import data_loader as dl
from utils import geo_utils
from utils import theme

st.set_page_config(
    page_title=CFG.APP_TITLE,
    page_icon="🚓",
    layout="wide",
)
theme.inject_theme()

theme.masthead(
    title=f"🔅 {CFG.APP_TITLE}",
    subtitle=f"Deployment window: {CFG.DEPLOYMENT_WINDOW} · 8 patrol zones",
    eyebrow="Bartlett Police Department · Shelby County, TN",
)

st.markdown(
    "This tool translates historical crash and traffic-stop patterns into "
    "**patrol allocation guidance** for Bartlett's 8 patrol zones. "
    "Use the pages in the left sidebar to get started."
)

col1, col2, col3 = st.columns(3)
with col1:
    theme.nav_card(
        "Data Insights",
        "Maps, charts, and plain-language takeaways on where and when "
        "crashes and traffic stops happen across the city.",
    )
with col2:
    theme.nav_card(
        "Allocation Comparison",
        "See how three different patrol-allocation approaches "
        "(<strong>Uniform Plan</strong>, <strong>Static Plan</strong>, <strong>Dynamic Plan</strong>) "
        "distribute officers, and how well each matches actual demand.",
    )
with col3:
    theme.nav_card(
        "Help Guide",
        "New to this tool? Start here for a walkthrough of every map, "
        "chart, and color code used in the dashboard.",
    )

st.divider()

# ---------------------------------------------------------------------------
# Quick citywide snapshot
# ---------------------------------------------------------------------------
st.subheader("✨ Citywide Snapshot")

try:
    theil = dl.load_theil_workbook()
    zsum = theil["zone_summary"]
    t_test = theil["t_test"]

    h_mean_row = t_test[t_test["Parameter"] == "H_mean"]
    h_mean = float(h_mean_row["Value"].values[0]) if not h_mean_row.empty else None

    worst_zone_row = zsum.loc[zsum["Equity gap (s-r)"].idxmin()]
    best_zone_row = zsum.loc[zsum["Equity gap (s-r)"].idxmax()]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Patrol Zones", "8")
    k2.metric("Deployment Window", "7 days")
    if h_mean is not None:
        k3.metric("Current Misalignment Score*", f"{h_mean:.2f}", help="Lower is better. Measures how far today's Uniform Plan patrol is from matching actual demand.")
    k4.metric("Most Under-Patrolled Zone", worst_zone_row["Zone"])

    st.info(
        f"💡 **Quick takeaway:** Under the current Uniform Plan, "
        f"**{worst_zone_row['Zone']}** receives less patrol coverage than its demand justifies, "
        f"while **{best_zone_row['Zone']}** receives more than it needs. "
        f"See the **Allocation Comparison** page to view demand-based alternatives.",
    )
except Exception as e:
    st.warning(f"Snapshot data could not be loaded: {e}")
