"""
Zone geometry loading. Tries the real patrol-district polygons from
PATROL_DISTRICTS_2025/; if that shapefile isn't present yet, falls back
to a Voronoi approximation from zone_schedule.csv centroids so the app
still runs end-to-end.
"""
import streamlit as st
import pandas as pd
from . import config as CFG

_CANDIDATE_ZONE_FIELDS = [
    "ZONE_ID", "ZONE", "Zone", "zone_id", "ZONE_NUM", "ZONE_NO", "PATDIST_", "PATDIST",
    "PATROL_ZON", "PATROL_ID", "DISTRICT", "District", "Name", "NAME", "Id", "ID",
]


def _to_zone_id(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return CFG.zone_label_to_id(v)


def _detect_zone_field(gdf, n_expected_zones=8):
    """
    Picks the shapefile field that actually identifies zones 1..N, rather
    than trusting field-name priority alone. A field name like 'Id' can
    exist in a shapefile's attribute table but hold nothing useful (e.g.
    all zeros) — so each candidate is validated: converting it to zone_id
    must yield exactly n_expected_zones distinct values, all within
    1..n_expected_zones, before it's accepted. Falls back to name-priority
    order only if no candidate passes validation.
    """
    override = CFG.SHAPEFILE_ZONE_FIELD_OVERRIDE
    if override is not None:
        return override

    valid_range = set(range(1, n_expected_zones + 1))
    for cand in _CANDIDATE_ZONE_FIELDS:
        if cand not in gdf.columns:
            continue
        try:
            ids = gdf[cand].apply(_to_zone_id).dropna().astype(int)
        except Exception:
            continue
        if len(ids) == n_expected_zones and set(ids) == valid_range:
            return cand

    # No candidate cleanly validated — fall back to the first name match
    # that at least exists, so behavior degrades gracefully rather than
    # silently picking nothing.
    for cand in _CANDIDATE_ZONE_FIELDS:
        if cand in gdf.columns:
            return cand
    return None


@st.cache_data(show_spinner=False)
def load_zone_shapes():
    """
    Returns (geojson_dict_or_None, zone_field_name_or_None, status_msg).
    geojson features are re-keyed so that feature.properties['zone_id']
    always holds the integer 1..8 zone id, regardless of the source
    shapefile's original field name.
    """
    shp_path = CFG.SHAPEFILE_DIR / CFG.SHAPEFILE_NAME
    if not shp_path.exists():
        return None, None, f"Shapefile not found at {shp_path}. Using centroid markers instead."

    try:
        import geopandas as gpd
    except ImportError:
        return None, None, "geopandas is not installed. Run: pip install geopandas shapely. Using centroid markers instead."

    try:
        gdf = gpd.read_file(shp_path)
    except Exception as e:
        return None, None, f"Could not read shapefile ({e}). Using centroid markers instead."

    # Reproject to WGS84 for web mapping if a CRS is defined
    try:
        if gdf.crs is not None and str(gdf.crs).upper() not in ("EPSG:4326",):
            gdf = gdf.to_crs(epsg=4326)
    except Exception:
        pass

    zone_field = _detect_zone_field(gdf)
    if zone_field is None:
        return None, None, (
            f"Could not auto-detect the zone field in the shapefile. "
            f"Available fields: {list(gdf.columns)}. "
            f"Set SHAPEFILE_ZONE_FIELD_OVERRIDE in utils/config.py. Using centroid markers instead."
        )

    gdf["zone_id"] = gdf[zone_field].apply(_to_zone_id)
    gdf = gdf.dropna(subset=["zone_id"])
    gdf["zone_id"] = gdf["zone_id"].astype(int)

    geojson = gdf.__geo_interface__
    return geojson, zone_field, f"Loaded {len(gdf)} zone polygons from shapefile."


@st.cache_data(show_spinner=False)
def load_zone_centroids():
    """Fallback / supplementary zone centroid table from zone_schedule.csv."""
    df = pd.read_csv(CFG.DATA_DIR / "zone_schedule.csv")
    cent = (
        df[["zone_idx", "zone_name", "centroid_lat", "centroid_lon", "zone_area_km2", "zone_size_class"]]
        .drop_duplicates(subset=["zone_idx"])
        .reset_index(drop=True)
    )
    cent["zone_id"] = cent["zone_idx"].astype(int) + 1  # zone_idx is 0-based
    return cent


def has_real_shapefile() -> bool:
    shp_path = CFG.SHAPEFILE_DIR / CFG.SHAPEFILE_NAME
    return shp_path.exists()


@st.cache_data(show_spinner=False)
def load_zone_gdf_native():
    """
    Returns the real shapefile's GeoDataFrame in its ORIGINAL CRS (no
    reprojection to WGS84), with a 'zone_id' column added — or None if the
    real shapefile isn't present.

    The glyph/rose map's sizing math (ring radii, label offsets, the mile
    scale bar) is built in the shapefile's native projected units (feet,
    for EPSG:2274) rather than lat/lon degrees, since projected feet behave
    uniformly across the map while degrees distort with latitude. Every
    other map in this app uses WGS84 (load_zone_gdf) since that's what
    lat/lon incident data and centroids are already in.
    """
    import geopandas as gpd

    shp_path = CFG.SHAPEFILE_DIR / CFG.SHAPEFILE_NAME
    if not shp_path.exists():
        return None
    try:
        gdf = gpd.read_file(shp_path)
        zone_field = _detect_zone_field(gdf)
        if zone_field is None:
            return None
        gdf["zone_id"] = gdf[zone_field].apply(_to_zone_id)
        gdf = gdf.dropna(subset=["zone_id"])
        gdf["zone_id"] = gdf["zone_id"].astype(int)
        if len(gdf) == 0:
            return None
        return gdf[["zone_id", "geometry"]]
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_zone_gdf():
    """
    Returns (GeoDataFrame[zone_id, geometry] in EPSG:4326, is_real_shapefile: bool)
    for static matplotlib rendering.

    If the real shapefile is present, uses it directly (with validated
    zone-field detection, see _detect_zone_field). Otherwise builds an
    approximate zone layout via a Voronoi diagram over the 8 zone centroids
    (from zone_schedule.csv), clipped to a padded bounding box — so maps
    still show plausible zone-shaped boundaries even before the real
    shapefile is added, and automatically upgrade once it is.
    """
    import geopandas as gpd
    from shapely.geometry import box
    from shapely.ops import voronoi_diagram
    from shapely.geometry import MultiPoint, Point

    shp_path = CFG.SHAPEFILE_DIR / CFG.SHAPEFILE_NAME
    if shp_path.exists():
        try:
            gdf = gpd.read_file(shp_path)
            if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
            zone_field = _detect_zone_field(gdf)
            if zone_field is not None:
                gdf["zone_id"] = gdf[zone_field].apply(_to_zone_id)
                gdf = gdf.dropna(subset=["zone_id"])
                gdf["zone_id"] = gdf["zone_id"].astype(int)
                if len(gdf) > 0:
                    return gdf[["zone_id", "geometry"]], True
        except Exception:
            pass  # fall through to Voronoi approximation

    # ---- Voronoi fallback from centroids ----
    cent = load_zone_centroids()
    pts = [Point(lon, lat) for lat, lon in zip(cent["centroid_lat"], cent["centroid_lon"])]
    mp = MultiPoint(pts)
    pad = 0.045
    minx, miny, maxx, maxy = mp.bounds
    envelope = box(minx - pad, miny - pad, maxx + pad, maxy + pad)
    regions = voronoi_diagram(mp, envelope=envelope)
    # Match each Voronoi cell back to its generating zone by containment
    rows = []
    for _, row in cent.iterrows():
        p = Point(row["centroid_lon"], row["centroid_lat"])
        for cell in regions.geoms:
            if cell.contains(p) or cell.intersects(p):
                rows.append({"zone_id": int(row["zone_id"]), "geometry": cell.intersection(envelope)})
                break
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf, False
