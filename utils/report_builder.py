"""
Builds a downloadable PDF report for a chosen deployment day: officer
placement maps and coverage-gap maps for all three models, across every
shift that has data that day, plus the demand-misalignment glyph map.

Deliberately uses the matplotlib static map renderers (utils/static_maps.py)
rather than exporting the interactive Plotly maps. Exporting Plotly's
Mapbox-family figures to a static image requires kaleido to drive a
headless browser that itself has to fetch real map tiles over the network
— a server-side dependency with the same fragility as the earlier
contextily basemap attempt (see static_maps.py's own history for that).
The matplotlib renderers already have real shapefile geometry, pastel
zone fills, and badge markers with no such dependency, so reusing them
here sidesteps that risk entirely.
"""
import gc
import io
from datetime import datetime
from pathlib import Path

# Report images are embedded at a small display size (roughly 2in wide in a
# 3-column layout), so a lower DPI than the app's interactive maps (150)
# loses no visible quality here while meaningfully reducing peak memory —
# generating ~18-19 map figures in one request is the single heaviest
# operation in this app, worth being deliberate about on a memory-capped
# free-tier host.
REPORT_DPI = 100

import pandas as pd
from PIL import Image as PILImage

# Our own generated images (matplotlib renders, possibly with legitimately
# fetched OSM tiles baked in) are always trusted, so Pillow's default
# decompression-bomb ceiling (~179M pixels) is unnecessarily strict here —
# it tripped on a basemap tile mosaic before the zoom cap below was added.
# Raised, not disabled outright, so a genuinely runaway image (a real bug)
# still gets caught rather than silently consuming unbounded memory.
PILImage.MAX_IMAGE_PIXELS = 300_000_000
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage,
    Table, TableStyle, KeepTogether,
)

from . import config as CFG
from . import static_maps

MODELS = ["Uniform", "Static", "Dynamic"]
PAGE_WIDTH, PAGE_HEIGHT = letter
CONTENT_WIDTH = PAGE_WIDTH - 1.4 * inch

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_WATERMARK_PATH = _ASSETS_DIR / "opps_watermark.png"

# ---------------------------------------------------------------------------
# Font registration: the actual Nunito font used across the web app,
# embedded into the PDF (not a lookalike substitute). Google Fonts only
# distributes Nunito as a single variable-weight file, so the Regular /
# Bold / ExtraBold static instances were pre-extracted once with fontTools
# (see assets/fonts/) and are just loaded here.
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False


def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        pdfmetrics.registerFont(TTFont("Nunito", str(_FONTS_DIR / "Nunito-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Nunito-Bold", str(_FONTS_DIR / "Nunito-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("Nunito-ExtraBold", str(_FONTS_DIR / "Nunito-ExtraBold.ttf")))
        pdfmetrics.registerFontFamily("Nunito", normal="Nunito", bold="Nunito-Bold")
        _FONTS_REGISTERED = True
    except Exception:
        pass  # fonts missing on this install — falls back to reportlab's built-in Helvetica


def _font(name: str, fallback: str) -> str:
    return name if _FONTS_REGISTERED else fallback


def _png_to_flowable(png_bytes: bytes, max_width: float, max_height: float = None) -> RLImage:
    """Wraps raw PNG bytes as a reportlab Image flowable, scaled to fit
    max_width while preserving aspect ratio."""
    pil_img = PILImage.open(io.BytesIO(png_bytes))
    w_px, h_px = pil_img.size
    aspect = h_px / w_px
    disp_w = max_width
    disp_h = disp_w * aspect
    if max_height and disp_h > max_height:
        disp_h = max_height
        disp_w = disp_h / aspect
    return RLImage(io.BytesIO(png_bytes), width=disp_w, height=disp_h)


def _styles():
    _register_fonts()
    body_font = _font("Nunito", "Helvetica")
    bold_font = _font("Nunito-Bold", "Helvetica-Bold")
    xbold_font = _font("Nunito-ExtraBold", "Helvetica-Bold")

    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("OppsTitle", parent=ss["Title"], fontName=xbold_font,
                           textColor=colors.HexColor("#7B1E3A"), fontSize=22, spaceAfter=4))
    ss.add(ParagraphStyle("OppsSubtitle", parent=ss["Normal"], fontName=body_font,
                           textColor=colors.HexColor("#595959"), fontSize=11, spaceAfter=14))
    ss.add(ParagraphStyle("OppsSection", parent=ss["Heading1"], fontName=bold_font,
                           textColor=colors.HexColor("#2B2B2B"), fontSize=15, spaceBefore=18, spaceAfter=8))
    ss.add(ParagraphStyle("OppsSubsection", parent=ss["Heading2"], fontName=bold_font,
                           textColor=colors.HexColor("#7B1E3A"), fontSize=12, spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle("OppsCaption", parent=ss["Normal"], fontName=body_font, fontSize=8.5,
                           textColor=colors.HexColor("#595959"), alignment=1, spaceBefore=2))
    ss.add(ParagraphStyle("OppsBody", parent=ss["Normal"], fontName=body_font, fontSize=10, leading=14))
    return ss


def _watermark_and_footer(canvas, doc):
    """Draws the faint OPPS badge watermark centered on the page, then the
    footer text, on every page of the report."""
    canvas.saveState()
    if _WATERMARK_PATH.exists():
        try:
            wm_size = 3.6 * inch
            canvas.saveState()
            canvas.setFillAlpha(0.05)
            canvas.drawImage(
                str(_WATERMARK_PATH),
                (PAGE_WIDTH - wm_size) / 2, (PAGE_HEIGHT - wm_size) / 2,
                width=wm_size, height=wm_size, mask="auto",
            )
            canvas.restoreState()
        except Exception:
            pass  # very old reportlab without alpha support - skip the watermark rather than risk drawing it opaque

    body_font = _font("Nunito", "Helvetica")
    canvas.setFont(body_font, 8)
    canvas.setFillColor(colors.HexColor("#8C8C8C"))
    canvas.drawString(0.7 * inch, 0.5 * inch, "OPPS - Optimal Prepositioning of Patrol Services")
    canvas.drawRightString(PAGE_WIDTH - 0.7 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _model_row(zone_gdf, subset_row_by_model: dict, render_fn, styles, title_prefix=""):
    """
    Builds a 3-column reportlab Table with one static map per model
    (Uniform / Static / Dynamic), each with a small caption underneath.
    render_fn(model) -> PNG bytes.
    """
    cell_width = CONTENT_WIDTH / 3 - 0.1 * inch
    cells = []
    captions = []
    for model in MODELS:
        png = render_fn(model)
        img_flowable = _png_to_flowable(png, cell_width)
        cells.append(img_flowable)
        captions.append(Paragraph(CFG.MODEL_SHORT_NAMES[model], styles["OppsCaption"]))
    table = Table([cells, captions], colWidths=[cell_width + 0.05 * inch] * 3)
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _zone_table(subset: pd.DataFrame, styles) -> Table:
    _register_fonts()
    cols = ["Zone", "Demand_share_pct", "x_Uniform", "x_Static", "x_Dynamic",
            "Gap_Uniform_pp", "Gap_Static_pp", "Gap_Dynamic_pp"]
    header = ["Zone", "Demand %", "Unif. Off.", "Static Off.", "Dyn. Off.",
              "Unif. Gap", "Static Gap", "Dyn. Gap"]
    rows = [header]
    for _, row in subset.sort_values("Zone").iterrows():
        rows.append([
            row["Zone"],
            f"{row['Demand_share_pct']:.1f}",
            f"{int(row['x_Uniform'])}",
            f"{int(row['x_Static'])}",
            f"{int(row['x_Dynamic'])}",
            f"{row['Gap_Uniform_pp']:+.1f}",
            f"{row['Gap_Static_pp']:+.1f}",
            f"{row['Gap_Dynamic_pp']:+.1f}",
        ])
    t = Table(rows, colWidths=[CONTENT_WIDTH / 8] * 8, repeatRows=1)
    body_font = _font("Nunito", "Helvetica")
    bold_font = _font("Nunito-Bold", "Helvetica-Bold")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B1E3A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), body_font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F0F2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_daily_report_pdf(sel_date, gis_all: pd.DataFrame, zone_gdf, zone_gdf_native,
                            gap_long_df: pd.DataFrame, day_name: str,
                            selected_shift: str = None) -> bytes:
    """
    Builds the full PDF report for one deployment day and returns raw
    PDF bytes (ready for st.download_button).

    selected_shift: one of the Slot_name values (e.g. "Wed_Day"), or None
    (default) to include every shift with data on this date. Limiting to
    a single shift cuts the map count from ~19 down to ~7, meaningfully
    reducing generation time on a resource-constrained host.
    """
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                             topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    story = []

    date_label = pd.Timestamp(sel_date).strftime("%A, %B %d, %Y")
    story.append(Paragraph("OPPS Patrol Allocation Report", styles["OppsTitle"]))
    story.append(Paragraph(
        f"Bartlett Police Department &middot; Shelby County, TN &middot; Deployment date: {date_label}",
        styles["OppsSubtitle"],
    ))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by the OPPS dashboard.",
        styles["OppsCaption"],
    ))
    story.append(Spacer(1, 8))

    day_subset_all = gis_all[gis_all["Date"] == sel_date]
    shifts_present = sorted(day_subset_all["Slot_name"].unique().tolist())
    if selected_shift:
        shifts_present = [s for s in shifts_present if s == selected_shift]

    for shift in shifts_present:
        subset = day_subset_all[day_subset_all["Slot_name"] == shift]
        if subset.empty:
            continue
        shift_code = shift.split("_")[-1]
        shift_label = CFG.SHIFT_LABELS.get(shift_code, shift)

        story.append(Paragraph(f"{shift_label} - {date_label}", styles["OppsSection"]))

        story.append(Paragraph("Recommended Officer Placement by Zone", styles["OppsSubsection"]))
        counts_by_model = {m: dict(zip(subset["zone_id"], subset[f"x_{m}"])) for m in MODELS}

        def _render_officer(model, counts_by_model=counts_by_model, shift=shift):
            return static_maps.render_car_placement_map(
                zone_gdf, counts_by_model[model],
                title=CFG.MODEL_SHORT_NAMES[model],
                seed_prefix=f"{sel_date}-{shift}-{model}",
                dpi=REPORT_DPI,
            )

        story.append(_model_row(zone_gdf, counts_by_model, _render_officer, styles))
        story.append(Spacer(1, 10))
        gc.collect()  # each shift renders 6 map figures - free them before the next batch

        story.append(Paragraph("Coverage Gap vs. Demand", styles["OppsSubsection"]))
        gap_cols = {m: f"Gap_{m}_pp" for m in MODELS}
        abs_max = float(pd.concat([subset[c] for c in gap_cols.values()]).abs().max())

        def _render_gap(model, subset=subset, gap_cols=gap_cols, abs_max=abs_max):
            values = dict(zip(subset["zone_id"], subset[gap_cols[model]]))
            return static_maps.render_choropleth_map(
                zone_gdf, values, vmin=-abs_max, vmax=abs_max,
                title=f"{CFG.MODEL_SHORT_NAMES[model]} - Gap",
                legend_label="Gap (pp)",
                dpi=REPORT_DPI,
            )

        story.append(_model_row(zone_gdf, counts_by_model, _render_gap, styles))
        story.append(Spacer(1, 10))
        gc.collect()

        story.append(KeepTogether([
            Paragraph("Zone Data", styles["OppsSubsection"]),
            _zone_table(subset, styles),
        ]))
        story.append(PageBreak())

    # Demand-misalignment glyph map for the day (uses the real ported
    # glyph renderer when the real shapefile + native-CRS gdf are available)
    story.append(Paragraph("Where Uniform Patrol Misses Demand", styles["OppsSection"]))
    story.append(Paragraph(
        "Each zone's rose shows the mismatch between the current Uniform Plan and "
        "actual demand, broken down by Day / Evening / Night shift for this day of week.",
        styles["OppsBody"],
    ))
    story.append(Spacer(1, 8))
    day_code = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
                "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}.get(day_name, day_name[:3])
    # Full-width figure with small text annotations - keep DPI a bit higher
    # than the compact comparison maps so labels stay legible, but still
    # below the interactive-app default (150) to control memory.
    glyph_png = static_maps.render_glyph_map(
        zone_gdf, gap_long_df, gdf_native=zone_gdf_native,
        title="Patrol Allocation Deviation", selected_day=day_code,
        dpi=120,
    )
    story.append(_png_to_flowable(glyph_png, CONTENT_WIDTH))
    gc.collect()

    doc.build(story, onFirstPage=_watermark_and_footer, onLaterPages=_watermark_and_footer)
    buf.seek(0)
    return buf.read()
