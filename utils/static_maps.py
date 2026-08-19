"""
Self-contained static map rendering (matplotlib + geopandas).

No external network calls at render time — the shapefile lives locally,
and the patrol-car icon is a bundled PNG (assets/patrol_car.png) rather
than fetched or drawn from an emoji font glyph (matplotlib's default font
has no color-emoji support, so text-based emoji renders as an empty box).

Visual language: thin black zone boundaries, white zone fill (default /
no-data), a richer gamma-adjusted PuOr diverging scale for coverage-gap
maps, and light-weight (non-bold) zone number labels.
"""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

BOUNDARY_COLOR = "#1A1A1A"
BOUNDARY_WIDTH = 1.0
DEFAULT_FILL = "#FFFFFF"
DEFAULT_FILL_ALPHA = 0.35  # semi-transparent so the OSM basemap shows through
FIG_DPI = 150
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CAR_ICON_PATH = ASSETS_DIR / "patrol_car.png"

# A livelier, more saturated diverging palette than stock PuOr — deep violet
# through white to a warm amber, tuned for a punchier look on top of the
# translucent OSM basemap.
MODERN_DIVERGING = mcolors.LinearSegmentedColormap.from_list(
    "modern_diverging",
    ["#3B0764", "#8B5CF6", "#E9D8FD", "#FFFFFF", "#FDE8CB", "#F59E0B", "#9A3412"],
)


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _base_axes(gdf, figsize=(6.4, 5.6)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig, ax


_TILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _try_add_basemap(ax, gdf_crs) -> tuple:
    """
    Bakes real OpenStreetMap tile imagery directly into the static figure
    via contextily, so the map has genuine street/place context underneath
    the zone overlay — done server-side at render time (not dependent on
    the viewer's browser fetching tiles live).

    Sends a real browser User-Agent (OSM's tile usage policy blocks
    requests with generic/default library User-Agents, returning 403).

    Returns (success: bool, error_detail: str | None). On failure, the
    actual exception is also printed to stderr (visible in the terminal
    running `streamlit run`) so a real network/library problem is
    diagnosable rather than hidden behind a generic message.
    """
    try:
        import contextily as cx
        cx.add_basemap(ax, crs=gdf_crs, source=cx.providers.OpenStreetMap.Mapnik,
                        attribution=False, zorder=0, headers=_TILE_HEADERS)
        return True, None
    except Exception as e:
        import sys
        print(f"[static_maps] Basemap tile fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False, f"{type(e).__name__}: {str(e)[:80]}"


def _basemap_caveat(ax, error_detail: str = None):
    """Small corner note shown only when the basemap tile fetch failed."""
    msg = "Basemap unavailable — zone outlines only"
    if error_detail:
        msg += f" ({error_detail})"
    ax.annotate(msg, xy=(0.01, 0.01), xycoords="axes fraction", fontsize=6.5, color="#B11313",
                ha="left", va="bottom", style="italic")


class DivergingPowerNorm(mcolors.Normalize):
    """
    Diverging norm with a gamma<1 stretch so small-magnitude values pull
    saturated color in sooner (instead of clustering pale near the center),
    while 0 still maps to true white and sign is preserved. Produces a
    noticeably richer, less washed-out gradient than a plain linear
    TwoSlopeNorm for the same data.
    """
    def __init__(self, vmax, gamma=0.55, clip=False):
        vmax = max(float(vmax), 1e-9)
        super().__init__(vmin=-vmax, vmax=vmax, clip=clip)
        self.gamma = gamma

    def __call__(self, value, clip=None):
        value = np.ma.asarray(value, dtype=float)
        mag = (np.abs(value) / self.vmax) ** self.gamma
        result = 0.5 + 0.5 * np.sign(value) * mag
        return np.ma.masked_array(result)

    def inverse(self, value):
        value = np.asarray(value, dtype=float)
        s = 2 * value - 1
        return np.sign(s) * (np.abs(s) ** (1.0 / self.gamma)) * self.vmax


def render_zone_base_map(gdf, title: str = "") -> bytes:
    """OSM basemap with semi-transparent zone fill and thin boundaries."""
    fig, ax = _base_axes(gdf)
    ok, err_detail = _try_add_basemap(ax, gdf.crs)
    gdf.plot(ax=ax, facecolor=DEFAULT_FILL, edgecolor=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH,
             alpha=DEFAULT_FILL_ALPHA if ok else 1.0, zorder=1)
    for _, row in gdf.iterrows():
        c = row.geometry.centroid
        ax.annotate(str(int(row["zone_id"])), (c.x, c.y), ha="center", va="center",
                    fontsize=13, fontweight="normal", color="#2B2B2B",
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=3)
    if not ok:
        _basemap_caveat(ax, err_detail)
    if title:
        ax.set_title(title, fontsize=13, fontweight="normal", pad=10)
    return _fig_to_bytes(fig)


def _get_car_icon():
    """Loads the bundled patrol-car PNG once per process."""
    if not hasattr(_get_car_icon, "_cache"):
        if CAR_ICON_PATH.exists():
            _get_car_icon._cache = plt.imread(CAR_ICON_PATH)
        else:
            _get_car_icon._cache = None
    return _get_car_icon._cache


def _draw_car_icon(ax, x, y, zoom=0.22):
    """
    Places the bundled patrol-car icon (a real Twemoji police-car PNG,
    assets/patrol_car.png) at (x, y) as a raster image via OffsetImage —
    emoji text glyphs don't render reliably in matplotlib (no color-font
    support), so this uses an actual image instead of a unicode character.
    """
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    img = _get_car_icon()
    if img is None:
        # Bundled icon missing for some reason — fall back to a small dot
        # rather than silently drawing nothing.
        ax.plot(x, y, marker="o", markersize=5, color="#1A2233")
        return
    imagebox = OffsetImage(img, zoom=zoom)
    ab = AnnotationBbox(imagebox, (x, y), frameon=False, pad=0, zorder=6)
    ax.add_artist(ab)


def render_car_placement_map(gdf, counts_by_zone: dict, title: str = "", seed_prefix: str = "") -> bytes:
    """
    OSM basemap with semi-transparent zone fill, thin boundary, patrol-car
    icons placed at true random points sampled inside each zone's actual
    polygon (rejection sampling against the real geometry) — count per
    zone = counts_by_zone[zone_id].
    """
    fig, ax = _base_axes(gdf)
    ok, err_detail = _try_add_basemap(ax, gdf.crs)
    gdf.plot(ax=ax, facecolor=DEFAULT_FILL, edgecolor=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH,
             alpha=DEFAULT_FILL_ALPHA if ok else 1.0, zorder=1)

    minx, miny, maxx, maxy = gdf.total_bounds
    span = max(maxx - minx, maxy - miny)
    # Icon zoom scales gently with figure size / zone density so icons stay
    # legible without overwhelming small zones.
    icon_zoom = 0.20

    for _, row in gdf.iterrows():
        zid = int(row["zone_id"])
        c = row.geometry.centroid
        ax.annotate(f"Zone {zid}", (c.x, c.y), ha="center", va="top", xytext=(0, -14),
                    textcoords="offset points", fontsize=8.5, fontweight="normal", color="#333333",
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=3)

        n = int(counts_by_zone.get(zid, 0) or 0)
        if n <= 0:
            continue
        rng = np.random.default_rng(seed=abs(hash(f"{seed_prefix}-{zid}")) % (2**32))
        zminx, zminy, zmaxx, zmaxy = row.geometry.bounds
        pts = []
        attempts = 0
        while len(pts) < n and attempts < n * 60 + 200:
            attempts += 1
            x = rng.uniform(zminx, zmaxx)
            y = rng.uniform(zminy, zmaxy)
            from shapely.geometry import Point
            p = Point(x, y)
            if row.geometry.contains(p):
                pts.append((x, y))
        for (x, y) in pts:
            _draw_car_icon(ax, x, y, zoom=icon_zoom)

    if not ok:
        _basemap_caveat(ax, err_detail)
    if title:
        ax.set_title(title, fontsize=13, fontweight="normal", pad=10)
    return _fig_to_bytes(fig)


def render_choropleth_map(gdf, values_by_zone: dict, cmap=None, vmin=None, vmax=None,
                           title: str = "", legend_label: str = "", diverging: bool = True,
                           gamma: float = 0.6) -> bytes:
    """
    OSM basemap with zones filled by value (semi-transparent so streets
    show through), thin boundary retained regardless of fill. Uses
    DivergingPowerNorm (gamma<1) for diverging data by default, and the
    livelier MODERN_DIVERGING palette unless a different cmap is passed.
    """
    if cmap is None:
        cmap = MODERN_DIVERGING
    fig, ax = _base_axes(gdf)
    ok, err_detail = _try_add_basemap(ax, gdf.crs)
    plot_df = gdf.copy()
    plot_df["_val"] = plot_df["zone_id"].map(values_by_zone)

    if vmin is None:
        vmin = plot_df["_val"].min()
    if vmax is None:
        vmax = plot_df["_val"].max()
    if diverging:
        absmax = max(abs(vmin), abs(vmax), 1e-9)
        norm = DivergingPowerNorm(absmax, gamma=gamma)
    else:
        norm = None

    plot_df.plot(ax=ax, column="_val", cmap=cmap, norm=norm, vmin=None if diverging else vmin,
                 vmax=None if diverging else vmax, edgecolor=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH,
                 alpha=0.8 if ok else 1.0, missing_kwds={"color": DEFAULT_FILL}, zorder=1)

    for _, row in gdf.iterrows():
        c = row.geometry.centroid
        val = values_by_zone.get(int(row["zone_id"]))
        label = f"{int(row['zone_id'])}\n{val:.2f}" if val is not None else str(int(row["zone_id"]))
        ax.annotate(label, (c.x, c.y), ha="center", va="center", fontsize=9.5, fontweight="normal",
                    color="#1A1A1A", path_effects=[pe.withStroke(linewidth=2.5, foreground="white")], zorder=3)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.75, pad=0.02)
    if legend_label:
        cbar.set_label(legend_label, fontsize=9)

    if not ok:
        _basemap_caveat(ax, err_detail)
    if title:
        ax.set_title(title, fontsize=13, fontweight="normal", pad=10)
    return _fig_to_bytes(fig)


def render_hotspot_map(gdf, lats, lons, color: str, title: str = "") -> bytes:
    """OSM basemap with individual incident points scattered on top."""
    fig, ax = _base_axes(gdf)
    ok, err_detail = _try_add_basemap(ax, gdf.crs)
    gdf.plot(ax=ax, facecolor=DEFAULT_FILL, edgecolor=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH,
             alpha=DEFAULT_FILL_ALPHA if ok else 1.0, zorder=1)
    if len(lats) > 0:
        ax.scatter(lons, lats, s=7, c=color, alpha=0.7, linewidths=0, zorder=2)
    for _, row in gdf.iterrows():
        c = row.geometry.centroid
        ax.annotate(str(int(row["zone_id"])), (c.x, c.y), ha="center", va="center",
                    fontsize=11, fontweight="normal", color="#333333", alpha=0.8,
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=3)
    # Clip the view to the zone boundaries (+ small pad) rather than
    # auto-scaling to every scatter point — a single mis-geocoded outlier
    # in the source data would otherwise stretch the whole frame and
    # shrink the actual area of interest down to a corner.
    minx, miny, maxx, maxy = gdf.total_bounds
    padx, pady = (maxx - minx) * 0.06, (maxy - miny) * 0.06
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    if not ok:
        _basemap_caveat(ax, err_detail)
    if title:
        ax.set_title(title, fontsize=13, fontweight="normal", pad=10)
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Glyph / rose map
# ---------------------------------------------------------------------------
_SHIFT_ORDER = ["Day", "Eve", "Ngt"]
_DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def render_glyph_map_simple(gdf, gap_long_df: pd.DataFrame,
                             title: str = "Spatiotemporal Patrol Allocation Deviation") -> bytes:
    """
    Fallback glyph map for when the real shapefile isn't available (i.e.
    gdf is the lat/lon Voronoi approximation). See render_glyph_map_pro
    for the full version used with the real shapefile.
    """
    from matplotlib.colors import Normalize
    import matplotlib.cm as cm

    fig, ax = _base_axes(gdf, figsize=(9.5, 8))
    gdf.plot(ax=ax, facecolor=DEFAULT_FILL, edgecolor=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH)

    all_gaps = gap_long_df["gap"].dropna()
    gmax = float(all_gaps.abs().max()) if not all_gaps.empty else 1.0
    norm = Normalize(vmin=-gmax, vmax=gmax)
    cmap = cm.get_cmap("PuOr_r")

    minx, miny, maxx, maxy = gdf.total_bounds
    span = max(maxx - minx, maxy - miny)
    inset_size_data = span * 0.13
    label_offset_data = span * 0.028

    n_slots = len(_DAY_ORDER) * len(_SHIFT_ORDER)
    slot_angle = 360.0 / n_slots

    for _, row in gdf.iterrows():
        zid = int(row["zone_id"])
        c = row.geometry.centroid
        zone_gaps = gap_long_df[gap_long_df["zone_id"] == zid].set_index("slot_name")["gap"]

        disp = ax.transData.transform((c.x, c.y))
        fig_pt = fig.transFigure.inverted().transform(disp)
        inset_disp_size = ax.transData.transform((minx + inset_size_data, miny))[0] - ax.transData.transform((minx, miny))[0]
        inset_fig_w = inset_disp_size / fig.bbox.width
        inset_fig_h = inset_disp_size / fig.bbox.height
        iax = fig.add_axes([fig_pt[0] - inset_fig_w / 2, fig_pt[1] - inset_fig_h / 2, inset_fig_w, inset_fig_h],
                            projection="polar")
        iax.set_theta_zero_location("N")
        iax.set_theta_direction(-1)
        iax.set_xticks([])
        iax.set_yticks([])
        iax.spines["polar"].set_visible(False)
        iax.patch.set_alpha(0.0)

        slot_i = 0
        for day in _DAY_ORDER:
            for shift in _SHIFT_ORDER:
                slot_name = f"{day}_{shift}"
                gap_val = zone_gaps.get(slot_name, 0.0)
                if pd.isna(gap_val):
                    gap_val = 0.0
                theta = np.radians(slot_i * slot_angle)
                width = np.radians(slot_angle * 0.92)
                height = max(abs(gap_val), 0.01)
                color = cmap(norm(gap_val))
                iax.bar(theta, height, width=width, bottom=0, color=color, edgecolor="white", linewidth=0.3)
                slot_i += 1
        iax.set_ylim(0, gmax if gmax > 0 else 1)

        _, zminy, _, _ = row.geometry.bounds
        room_below = max(c.y - zminy - span * 0.01, span * 0.01)
        offset = min(inset_size_data / 2 + label_offset_data, room_below * 0.85)
        ax.text(c.x, c.y - offset, f"Zone {zid}",
                ha="center", va="top", fontsize=9.5, fontweight="normal", color="#262626",
                path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.03)
    cbar.set_label("Allocation deviation from target patrol level", fontsize=9)

    ax.set_title(title, fontsize=14, fontweight="normal", pad=32)
    ax.text(0.0, 1.045, "Each wedge = one day/shift slot (Mon\u2013Sun \u00d7 Day/Eve/Night). "
                          "Purple = under-patrol, Orange = over-patrol.",
            transform=ax.transAxes, fontsize=8.5, color="#595959", va="bottom", ha="left")

    return _fig_to_bytes(fig)


def render_glyph_map_pro(gdf_native, gap_long_df: pd.DataFrame,
                          title: str = "Spatiotemporal Patrol Allocation Deviation Across Bartlett Patrol Zones",
                          selected_day: str = None) -> bytes:
    """
    Full glyph map, ported from the original Bartlett PD project script.
    gdf_native must be the shapefile's GeoDataFrame in its ORIGINAL
    (projected, feet) CRS — see geo_utils.load_zone_gdf_native() — since
    the sizing math below (ring radii, label offsets, the mile scale bar)
    is built in projected feet, which behaves uniformly across the map
    unlike lat/lon degrees.

    gap_long_df needs columns: zone_id, slot_name (e.g. 'Mon_Day'), gap.

    selected_day: one of "Mon".."Sun", or None. When a day is given, each
    zone shows a simplified 3-wedge glyph (Day/Evening/Night) for just
    that day instead of the full 21-wedge week — much larger and easier
    to read per zone, and switching the day updates the figure. The color
    scale stays fixed to the full week's range regardless of which day is
    selected, so wedge size/color is comparable across day selections
    (a calmer day visibly shows smaller wedges relative to the worst day,
    rather than every day being independently rescaled to fill the ring).
    """
    from matplotlib.patches import Wedge, Circle, Rectangle
    from matplotlib.cm import ScalarMappable

    FONT_NAME = "Liberation Serif"  # metrically identical to Times New Roman
    plt.rcParams["font.family"] = FONT_NAME
    plt.rcParams["mathtext.fontset"] = "stix"

    all_slots = [f"{d}_{s}" for d in _DAY_ORDER for s in _SHIFT_ORDER]
    zone_ids = sorted(gdf_native["zone_id"].unique().tolist())

    # Full week matrix — used to fix the color/radius scale regardless of
    # which day (if any) is currently displayed, so comparisons across
    # day selections stay meaningful.
    pivot_full = gap_long_df.pivot_table(index="zone_id", columns="slot_name", values="gap", aggfunc="mean")
    pivot_full = pivot_full.reindex(index=zone_ids, columns=all_slots)
    V_full = pivot_full.fillna(0.0).to_numpy()
    vmax_abs = max(float(np.abs(V_full).max()), 1e-9)

    if selected_day:
        slots = [f"{selected_day}_{s}" for s in _SHIFT_ORDER]
        slot_labels = ["Day", "Evening", "Night"]
    else:
        slots = all_slots
        slot_labels = None
    n_slots = len(slots)

    pivot = gap_long_df.pivot_table(index="zone_id", columns="slot_name", values="gap", aggfunc="mean")
    pivot = pivot.reindex(index=zone_ids, columns=slots)
    V = pivot.fillna(0.0).to_numpy()
    zone_mean = np.nanmean(V, axis=1)

    norm = DivergingPowerNorm(vmax_abs, gamma=0.55)
    cmap = plt.cm.PuOr_r

    gdf = gdf_native[["zone_id", "geometry"]].copy().rename(columns={"zone_id": "zone"})
    gdf = gdf.sort_values("zone").reset_index(drop=True)
    gdf["mean_val"] = gdf["zone"].map(dict(zip(zone_ids, zone_mean)))
    centroids = gdf.geometry.centroid
    gdf["cx"] = centroids.x
    gdf["cy"] = centroids.y

    from shapely.geometry import Point
    boundary_dist = []
    for _, row in gdf.iterrows():
        boundary_dist.append(row.geometry.boundary.distance(Point(row.cx, row.cy)))
    gdf["boundary_dist"] = boundary_dist

    SHRINK = 0.78
    LABEL_RING_FRAC = 1.03
    FRAC_BASE = 0.26

    gdf["total_r"] = gdf["boundary_dist"] * SHRINK
    gdf["base_r"] = gdf["total_r"] * FRAC_BASE
    gdf["max_extra"] = gdf["total_r"] * (1 - FRAC_BASE)
    gdf["label_mult"] = (0.85 * gdf["boundary_dist"] / gdf["total_r"]).clip(lower=1.18, upper=1.6)

    fig = plt.figure(figsize=(20, 14.5), dpi=150)
    ax = fig.add_axes([0.03, 0.09, 0.94, 0.88])

    gdf.plot(ax=ax, column="mean_val", cmap=cmap, norm=norm, edgecolor="none",
             linewidth=0, alpha=0.28, zorder=1)
    gdf.boundary.plot(ax=ax, color="black", linewidth=1.0, alpha=1.0, zorder=1.5)

    angle_per_slot = 360.0 / n_slots
    start_angle = 90.0
    gap_deg = 0.6 if selected_day is None else 2.5
    ring_fracs = [0.25, 0.5, 0.75, 1.0]
    tod_labels = ["D", "E", "N"]
    LABEL_TOD_THRESHOLD = 2600.0

    for _, row in gdf.iterrows():
        z = int(row["zone"])
        cx, cy = row["cx"], row["cy"]
        base_r, max_extra = row["base_r"], row["max_extra"]
        vals = V[zone_ids.index(z)]

        for rf in ring_fracs:
            rr = base_r + max_extra * rf
            ax.add_patch(Circle((cx, cy), rr, fill=False, edgecolor="black",
                                 linewidth=0.7, linestyle=(0, (1, 2.2)), zorder=2, alpha=0.85))
        ax.add_patch(Circle((cx, cy), base_r, fill=True, facecolor="white",
                             edgecolor="black", linewidth=1.0, zorder=3))

        for i, (slot, val) in enumerate(zip(slots, vals)):
            theta1 = start_angle - (i + 1) * angle_per_slot + gap_deg / 2
            theta2 = start_angle - i * angle_per_slot - gap_deg / 2
            r = base_r + max_extra * (abs(val) / vmax_abs)
            color = cmap(norm(val))
            w = Wedge((cx, cy), r, theta1, theta2, width=r - base_r, facecolor=color,
                      edgecolor="white", linewidth=0.9, alpha=0.95, zorder=4)
            ax.add_patch(w)

            if selected_day:
                # Simplified 3-wedge view: label each wedge with the full
                # shift name and its value directly, no abbreviation needed.
                mid_ang = np.deg2rad((theta1 + theta2) / 2)
                label_r = base_r + max_extra * 0.55
                tx = cx + label_r * np.cos(mid_ang)
                ty = cy + label_r * np.sin(mid_ang)
                ax.annotate(f"{slot_labels[i]}\n{val:+.2f}", (tx, ty), ha="center", va="center",
                            fontsize=10.5, color="#14142b", fontweight="bold", zorder=6,
                            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
            elif row["total_r"] >= LABEL_TOD_THRESHOLD:
                tod_idx = i % 3
                mid_ang = np.deg2rad((theta1 + theta2) / 2)
                label_r = base_r + max_extra * 0.12
                tx = cx + label_r * np.cos(mid_ang)
                ty = cy + label_r * np.sin(mid_ang)
                ax.annotate(tod_labels[tod_idx], (tx, ty), ha="center", va="center",
                            fontsize=5.4, color="white", fontweight="bold", zorder=6, alpha=0.95)

        if selected_day is None:
            for d in range(7):
                ang = np.deg2rad(start_angle - d * 3 * angle_per_slot)
                x0, y0 = cx + base_r * np.cos(ang), cy + base_r * np.sin(ang)
                x1, y1 = cx + (base_r + max_extra) * np.cos(ang), cy + (base_r + max_extra) * np.sin(ang)
                ax.plot([x0, x1], [y0, y1], color="black", linewidth=0.6, zorder=5, alpha=0.8)
                mid_ang = np.deg2rad(start_angle - (d * 3 + 1.5) * angle_per_slot)
                lx = cx + row["total_r"] * LABEL_RING_FRAC * np.cos(mid_ang)
                ly = cy + row["total_r"] * LABEL_RING_FRAC * np.sin(mid_ang)
                ax.annotate(_DAY_ORDER[d], (lx, ly), ha="center", va="center",
                            fontsize=13, fontweight="normal", color="#14142b", zorder=8)
        else:
            # Radial divider lines between the 3 shift wedges
            for i in range(n_slots):
                ang = np.deg2rad(start_angle - i * angle_per_slot)
                x0, y0 = cx + base_r * np.cos(ang), cy + base_r * np.sin(ang)
                x1, y1 = cx + (base_r + max_extra) * np.cos(ang), cy + (base_r + max_extra) * np.sin(ang)
                ax.plot([x0, x1], [y0, y1], color="black", linewidth=0.6, zorder=5, alpha=0.6)

    minx, miny, maxx, maxy = gdf.total_bounds
    ax.set_xlim(minx - (maxx - minx) * 0.05, maxx + (maxx - minx) * 0.22)
    ax.set_ylim(miny - (maxy - miny) * 0.08, maxy + (maxy - miny) * 0.06)
    ax.set_aspect("equal")
    ax.axis("off")

    for _, row in gdf.iterrows():
        z = int(row["zone"])
        label_y = row["cy"] - row["total_r"] * row["label_mult"]
        ax.annotate(f"Zone {z}", (row["cx"], label_y), ha="center", va="top",
                    fontsize=15, fontweight="normal", color="#14142b", zorder=8)

    right_x = maxx + (maxx - minx) * 0.06
    span_y = maxy - miny

    # Compass
    arrow_y0 = miny + span_y * 0.22
    ax.annotate("", xy=(right_x, arrow_y0 + span_y * 0.05), xytext=(right_x, arrow_y0),
                arrowprops=dict(arrowstyle="-|>", color="#14142b", linewidth=2.0))
    ax.annotate("N", (right_x, arrow_y0 + span_y * 0.06), ha="center", va="bottom",
                fontsize=18, fontweight="normal", color="#14142b")

    # Scale bar (assumes feet, standard for US state-plane shapefiles)
    mi_ft = 5280.0
    bar_h = span_y * 0.006
    sb_x0 = right_x - 2 * mi_ft
    sb_y0 = miny + span_y * 0.12
    ax.add_patch(Rectangle((sb_x0, sb_y0), mi_ft, bar_h, facecolor="black", edgecolor="black", linewidth=1.0, zorder=10))
    ax.add_patch(Rectangle((sb_x0 + mi_ft, sb_y0), mi_ft, bar_h, facecolor="white", edgecolor="black", linewidth=1.0, zorder=10))
    for k, lbl in enumerate(["0", "1", "2"]):
        tx = sb_x0 + k * mi_ft
        ax.plot([tx, tx], [sb_y0, sb_y0 + bar_h], color="black", linewidth=1.0, zorder=11)
        ax.annotate(lbl, (tx, sb_y0 + bar_h + span_y * 0.004), ha="center", va="bottom", fontsize=9, color="black", zorder=11)
    ax.annotate("mi", (sb_x0 + 2 * mi_ft + 700, sb_y0 + bar_h + span_y * 0.004), ha="left", va="bottom",
                fontsize=9, color="black", zorder=11)

    # Legend glyph
    leg_cx = right_x
    leg_cy = miny + span_y * 0.62
    LEG_R = span_y * 0.11
    leg_base = LEG_R * 0.30
    leg_extra = LEG_R * 0.70

    for rf in ring_fracs:
        rr = leg_base + leg_extra * rf
        ax.add_patch(Circle((leg_cx, leg_cy), rr, fill=False, edgecolor="#5a5a5a", linewidth=0.8,
                             linestyle=(0, (1, 2.2)), alpha=0.85, zorder=6))
        ax.annotate(f"{rf * vmax_abs:.2f}", (leg_cx + LEG_R * 0.05, leg_cy + rr), fontsize=11, color="#333333",
                    fontweight="normal", ha="left", va="bottom", zorder=7)

    for i in range(n_slots):
        theta1 = start_angle - (i + 1) * angle_per_slot + gap_deg / 2
        theta2 = start_angle - i * angle_per_slot - gap_deg / 2
        ax.add_patch(Wedge((leg_cx, leg_cy), leg_base + leg_extra * 0.55, theta1, theta2,
                            width=leg_extra * 0.55, facecolor="#d9d9d9", edgecolor="white",
                            linewidth=0.9, alpha=1.0, zorder=6))
    ax.add_patch(Circle((leg_cx, leg_cy), leg_base, fill=True, facecolor="white",
                         edgecolor="#20203a", linewidth=1.0, zorder=7))

    if selected_day is None:
        for d in range(7):
            ang = np.deg2rad(start_angle - d * 3 * angle_per_slot)
            x0, y0 = leg_cx + leg_base * np.cos(ang), leg_cy + leg_base * np.sin(ang)
            x1, y1 = leg_cx + LEG_R * np.cos(ang), leg_cy + LEG_R * np.sin(ang)
            ax.plot([x0, x1], [y0, y1], color="#20203a", linewidth=0.7, zorder=7, alpha=0.8)
            mid_ang = np.deg2rad(start_angle - (d * 3 + 1.5) * angle_per_slot)
            lx = leg_cx + LEG_R * 1.18 * np.cos(mid_ang)
            ly = leg_cy + LEG_R * 1.18 * np.sin(mid_ang)
            ax.annotate(_DAY_ORDER[d], (lx, ly), ha="center", va="center", fontsize=15,
                        fontweight="normal", color="#14142b", zorder=8)

        for d in range(7):
            for j, lbl in enumerate(tod_labels):
                ang = np.deg2rad(start_angle - (d * 3 + j + 0.5) * angle_per_slot)
                x = leg_cx + (leg_base + leg_extra * 0.22) * np.cos(ang)
                y = leg_cy + (leg_base + leg_extra * 0.22) * np.sin(ang)
                ax.annotate(lbl, (x, y), ha="center", va="center", fontsize=11,
                            fontweight="bold", color="#111111", zorder=8)

        ax.annotate("Outer ring = day/time slot; inner rings = deviation magnitude",
                    (leg_cx, leg_cy + LEG_R * 1.55), ha="center", va="bottom", fontsize=13,
                    fontweight="normal", color="#14142b", zorder=8)
        ax.annotate("D = Day      E = Evening      N = Night",
                    (leg_cx + LEG_R * 0.2, leg_cy - LEG_R * 1.5), ha="center", va="top", fontsize=11,
                    fontweight="normal", color="#14142b", zorder=8)
    else:
        for i in range(n_slots):
            ang = np.deg2rad(start_angle - i * angle_per_slot)
            x0, y0 = leg_cx + leg_base * np.cos(ang), leg_cy + leg_base * np.sin(ang)
            x1, y1 = leg_cx + LEG_R * np.cos(ang), leg_cy + LEG_R * np.sin(ang)
            ax.plot([x0, x1], [y0, y1], color="#20203a", linewidth=0.7, zorder=7, alpha=0.8)
            mid_ang = np.deg2rad(start_angle - (i + 0.5) * angle_per_slot)
            lx = leg_cx + LEG_R * 1.18 * np.cos(mid_ang)
            ly = leg_cy + LEG_R * 1.18 * np.sin(mid_ang)
            ax.annotate(slot_labels[i], (lx, ly), ha="center", va="center", fontsize=14,
                        fontweight="normal", color="#14142b", zorder=8)

        ax.annotate("Ring radius = deviation magnitude for this shift",
                    (leg_cx, leg_cy + LEG_R * 1.55), ha="center", va="bottom", fontsize=13,
                    fontweight="normal", color="#14142b", zorder=8)

    full_title = title
    if selected_day:
        day_full = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
                    "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}.get(selected_day, selected_day)
        full_title = f"{title} - {day_full}"
    fig.text(0.5, 0.965, full_title, ha="center", fontsize=22, fontweight="normal", color="#14142b")

    # Color-scale legend
    cbar_w = span_y * 0.09
    cbar_h = span_y * 0.007
    cbar_x0 = leg_cx - cbar_w / 2
    cbar_y0 = miny + span_y * 0.03

    cbar_ax = ax.inset_axes([cbar_x0, cbar_y0, cbar_w, cbar_h], transform=ax.transData)
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.ax.tick_params(labelsize=9)
    cbar.set_label("Allocation deviation", fontsize=13, labelpad=4)
    ax.annotate("UNDERPATROL", (cbar_x0 - cbar_w * 0.04, cbar_y0 + cbar_h / 2), ha="right", va="center",
                fontsize=10, fontweight="normal", color="#5b3a8e", zorder=11)
    ax.annotate("OVERPATROL", (cbar_x0 + cbar_w * 1.04, cbar_y0 + cbar_h / 2), ha="left", va="center",
                fontsize=10, fontweight="normal", color="#b5651d", zorder=11)

    result = _fig_to_bytes(fig)
    plt.rcParams["font.family"] = "sans-serif"  # reset so other maps aren't affected
    return result


def render_glyph_map(gdf, gap_long_df: pd.DataFrame, gdf_native=None, title: str = None,
                      selected_day: str = None) -> bytes:
    """
    Dispatches to the full ported glyph map (render_glyph_map_pro) when a
    native-CRS real-shapefile GeoDataFrame is available, otherwise falls
    back to the simpler lat/lon version (which does not support the
    selected_day simplification — always shows the full week).
    """
    if gdf_native is not None:
        kwargs = {"selected_day": selected_day}
        if title:
            kwargs["title"] = title
        return render_glyph_map_pro(gdf_native, gap_long_df, **kwargs)
    kwargs = {}
    if title:
        kwargs["title"] = title
    return render_glyph_map_simple(gdf, gap_long_df, **kwargs)
