"""
Central configuration for the Bartlett PD Patrol Allocation Dashboard.
Edit the constants below if your folder layout or shapefile field names differ.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Folder containing the zone-boundary shapefile set
# (PATROL_DISTRICTS_2025.shp / .dbf / .shx / .prj all live in this folder)
SHAPEFILE_DIR = BASE_DIR / "PATROL_DISTRICTS_2025"
SHAPEFILE_NAME = "BARTLETT_PATROL_DISTRICTS_2025.shp"

# The shapefile's zone-identifier field. Common candidates are tried
# automatically in geo_utils.load_zone_shapes(); override here if you know
# the exact field name to skip the auto-detection step.
SHAPEFILE_ZONE_FIELD_OVERRIDE = None  # e.g. "ZONE_ID" or "PATROL_ZON"

# ---------------------------------------------------------------------------
# Zone naming - the source files use three different zone key conventions.
# This is the single source of truth mapping between them.
# ---------------------------------------------------------------------------
ZONE_IDS = list(range(1, 9))  # 1..8, matches x_alloc / gis_alloc / zone_schedule zone_id

ZONE_LABELS = {i: f"Zone {i}" for i in ZONE_IDS}          # matches gis_alloc "Zone" column
ZONE_LABELS_US = {i: f"Zone_{i}" for i in ZONE_IDS}         # matches zone_schedule "zone_name"

def zone_label_to_id(label: str) -> int:
    """'Zone 3' or 'Zone_3' -> 3"""
    digits = "".join(ch for ch in str(label) if ch.isdigit())
    return int(digits) if digits else None

# ---------------------------------------------------------------------------
# Shift / slot ordering
# ---------------------------------------------------------------------------
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
            "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
SHIFT_ORDER = ["Day", "Eve", "Ngt"]
SHIFT_LABELS = {"Day": "Day Shift (6:30 AM - 2:30 PM)",
                "Eve": "Evening Shift (2:30 PM - 10:30 PM)",
                "Ngt": "Night Shift (10:30 PM - 6:30 AM)"}


def hour_to_shift(hour: int) -> str:
    """Buckets an hour-of-day (0-23) into Day/Eve/Ngt, matching SHIFT_LABELS."""
    if 6 <= hour < 14:
        return "Day"
    elif 14 <= hour < 22:
        return "Eve"
    else:
        return "Ngt"

MODEL_COLORS = {
    "Uniform": "#8c8c8c",
    "Static": "#1f77b4",
    "Dynamic": "#2ca02c",
}

# Officer-facing plain-language names for the three allocation strategies.
# Internal/model code always uses Uniform/Static/Dynamic; the UI shows these.
MODEL_DISPLAY_NAMES = {
    "Uniform": "Uniform Plan (Current Practice)",
    "Static": "Static Plan (Demand-Based)",
    "Dynamic": "Dynamic Plan (Demand-Based, Day-of)",
}
MODEL_SHORT_NAMES = {
    "Uniform": "Uniform Plan",
    "Static": "Static Plan",
    "Dynamic": "Dynamic Plan",
}

# Diverging color scale for under/over coverage maps (purple = under, orange = over)
GAP_COLORSCALE = "PuOr_r"  # reversed so negative(purple)=under, positive(orange)=over

# ---------------------------------------------------------------------------
# App-wide display text
# ---------------------------------------------------------------------------
APP_TITLE = "Bartlett PD - Patrol Allocation Dashboard"
DEPLOYMENT_WINDOW = "December 25 – 31, 2024"
