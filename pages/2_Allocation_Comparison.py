import pandas as pd
import streamlit as st

from utils import config as CFG
from utils import data_loader as dl
from utils import geo_utils
from utils import interactive_maps as imaps
from utils import theme

st.set_page_config(page_title="Allocation Comparison", page_icon="🗺️", layout="wide")
theme.inject_theme()
theme.masthead(
    title="🔅 Allocation Comparison",
    subtitle="Compare how three patrol strategies distribute officers across Bartlett's "
             "8 zones, and how well each matches actual demand.",
)

MODELS = ["Uniform", "Static", "Dynamic"]

zone_gdf, gdf_is_real = geo_utils.load_zone_gdf()
zone_geojson, zone_field, geojson_status = geo_utils.load_zone_shapes()
gis_all = dl.load_gis_alloc_all()

if gis_all.empty:
    st.error("No allocation map data found. Check that gis_alloc_*.csv files are in the data/ folder.")
    st.stop()
if zone_geojson is None:
    st.error("Zone boundary shapefile could not be loaded. Maps cannot render without it.")
    st.stop()

combos = dl.gis_alloc_available_dates_shifts()  # list of (Date, Day, Slot_name)

# ---------------------------------------------------------------------------
# Date / shift selectors
# ---------------------------------------------------------------------------
dates_available = sorted(set(c[0] for c in combos))
date_labels = {d: pd.Timestamp(d).strftime("%A, %b %d, %Y") for d in dates_available}

with st.container(key="allocation_filters"):
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        sel_date = st.selectbox("Date", options=dates_available, format_func=lambda d: date_labels[d])
    with col_sel2:
        shifts_for_date = sorted(set(c[2] for c in combos if c[0] == sel_date))
        shift_label_map = {s: CFG.SHIFT_LABELS.get(s.split("_")[-1], s) for s in shifts_for_date}
        sel_shift = st.selectbox("Shift", options=shifts_for_date, format_func=lambda s: shift_label_map.get(s, s))

day_name = [c[1] for c in combos if c[0] == sel_date and c[2] == sel_shift][0]
st.markdown(f"**Showing:** {date_labels[sel_date]} - {shift_label_map.get(sel_shift, sel_shift)}")

subset = gis_all[(gis_all["Date"] == sel_date) & (gis_all["Slot_name"] == sel_shift)].copy()

if subset.empty:
    st.warning("No data for this date/shift combination.")
    st.stop()

# ===========================================================================
# SECTION 1 - Officer allocation per model, shown as patrol units placed
# within each zone (not exact vehicle GPS - a representative icon count
# per zone, N = the model's recommended officer count).
# ===========================================================================
st.header("🔅 Recommended officer placement by zone")
st.caption(
    "Each marker represents one recommended patrol officer, placed at a random point "
    "within its assigned zone - not an exact vehicle location, just a visual count "
    "per zone for this date and shift."
)

tabs = st.tabs([CFG.MODEL_SHORT_NAMES[m] for m in MODELS])
for tab, model in zip(tabs, MODELS):
    with tab:
        col_map, col_table = st.columns([2, 1], vertical_alignment="center")
        val_col = f"x_{model}"
        with col_map:
            counts_by_zone = dict(zip(subset["zone_id"], subset[val_col]))
            fig = imaps.render_car_placement_mapbox(
                zone_geojson, zone_gdf, counts_by_zone,
                title=CFG.MODEL_DISPLAY_NAMES[model],
                seed_prefix=f"{sel_date}-{sel_shift}-{model}",
            )
            st.plotly_chart(fig, width='stretch')
        with col_table:
            tbl = subset[["Zone", val_col, "Demand_share_pct"]].sort_values(val_col, ascending=False)
            tbl.columns = ["Zone", "Officers", "Demand Share %"]
            st.table(tbl.set_index("Zone"))
        st.caption(CFG.MODEL_DISPLAY_NAMES[model] + " - " + {
            "Uniform": "assigns the same number of officers to every zone regardless of demand.",
            "Static": "assigns officers based on a fixed plan built from historical demand patterns.",
            "Dynamic": "adjusts officer counts based on recent, day-specific demand patterns.",
        }[model])

st.divider()

# ===========================================================================
# SECTION 2 - Demand-alignment gap per model
# ===========================================================================
st.header("🔅 How well does each plan match demand?")
st.caption(
    "🟣 Purple = zone is **under-patrolled** relative to its demand share this shift.   "
    "🟠 Orange = zone is **over-patrolled** relative to its demand share this shift."
)

gap_cols = {m: f"Gap_{m}_pp" for m in MODELS}
all_gap_vals = pd.concat([subset[c] for c in gap_cols.values() if c in subset.columns])
gap_abs_max = float(all_gap_vals.abs().max()) if not all_gap_vals.empty else 10

tabs2 = st.tabs([CFG.MODEL_SHORT_NAMES[m] for m in MODELS])
for tab, model in zip(tabs2, MODELS):
    with tab:
        gap_col = gap_cols[model]
        if gap_col not in subset.columns:
            st.info("Gap data not available for this model.")
            continue
        col_map, col_table = st.columns([2, 1], vertical_alignment="center")
        with col_map:
            values_by_zone = dict(zip(subset["zone_id"], subset[gap_col]))
            fig = imaps.render_gap_choropleth_mapbox(
                zone_geojson, values_by_zone, colorscale=CFG.GAP_COLORSCALE,
                title=f"{CFG.MODEL_SHORT_NAMES[model]} - Coverage Gap",
                legend_label="Gap (pp)",
            )
            st.plotly_chart(fig, width='stretch')
        with col_table:
            tbl = subset[["Zone", gap_col]].sort_values(gap_col)
            tbl.columns = ["Zone", "Gap (pp)"]
            st.table(tbl.set_index("Zone"))

        worst_row = subset.loc[subset[gap_col].idxmin()]
        best_row = subset.loc[subset[gap_col].idxmax()]
        st.info(
            f"Under **{CFG.MODEL_SHORT_NAMES[model]}** for this shift, **{worst_row['Zone']}** is the most "
            f"under-covered ({worst_row[gap_col]:+.1f} percentage points below its demand share), while "
            f"**{best_row['Zone']}** is the most over-covered ({best_row[gap_col]:+.1f} pp above)."
        )

st.divider()
st.subheader("✨ Full data for this date/shift")
st.table(
    subset[["Zone", "Demand_share_pct", "Uniform_patrol_pct", "Static_patrol_pct", "Dynamic_patrol_pct",
            "Gap_Uniform_pp", "Gap_Static_pp", "Gap_Dynamic_pp", "x_Uniform", "x_Static", "x_Dynamic"]]
    .sort_values("Zone").set_index("Zone")
)
