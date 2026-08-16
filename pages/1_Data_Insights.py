import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils import config as CFG
from utils import data_loader as dl
from utils import geo_utils
from utils import interpret as itp
from utils import interactive_maps as imaps
from utils import static_maps
from utils import theme

st.set_page_config(page_title="Data Insights", page_icon="📊", layout="wide")
theme.inject_theme()
theme.masthead(
    title="🔅 Data Insights",
    subtitle="Explore where and when crashes and traffic stops happen across Bartlett. "
             "Every chart below updates live as you change the filters, and the note "
             "underneath explains what it means for patrol.",
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
crash_pts = dl.load_crash_points()
viol_pts = dl.load_violation_points()
crash_pm = dl.load_crashes_per_mile()
viol_pm = dl.load_violations_per_mile()
zone_sched = dl.load_zone_schedule()
theil = dl.load_theil_workbook()
zone_summary = theil["zone_summary"]
centroids = geo_utils.load_zone_centroids()
zone_gdf, gdf_is_real = geo_utils.load_zone_gdf()
zone_geojson, zone_field, geojson_status = geo_utils.load_zone_shapes()

all_days = CFG.DAY_ORDER
all_zones = CFG.ZONE_IDS
all_shifts = CFG.SHIFT_ORDER

# Tag each incident with its shift bucket once, up front
crash_pts = crash_pts.assign(shift=crash_pts["hour"].map(CFG.hour_to_shift))
viol_pts = viol_pts.assign(shift=viol_pts["hour"].map(CFG.hour_to_shift))

# ---------------------------------------------------------------------------
# Sidebar filters (apply to every chart on this page)
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")
sel_zones = st.sidebar.multiselect("Zones", options=all_zones, default=all_zones,
                                    format_func=lambda z: f"Zone {z}")
sel_days = st.sidebar.multiselect("Days of week", options=all_days, default=all_days)
sel_shifts = st.sidebar.multiselect("Shift", options=all_shifts, default=all_shifts,
                                     format_func=lambda s: CFG.SHIFT_LABELS.get(s, s))
sel_hour_range = st.sidebar.slider("Hour of day range", 0, 23, (0, 23))
st.sidebar.caption("Filters apply to every chart on this page.")

if not sel_zones:
    sel_zones = all_zones
if not sel_days:
    sel_days = all_days
if not sel_shifts:
    sel_shifts = all_shifts

hmin, hmax = sel_hour_range


def _filter_points(df):
    return df[
        df["zone_id"].isin(sel_zones)
        & df["Day"].isin(sel_days)
        & df["shift"].isin(sel_shifts)
        & df["hour"].between(hmin, hmax)
    ]


crash_f = _filter_points(crash_pts)
viol_f = _filter_points(viol_pts)

# ===========================================================================
# SECTION 1 - Spatial hotspots
# ===========================================================================
st.header("🔅 Where incidents happen")

c1, c2 = st.columns(2)

with c1:
    st.subheader("✨ Crash locations")
    if crash_f.empty:
        st.info("No crashes match the current filters.")
    elif zone_geojson is None:
        st.warning("Zone boundary data unavailable for this map.")
    else:
        fig = imaps.render_hotspot_mapbox(zone_geojson, crash_f, "Latitude", "Longitude",
                                           color=theme.CRASH_COLOR)
        st.plotly_chart(fig, use_container_width=True)
    st.info(itp.crash_hotspot_text(crash_f, sel_zones, sel_days))

with c2:
    st.subheader("✨ Traffic stop locations")
    if viol_f.empty:
        st.info("No traffic stops match the current filters.")
    elif zone_geojson is None:
        st.warning("Zone boundary data unavailable for this map.")
    else:
        fig = imaps.render_hotspot_mapbox(zone_geojson, viol_f, "Latitude", "Longitude",
                                           color=theme.VIOLATION_COLOR)
        st.plotly_chart(fig, use_container_width=True)
    st.info(itp.violation_hotspot_text(viol_f, sel_zones, sel_days))

st.divider()

# ===========================================================================
# SECTION 2 - Rate by zone (per-mile, normalizes for zone road length)
# ===========================================================================
st.header("🔅 Incident rate by zone (per mile of road)")
st.caption("Normalizing by road-mile shows which zones have disproportionately more incidents, not just more roads.")

c3, c4 = st.columns(2)

crash_pm_f = crash_pm[crash_pm["zone_id"].isin(sel_zones)]
viol_pm_f = viol_pm[viol_pm["zone_id"].isin(sel_zones)]

with c3:
    st.subheader("✨ Crashes per mile")
    agg = crash_pm_f.groupby("zone_id", as_index=False)["crashes_per_mile"].mean()
    agg["Zone"] = agg["zone_id"].map(lambda z: f"Zone {z}")
    fig = px.bar(agg.sort_values("crashes_per_mile", ascending=False), x="Zone", y="crashes_per_mile",
                 color="crashes_per_mile", color_continuous_scale=theme.RED_SEQUENTIAL, height=350)
    fig.update_layout(coloraxis_showscale=False, yaxis_title="Crashes / mile")
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.rate_by_zone_text(crash_pm_f, "crashes_per_mile", "crash rate", sel_zones))

with c4:
    st.subheader("✨ Traffic stops per mile")
    agg = viol_pm_f.groupby("zone_id", as_index=False)["violations_per_mile"].mean()
    agg["Zone"] = agg["zone_id"].map(lambda z: f"Zone {z}")
    fig = px.bar(agg.sort_values("violations_per_mile", ascending=False), x="Zone", y="violations_per_mile",
                 color="violations_per_mile", color_continuous_scale=theme.BLUE_SEQUENTIAL, height=350)
    fig.update_layout(coloraxis_showscale=False, yaxis_title="Stops / mile")
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.rate_by_zone_text(viol_pm_f, "violations_per_mile", "traffic stop rate", sel_zones))

st.divider()

# ===========================================================================
# SECTION 3 - Temporal patterns
# ===========================================================================
st.header("🔅 When incidents happen")

c5, c6 = st.columns(2)

with c5:
    st.subheader("✨ Crashes by hour of day")
    by_hour = crash_f.groupby("hour").size().reindex(range(24), fill_value=0).reset_index(name="count")
    by_hour["hour_label"] = by_hour["hour"].map(itp.HOUR_LABELS)
    fig = px.bar(by_hour, x="hour_label", y="count", color="count", color_continuous_scale=theme.RED_SEQUENTIAL, height=320)
    fig.update_layout(coloraxis_showscale=False, xaxis_title="Hour", yaxis_title="Crashes")
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.hourly_pattern_text(crash_f, "Crash frequency"))

with c6:
    st.subheader("✨ Traffic stops by hour of day")
    by_hour = viol_f.groupby("hour").size().reindex(range(24), fill_value=0).reset_index(name="count")
    by_hour["hour_label"] = by_hour["hour"].map(itp.HOUR_LABELS)
    fig = px.bar(by_hour, x="hour_label", y="count", color="count", color_continuous_scale=theme.BLUE_SEQUENTIAL, height=320)
    fig.update_layout(coloraxis_showscale=False, xaxis_title="Hour", yaxis_title="Traffic Stops")
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.hourly_pattern_text(viol_f, "Traffic stop activity"))

c7, c8 = st.columns(2)

with c7:
    st.subheader("✨ Crashes by day of week")
    by_day = crash_f.groupby("Day").size().reindex(all_days, fill_value=0).reset_index(name="count")
    fig = px.bar(by_day, x="Day", y="count", color="count", color_continuous_scale=theme.RED_SEQUENTIAL, height=320)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.day_pattern_text(crash_f, "Crash frequency"))

with c8:
    st.subheader("✨ Traffic stops by day of week")
    by_day = viol_f.groupby("Day").size().reindex(all_days, fill_value=0).reset_index(name="count")
    fig = px.bar(by_day, x="Day", y="count", color="count", color_continuous_scale=theme.BLUE_SEQUENTIAL, height=320)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.day_pattern_text(viol_f, "Traffic stop activity"))

st.divider()

# ===========================================================================
# SECTION 4 - Officer proactive-patrol capacity
# ===========================================================================
st.header("🔅 Officer capacity for proactive patrol")
st.caption(
    "After briefing, paperwork, meals, and responding to calls, this shows how much "
    "time officers actually have left for proactive patrol in each zone and shift."
)

sched_f = zone_sched[zone_sched["zone_id"].isin(sel_zones)]
sched_f = sched_f[sched_f["day_name"].isin(sel_days)]

if sched_f.empty:
    st.info("No capacity data for the current filters.")
else:
    pivot = sched_f.pivot_table(index="zone_name", columns="slot_name", values="F_zt_pct_of_shift", aggfunc="mean")
    # Order columns by weekday/shift if all slots present
    slot_order = [f"{d[:3]}_{s}" for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] for s in ["Day", "Eve", "Ngt"]]
    ordered_cols = [c for c in slot_order if c in pivot.columns]
    if ordered_cols:
        pivot = pivot[ordered_cols]
    fig = px.imshow(pivot, color_continuous_scale=theme.GREY_SEQUENTIAL, aspect="auto", height=380,
                     labels=dict(color="% shift available"))
    st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    st.info(itp.capacity_text(sched_f, sel_zones))

st.divider()

# ===========================================================================
# SECTION 5 - Current approach misalignment (glyph map)
# ===========================================================================
st.header("🔅 How well does today's patrol match demand?")
st.caption(
    "This compares the current Uniform Plan patrol schedule against where crashes and "
    "traffic stops actually happen, one day at a time. Each zone's rose shows the "
    "mismatch for Day, Evening, and Night shifts that day; longer, darker wedges mean "
    "a bigger mismatch. Pick a day below to see how the pattern shifts."
)

gap_long = dl.build_uniform_gap_long()
if gap_long.empty:
    st.info("No misalignment data available.")
else:
    glyph_day = st.radio(
        "Day to show", options=CFG.DAY_ORDER, index=1, horizontal=True,
        format_func=lambda d: d[:3], key="glyph_day_selector",
    )
    glyph_day_code = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
                       "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}[glyph_day]
    zone_gdf_native = geo_utils.load_zone_gdf_native()
    glyph_png = static_maps.render_glyph_map(
        zone_gdf, gap_long, gdf_native=zone_gdf_native,
        title="Where Uniform Patrol Misses Demand",
        selected_day=glyph_day_code,
    )
    st.image(glyph_png, use_container_width=True)
    st.caption("🟣 Purple = under-patrolled relative to demand    🟠 Orange = over-patrolled relative to demand")
    zsum_f = zone_summary[zone_summary["Zone"].apply(lambda z: CFG.zone_label_to_id(z) in sel_zones)]
    if not zsum_f.empty:
        st.info(itp.misalignment_text(zsum_f, sel_zones))
