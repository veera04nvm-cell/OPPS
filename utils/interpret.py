"""
Plain-language, filter-reactive interpretation text generators.
Each function takes the CURRENTLY FILTERED dataframe (plus small context)
and returns a short, officer-facing sentence or two. No jargon, no stats
terminology - just "what does this mean for patrol."
"""
import pandas as pd

from . import config as CFG

HOUR_LABELS = {h: f"{h % 12 or 12}{'AM' if h < 12 else 'PM'}" for h in range(24)}


def _zone_scope_phrase(zone_ids):
    all_zones = set(CFG.ZONE_IDS)
    if zone_ids is None or set(zone_ids) == all_zones or len(zone_ids) == 0:
        return "Citywide (all 8 zones)"
    if len(zone_ids) == 1:
        return f"Zone {zone_ids[0]}"
    return "Zones " + ", ".join(str(z) for z in sorted(zone_ids))


def _day_scope_phrase(days):
    if days is None or len(days) == 0 or len(days) == 7:
        return "across the full week"
    if len(days) == 1:
        return f"on {days[0]}s"
    return "on " + ", ".join(days)


def crash_hotspot_text(df: pd.DataFrame, zone_ids, days) -> str:
    scope = _zone_scope_phrase(zone_ids)
    dscope = _day_scope_phrase(days)
    if df.empty:
        return f"No recorded crashes match the current filters ({scope}, {dscope})."
    n = len(df)
    top_zone = df["zone_id"].value_counts().idxmax()
    top_zone_n = df["zone_id"].value_counts().max()
    top_hour = df["hour"].value_counts().idxmax()
    return (
        f"**{n} crashes** recorded for {scope}, {dscope}. "
        f"Zone {top_zone} accounts for the most ({top_zone_n} crashes). "
        f"Crashes are most frequent around **{HOUR_LABELS.get(int(top_hour), top_hour)}** - "
        f"consider prioritizing visible patrol presence near that time."
    )


def violation_hotspot_text(df: pd.DataFrame, zone_ids, days) -> str:
    scope = _zone_scope_phrase(zone_ids)
    dscope = _day_scope_phrase(days)
    if df.empty:
        return f"No recorded stops match the current filters ({scope}, {dscope})."
    n = len(df)
    top_zone = df["zone_id"].value_counts().idxmax()
    top_zone_n = df["zone_id"].value_counts().max()
    top_hour = df["hour"].value_counts().idxmax()
    return (
        f"**{n} traffic stops** recorded for {scope}, {dscope}. "
        f"Zone {top_zone} has the most enforcement activity ({top_zone_n} stops), "
        f"concentrated around **{HOUR_LABELS.get(int(top_hour), top_hour)}**."
    )


def rate_by_zone_text(df: pd.DataFrame, value_col: str, label: str, zone_ids) -> str:
    if df.empty:
        return "No data available for the selected zones."
    agg = df.groupby("zone_id")[value_col].mean().sort_values(ascending=False)
    if agg.empty:
        return "No data available for the selected zones."
    top_zone = agg.index[0]
    top_val = agg.iloc[0]
    scope = _zone_scope_phrase(zone_ids)
    return (
        f"Within {scope}, **Zone {top_zone}** has the highest {label} "
        f"({top_val:.1f} per mile) - this zone's road segments see disproportionately "
        f"more incidents relative to their length and may warrant closer attention."
    )


def hourly_pattern_text(df: pd.DataFrame, label: str) -> str:
    if df.empty:
        return "No data available for the selected filters."
    by_hour = df.groupby("hour").size()
    if by_hour.empty:
        return "No data available for the selected filters."
    peak_hour = int(by_hour.idxmax())
    peak_n = int(by_hour.max())
    is_night = peak_hour >= 22 or peak_hour < 6
    tod = "overnight" if is_night else ("morning" if peak_hour < 12 else "afternoon/evening")
    return (
        f"{label} peaks at **{HOUR_LABELS.get(peak_hour, peak_hour)}** ({peak_n} incidents at that hour), "
        f"during the {tod} window. Shift schedules should weight coverage toward this period."
    )


def day_pattern_text(df: pd.DataFrame, label: str) -> str:
    if df.empty or "Day" not in df.columns:
        return "No data available for the selected filters."
    by_day = df.groupby("Day").size()
    if by_day.empty:
        return "No data available for the selected filters."
    peak_day = by_day.idxmax()
    peak_n = int(by_day.max())
    return (
        f"{label} is highest on **{peak_day}** ({peak_n} incidents). "
        f"Weekend vs. weekday staffing levels should reflect this pattern."
    )


def capacity_text(df: pd.DataFrame, zone_ids) -> str:
    if df.empty:
        return "No capacity data available for the selected zones."
    avg_pct = df["F_zt_pct_of_shift"].mean()
    lowest_row = df.loc[df["F_zt_pct_of_shift"].idxmin()]
    scope = _zone_scope_phrase(zone_ids)
    return (
        f"On average, officers in {scope} have **{avg_pct:.0f}%** of their shift "
        f"available for proactive patrol after briefing, paperwork, meals, and call load. "
        f"The tightest capacity is {lowest_row.get('zone_name', '')} during "
        f"{lowest_row.get('slot_name', '')} ({lowest_row['F_zt_pct_of_shift']:.0f}% available) - "
        f"officers there have the least discretionary patrol time."
    )


def misalignment_text(df: pd.DataFrame, zone_ids) -> str:
    """df expects columns: zone_id/zone, Equity gap (s-r) (from Per_Zone_Summary)."""
    gap_col = "Equity gap (s-r)"
    if df.empty or gap_col not in df.columns:
        return "No misalignment data available for the selected zones."
    worst_under = df.loc[df[gap_col].idxmin()]
    worst_over = df.loc[df[gap_col].idxmax()]
    scope = _zone_scope_phrase(zone_ids)
    return (
        f"Under the current **equal-split (uniform)** deployment in {scope}, "
        f"**{worst_under['Zone']}** is the most under-patrolled relative to its demand "
        f"(gap {worst_under[gap_col]:+.3f}), while **{worst_over['Zone']}** receives more "
        f"patrol time than its demand justifies (gap {worst_over[gap_col]:+.3f}). "
        f"A demand-based allocation would shift coverage from over- to under-served zones."
    )
