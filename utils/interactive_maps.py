"""
Interactive Plotly maps using the older Mapbox-GL trace family
(go.Choroplethmapbox / go.Scattermapbox / px.scatter_mapbox with
mapbox_style="open-street-map"), NOT the newer MapLibre-based
scatter_map/choropleth_map family.

This distinction matters: tiles for this trace family load client-side,
in the viewer's own browser, when Plotly.js renders the figure — a
completely different network path from the app.py Python process. The
newer "_map" family (which this app used earlier and which repeatedly
rendered blank) may behave differently in some environments; this older
family is what's used in this project's other, confirmed-working
Streamlit dashboard (see streamlit_app_v2.py), so it's the reference
implementation here.

No server-side network calls happen when building these figures — the
zone boundary comes from the local shapefile via geo_utils, and no tile
image bytes are fetched until the browser renders the page.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DEFAULT_ZOOM = 10.6
BOUNDARY_LINE_COLOR = "black"
BOUNDARY_LINE_WIDTH = 1.6


def _zone_center(geojson):
    """Rough centroid of all zone polygons combined, for map centering."""
    lats, lons = [], []
    for feat in geojson["features"]:
        geom = feat["geometry"]
        coords = geom["coordinates"]
        rings = coords if geom["type"] == "MultiPolygon" else [coords]
        for poly in rings:
            for ring in poly:
                for lon, lat in ring:
                    lats.append(lat)
                    lons.append(lon)
    return {"lat": float(np.mean(lats)), "lon": float(np.mean(lons))}


def zone_boundary_trace(geojson, zone_ids, fill_opacity=0.0):
    """
    A Choroplethmapbox trace showing only zone outlines — used as a
    boundary overlay under point/marker layers. Fill transparency is
    controlled ONLY via the colorscale's own rgba alpha channel; marker_opacity
    is left at 1.0 deliberately, since Choroplethmapbox's marker_opacity
    multiplies the entire marker (fill AND boundary line together) — a low
    marker_opacity was making the boundary line nearly invisible too, not
    just the fill.
    """
    return go.Choroplethmapbox(
        geojson=geojson,
        locations=zone_ids,
        z=[0] * len(zone_ids),
        featureidkey="properties.zone_id",
        colorscale=[[0, f"rgba(255,255,255,{fill_opacity})"], [1, f"rgba(255,255,255,{fill_opacity})"]],
        showscale=False,
        marker_line_width=BOUNDARY_LINE_WIDTH,
        marker_line_color=BOUNDARY_LINE_COLOR,
        marker_opacity=1.0,
        hoverinfo="skip",
    )


ZONE_PASTELS = {
    1: "#F6C9CC", 2: "#F9DDB1", 3: "#FBF1A9", 4: "#C8E6C9",
    5: "#B3E0DC", 6: "#BBD8F7", 7: "#D3C5F0", 8: "#F3C6E0",
}


def zone_pastel_fill_traces(geojson, zone_ids, opacity=0.55):
    """
    One Choroplethmapbox trace per zone, each filled with a distinct
    pastel color (see ZONE_PASTELS) — built as separate single-zone traces
    rather than one multi-zone trace with a shared colorscale, so each
    zone's color is exact rather than interpolated.
    """
    traces = []
    for zid in zone_ids:
        color = ZONE_PASTELS.get(zid, "#E0E0E0")
        traces.append(go.Choroplethmapbox(
            geojson=geojson,
            locations=[zid],
            z=[0],
            featureidkey="properties.zone_id",
            colorscale=[[0, color], [1, color]],
            showscale=False,
            marker_opacity=opacity,
            marker_line_width=BOUNDARY_LINE_WIDTH,
            marker_line_color=BOUNDARY_LINE_COLOR,
            hoverinfo="skip",
        ))
    return traces


def render_hotspot_mapbox(geojson, df: pd.DataFrame, lat_col: str, lon_col: str,
                           color: str, title: str = "") -> go.Figure:
    """Real OSM basemap, zone boundary overlay, incident points scattered on top."""
    zone_ids = [f["properties"]["zone_id"] for f in geojson["features"]]
    center = _zone_center(geojson)

    fig = go.Figure()
    fig.add_trace(zone_boundary_trace(geojson, zone_ids))
    if len(df) > 0:
        fig.add_trace(go.Scattermapbox(
            lat=df[lat_col], lon=df[lon_col], mode="markers",
            marker=dict(size=5, color=color, opacity=0.65),
            hoverinfo="skip", showlegend=False,
        ))
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=center, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=30, b=0), height=420,
        title=dict(text=title, font=dict(size=14)) if title else None,
    )
    return fig


def render_car_placement_mapbox(geojson, gdf_wgs84, counts_by_zone: dict,
                                 title: str = "", seed_prefix: str = "") -> go.Figure:
    """
    Real OSM basemap, each zone filled with a distinct pastel color,
    patrol units shown as a two-tone maroon/white badge marker (a plain
    "P" letter, not an emoji — emoji glyph support varies too much across
    browsers/OSes to rely on for something this central to the figure)
    placed at true random points sampled inside each zone's actual polygon.
    """
    from shapely.geometry import Point

    zone_ids = [f["properties"]["zone_id"] for f in geojson["features"]]
    center = _zone_center(geojson)
    gdf_by_zone = gdf_wgs84.set_index("zone_id")

    lats, lons, hover = [], [], []
    for zid, n in counts_by_zone.items():
        n = int(n) if pd.notna(n) else 0
        if n <= 0 or zid not in gdf_by_zone.index:
            continue
        geom = gdf_by_zone.loc[zid, "geometry"]
        minx, miny, maxx, maxy = geom.bounds
        rng = np.random.default_rng(seed=abs(hash(f"{seed_prefix}-{zid}")) % (2**32))
        found = 0
        attempts = 0
        while found < n and attempts < n * 60 + 200:
            attempts += 1
            x = rng.uniform(minx, maxx)
            y = rng.uniform(miny, maxy)
            if geom.contains(Point(x, y)):
                lats.append(y)
                lons.append(x)
                hover.append(f"Zone {zid}")
                found += 1

    fig = go.Figure()
    for tr in zone_pastel_fill_traces(geojson, zone_ids, opacity=0.55):
        fig.add_trace(tr)

    import warnings
    with warnings.catch_warnings():
        # Centroid-in-geographic-CRS warning: harmless at this scale (an
        # 8-zone city, a few km across) — used only for approximate label
        # placement, not for any measurement that needs to be precise.
        warnings.simplefilter("ignore", UserWarning)
        zone_centroids = gdf_wgs84.geometry.centroid

    zone_label_text = [f"Zone {z}" for z in gdf_wgs84["zone_id"]]
    # White halo behind the label (rendered first, larger/bolder) plus the
    # actual navy text on top — Plotly text has no native outline/halo
    # option, so this two-layer trick fakes one for legibility against the
    # busy OSM tile background.
    fig.add_trace(go.Scattermapbox(
        lat=zone_centroids.y, lon=zone_centroids.x, mode="text",
        text=zone_label_text, textfont=dict(size=15, color="#FFFFFF"),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scattermapbox(
        lat=zone_centroids.y, lon=zone_centroids.x, mode="text",
        text=zone_label_text, textfont=dict(size=12, color="#0D2B52"),
        hoverinfo="skip", showlegend=False,
    ))

    if lats:
        # Outer white ring, then inner maroon badge with a plain "P" —
        # guaranteed to render regardless of emoji font support.
        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons, mode="markers",
            marker=dict(size=21, color="#FFFFFF", opacity=0.95),
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons, mode="markers+text",
            marker=dict(size=15, color="#7B1E3A", opacity=1.0),
            text=["P"] * len(lats), textfont=dict(size=10, color="#FFFFFF"),
            hovertext=hover, hoverinfo="text", showlegend=False,
        ))
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=center, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=30, b=0), height=420,
        title=dict(text=title, font=dict(size=14)) if title else None,
    )
    return fig


def render_gap_choropleth_mapbox(geojson, values_by_zone: dict, colorscale, zmid: float = 0,
                                  title: str = "", legend_label: str = "") -> go.Figure:
    """Real OSM basemap with zones filled by value (coverage gap, etc.)."""
    zone_ids = [f["properties"]["zone_id"] for f in geojson["features"]]
    z_values = [values_by_zone.get(zid) for zid in zone_ids]
    center = _zone_center(geojson)
    abs_max = max(abs(v) for v in z_values if v is not None) if any(v is not None for v in z_values) else 1

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson, locations=zone_ids, z=z_values,
        featureidkey="properties.zone_id",
        colorscale=colorscale, zmid=zmid, zmin=-abs_max, zmax=abs_max,
        marker_opacity=0.7, marker_line_width=BOUNDARY_LINE_WIDTH, marker_line_color=BOUNDARY_LINE_COLOR,
        colorbar=dict(title=legend_label, thickness=14, len=0.75),
        text=[f"Zone {z}: {v:+.1f}" if v is not None else f"Zone {z}" for z, v in zip(zone_ids, z_values)],
        hoverinfo="text",
    ))
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=center, zoom=DEFAULT_ZOOM),
        margin=dict(l=0, r=0, t=30, b=0), height=420,
        title=dict(text=title, font=dict(size=14)) if title else None,
    )
    return fig
