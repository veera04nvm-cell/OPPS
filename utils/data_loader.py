"""
All data loading + light preprocessing for the dashboard, cached so the
app stays snappy across filter changes.
"""
import glob
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from . import config as CFG


# ---------------------------------------------------------------------------
# Page I data — crash / violation / capacity sources
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_crash_points():
    df = pd.read_csv(CFG.DATA_DIR / "crash_points.csv")
    return df


@st.cache_data(show_spinner=False)
def load_violation_points():
    df = pd.read_csv(CFG.DATA_DIR / "violation_points.csv")
    return df


@st.cache_data(show_spinner=False)
def load_crashes_per_mile():
    return pd.read_csv(CFG.DATA_DIR / "crashes_per_mile_by_zone.csv")


@st.cache_data(show_spinner=False)
def load_violations_per_mile():
    return pd.read_csv(CFG.DATA_DIR / "violations_per_mile_by_zone.csv")


@st.cache_data(show_spinner=False)
def load_zone_schedule():
    df = pd.read_csv(CFG.DATA_DIR / "zone_schedule.csv")
    df["zone_id"] = df["zone_idx"].astype(int) + 1
    return df


@st.cache_data(show_spinner=False)
def load_theil_workbook():
    """Returns a dict of cleaned dataframes keyed by sheet purpose."""
    path = CFG.DATA_DIR / "theil_uniform_analysis.xlsx"
    xl = pd.ExcelFile(path)

    out = {}

    # Per-zone summary (mean Theil H_z, demand share, patrol share, gap)
    out["zone_summary"] = xl.parse("Per_Zone_Summary", header=2)

    # Full per-zone-per-slot Theil matrix (rows=zones, cols=21 slots)
    pzps = xl.parse("Per_Zone_Per_Slot", header=2)
    pzps = pzps.rename(columns={pzps.columns[0]: "Zone"})
    out["zone_slot_theil"] = pzps

    # Uniform gap analysis: demand share (block 1) vs patrol share vs gap, by zone x slot.
    # This sheet has an extra "BLOCK 1: ..." label row before the real header
    # ("Zone \ Slot", "Mon_Day", ...), so auto-detect the header row instead
    # of assuming a fixed offset.
    raw_probe = xl.parse("Uniform_Gap_Analysis", header=None)
    header_row = None
    for i in range(min(10, len(raw_probe))):
        first_cell = str(raw_probe.iloc[i, 0])
        if "zone" in first_cell.lower() and "slot" in first_cell.lower():
            header_row = i
            break
    if header_row is None:
        header_row = 3  # fallback to previous assumption
    uga = xl.parse("Uniform_Gap_Analysis", header=header_row)
    uga = uga.rename(columns={uga.columns[0]: "Zone"})
    out["uniform_gap_raw"] = uga

    # t-test summary
    out["t_test"] = xl.parse("T_Test_Results", header=2)

    # Sensitivity comparison table
    out["sensitivity"] = xl.parse("Sensitivity_Comparison", header=2)

    return out


@st.cache_data(show_spinner=False)
def build_uniform_gap_long():
    """
    Reshapes the Uniform_Gap_Analysis sheet (3 stacked blocks: demand share,
    uniform patrol share, gap) into a tidy long dataframe:
    zone, slot_name, demand_share, patrol_share, gap
    """
    raw = load_theil_workbook()["uniform_gap_raw"]
    slot_cols = [c for c in raw.columns if c not in
                 ("Zone", "Zone mean", "Zone std", "Zone min", "Zone max")]

    # The sheet stacks 3 blocks of 8 zone-rows each, separated by header rows
    # (identifiable because 'Zone' col holds 'Zone 1'.."Zone 8" only in data rows)
    zone_mask = raw["Zone"].astype(str).str.match(r"^Zone \d+$", na=False)
    zone_rows = raw[zone_mask].reset_index(drop=True)

    n_zones = 8
    demand_block = zone_rows.iloc[0:n_zones].reset_index(drop=True)
    patrol_block = zone_rows.iloc[n_zones:2 * n_zones].reset_index(drop=True)
    gap_block = zone_rows.iloc[2 * n_zones:3 * n_zones].reset_index(drop=True)

    records = []
    for i in range(n_zones):
        zone_label = demand_block.loc[i, "Zone"]
        zone_id = CFG.zone_label_to_id(zone_label)
        for slot in slot_cols:
            records.append({
                "zone_id": zone_id,
                "zone": zone_label,
                "slot_name": slot,
                "demand_share": pd.to_numeric(demand_block.loc[i, slot], errors="coerce"),
                "patrol_share": pd.to_numeric(patrol_block.loc[i, slot], errors="coerce") if i < len(patrol_block) else None,
                "gap": pd.to_numeric(gap_block.loc[i, slot], errors="coerce") if i < len(gap_block) else None,
            })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Page II data — allocation results (uniform / static / dynamic) + GIS gap
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_static_alloc():
    return pd.read_csv(CFG.DATA_DIR / "static_alloc.csv")


@st.cache_data(show_spinner=False)
def load_dynamic_alloc_all():
    """Concatenates all dynamic_alloc_<date>_*.csv files, tagging with date."""
    files = sorted(glob.glob(str(CFG.DATA_DIR / "dynamic_alloc_*.csv")))
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def load_gis_alloc_all():
    """
    Concatenates all gis_alloc_<date>_<Day>_<Shift>.csv files into one
    tidy dataframe with a zone_id column added.
    """
    files = sorted(glob.glob(str(CFG.DATA_DIR / "gis_alloc_*.csv")))
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["zone_id"] = df["Zone"].apply(CFG.zone_label_to_id)
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out


@st.cache_data(show_spinner=False)
def gis_alloc_available_dates_shifts():
    """Returns sorted unique (date, day_name, slot_name) combos available."""
    df = load_gis_alloc_all()
    if df.empty:
        return []
    combos = df[["Date", "Day", "Slot_name"]].drop_duplicates()
    combos = combos.sort_values(["Date", "Slot_name"])
    return list(combos.itertuples(index=False, name=None))
