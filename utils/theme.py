"""
Site-wide visual identity for the Patrol Allocation Dashboard.

Design intent:
- Neutral grey console: dark charcoal sidebar, light grey main canvas.
  Crash/violation data keep two fixed, deliberate colors (red / blue) as
  the only non-grey hues in the interface, so they read as data, not decor.
- The purple/orange diverging scale on coverage-gap maps remains the one
  other intentional color signature (unchanged from before).
- Nunito (Google Fonts) for all text.

IMPORTANT: no blank lines inside CUSTOM_CSS's <style> block. Streamlit's
Markdown renderer treats <style> as raw HTML only until the first blank
line, after which it falls back to normal Markdown parsing and the CSS
becomes visible page text. Keep every line inside <style>...</style>
non-blank.
"""
import streamlit as st
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_PATH = _ASSETS_DIR / "opps_logo.png"

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap">'

# Fixed data colors (not theme-adjustable — these encode meaning)
CRASH_COLOR = "#B11313"
VIOLATION_COLOR = "#2B3784"

CUSTOM_CSS = f"""
{FONT_LINK}
<style>
:root {{
  --ink: #262626;
  --paper: #F1F1F1;
  --card: #FFFFFF;
  --border: #D9D9D9;
  --steel: #595959;
  --steel-dk: #2B2B2B;
  --accent: #8C8C8C;
  --muted: #737373;
  --cherry: #C41E3A;
  --maroon: #7B1E3A;
}}
/* ---- Page 2 filter row: glass/gradient maroon selects, scoped via container key ----
   Multiple redundant selectors targeting different possible internal
   structures of the selectbox widget, since baseweb's internal DOM can
   vary between Streamlit versions — [data-testid] selectors are Streamlit's
   own stable API and are tried first, baseweb attribute selectors second. */
.st-key-allocation_filters [data-testid="stSelectbox"] > div > div,
.st-key-allocation_filters [data-testid="stSelectbox"] div[data-baseweb="select"],
.st-key-allocation_filters [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
.st-key-allocation_filters div[data-baseweb="select"],
.st-key-allocation_filters div[data-baseweb="select"] > div,
.st-key-allocation_filters div[data-baseweb="base-input"] {{
  background: linear-gradient(135deg, rgba(123,30,58,0.42) 0%, rgba(123,30,58,0.14) 100%) !important;
  backdrop-filter: blur(7px) !important;
  -webkit-backdrop-filter: blur(7px) !important;
  border: 1.5px solid rgba(123,30,58,0.65) !important;
  border-radius: 10px !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 3px 10px rgba(123,30,58,0.22) !important;
}}
.st-key-allocation_filters label p, .st-key-allocation_filters label {{
  color: var(--maroon) !important;
  font-weight: 700 !important;
}}
/* ---- st.table styling: maroon header row, white header text ---- */
[data-testid="stTable"] table thead th {{
  background: var(--maroon) !important;
  color: #FFFFFF !important;
  font-weight: 700 !important;
  border-color: var(--maroon) !important;
}}
[data-testid="stTable"] table tbody tr:nth-child(even) {{
  background: #F7F0F2;
}}
[data-testid="stTable"] table td, [data-testid="stTable"] table th {{
  padding: 0.45rem 0.7rem !important;
}}
/* ---- Sidebar: default width ---- */
[data-testid="stSidebar"] {{
  min-width: 300px !important;
  max-width: 320px !important;
  width: 310px !important;
}}
html, body, [class*="css"], .stApp,
p, span, div, label, li, td, th, button, input, textarea, select,
[data-testid="stMarkdownContainer"], [data-testid="stMetricValue"],
[data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {{
  font-family: 'Nunito', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
h1, h2, h3, h4, h5, h6 {{
  font-family: 'Nunito', sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: -0.01em;
  color: var(--ink);
}}
h1 {{ font-size: 1.55rem !important; }}
h2 {{ font-size: 1.25rem !important; }}
h3 {{ font-size: 1.05rem !important; }}
[data-testid="stIconMaterial"], .material-symbols-outlined, .material-symbols-rounded, [class*="MaterialIcon"] {{
  font-family: 'Material Symbols Outlined', 'Material Symbols Rounded', 'Material Icons' !important;
}}
.stApp {{
  background: #FFFFFF;
}}
[data-testid="stAppViewContainer"] > .main {{
  color: var(--ink);
}}
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
[data-testid="stDecoration"] {{display: none;}}
[data-testid="stSidebar"] {{
  background: #CFCFCF;
  border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] * {{
  color: var(--ink) !important;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
  color: var(--ink) !important;
  text-transform: uppercase;
  font-size: 0.88rem;
  letter-spacing: 0.08em;
  font-weight: 700 !important;
  opacity: 0.85;
}}
[data-testid="stSidebar"] hr {{ border-color: var(--border); }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
  background: #F5F5F5;
  border-color: var(--border);
}}
[data-testid="stSidebar"] [data-testid="stIconMaterial"] {{
  color: var(--ink) !important;
}}
[data-testid="stSidebarNav"] a {{
  border-radius: 8px;
  font-weight: 600 !important;
}}
[data-testid="stLogo"] {{
  margin: 0.6rem auto 0.9rem auto;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid var(--border);
  display: block;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: rgba(0,0,0,0.06) !important;
  border-left: 3px solid var(--steel);
}}
.masthead {{
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.65rem;
  margin-bottom: 1.4rem;
}}
.masthead .eyebrow {{
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  font-weight: 700;
  color: var(--muted);
  margin-bottom: 0.15rem;
}}
.masthead .title {{
  font-size: 1.45rem;
  font-weight: 800;
  color: var(--ink);
  letter-spacing: -0.01em;
  line-height: 1.15;
}}
.masthead .subtitle {{
  font-size: 0.94rem;
  color: var(--muted);
  margin-top: 0.3rem;
  max-width: 62ch;
}}
[data-testid="stMetric"] {{
  background: var(--card);
  border: 1px solid var(--border);
  border-top: 3px solid var(--cherry);
  border-radius: 6px;
  padding: 0.9rem 1.1rem;
}}
[data-testid="stMetricValue"] {{
  color: var(--steel-dk);
  font-weight: 800 !important;
  font-variant-numeric: tabular-nums;
}}
[data-testid="stMetricLabel"] {{
  color: var(--muted);
  text-transform: uppercase;
  font-size: 0.72rem !important;
  letter-spacing: 0.06em;
}}
.stTabs [data-baseweb="tab-list"] {{
  gap: 4px;
  border-bottom: 1px solid var(--border);
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 6px 6px 0 0;
  padding: 8px 20px;
  font-weight: 600;
  color: var(--muted);
  background: transparent;
}}
.stTabs [aria-selected="true"] {{
  background-color: var(--steel) !important;
  color: #FFFFFF !important;
}}
.stButton>button, .stDownloadButton>button {{
  border-radius: 6px;
  border: 1px solid var(--steel);
  color: var(--steel-dk);
  font-weight: 600;
  background: var(--card);
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
  background: var(--steel);
  color: #FFFFFF;
  border-color: var(--steel);
}}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}}
[data-testid="stAlert"] {{
  border-radius: 4px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--steel);
  background: var(--card);
  color: var(--ink);
}}
hr {{ border-color: var(--border); }}
[data-baseweb="select"] > div {{
  border-radius: 6px;
  border-color: var(--border);
}}
.stSlider [data-baseweb="slider"] > div > div {{
  background: var(--steel);
}}
</style>
"""


_SIDEBAR_CARD_PATH = _ASSETS_DIR / "opps_sidebar_card.png"
_ABOUT_CARD_IMG_PATH = _ASSETS_DIR / "opps_about_card.png"


def sidebar_brand_card():
    """
    Renders the larger OPPS logo card + About description in the sidebar,
    below the automatic page-navigation links (Streamlit always renders
    the multipage nav first; anything written to st.sidebar afterward is
    appended below it automatically — no manual ordering needed). This is
    separate from the small st.logo() icon set in inject_theme(), which
    stays as-is above the nav.

    The About card (title + body text) is a single pre-rendered PNG
    (assets/opps_about_card.png), not CSS-styled HTML — two rounds of
    CSS-based attempts (class selectors, then inline style="..." with
    !important) both still rendered with black text in practice, despite
    passing every check available in this environment (parser-level
    verification, confirmed presence in the rendered output). Rather than
    keep guessing at a CSS/sanitizer interaction that isn't reproducible
    here, the text color is now baked into the image itself, which no
    stylesheet can override. To edit the wording, regenerate this PNG
    (see the generation script) rather than editing text in this file.
    """
    if _SIDEBAR_CARD_PATH.exists():
        st.sidebar.image(str(_SIDEBAR_CARD_PATH), use_container_width=True)
    if _ABOUT_CARD_IMG_PATH.exists():
        st.sidebar.image(str(_ABOUT_CARD_IMG_PATH), use_container_width=True)


def inject_theme():
    """Call once near the top of every page, right after st.set_page_config()."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    if _LOGO_PATH.exists():
        try:
            st.logo(str(_LOGO_PATH), size="large")
        except Exception:
            pass  # older Streamlit without st.logo support — degrade silently
    sidebar_brand_card()


def masthead(title: str, subtitle: str = "", eyebrow: str = ""):
    """
    Renders the page header used in place of an emoji-led st.title().
    eyebrow is optional — pass "" (default) to omit the small label line.
    Built as a single-line HTML string deliberately: any leading whitespace
    on HTML passed to st.markdown() gets treated as an indented Markdown
    code block (4+ spaces = code block per CommonMark) and rendered as
    literal escaped text instead of parsed HTML. Single-line avoids that
    entirely, regardless of the Python indentation level this is called from.
    """
    eyebrow_html = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    sub_html = f'<div class="subtitle">{subtitle}</div>' if subtitle else ""
    html = f'<div class="masthead">{eyebrow_html}<div class="title">{title}</div>{sub_html}</div>'
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chart color system
# ---------------------------------------------------------------------------
# Neutral grey ramp for anything that isn't crash/violation/gap-specific
# (e.g. officer-capacity heatmap, officer-count maps).
GREY_SEQUENTIAL = ["#F2F2F2", "#D9D9D9", "#BFBFBF", "#8C8C8C", "#595959", "#333333"]

# Fixed-hue ramps (light-to-dark) for crash (red) and violation (blue) charts.
RED_SEQUENTIAL = ["#FBEAEA", "#F0BFBF", "#DD8A8A", "#C64F4F", CRASH_COLOR, "#7A0D0D"]
BLUE_SEQUENTIAL = ["#E9EBF5", "#C3C9E6", "#8E97CE", "#5763AC", VIOLATION_COLOR, "#1B2352"]

PLOTLY_TEMPLATE_LAYOUT = dict(
    font=dict(family="Nunito, sans-serif", color="#262626"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=30, l=10, r=10, b=10),
)


def style_fig(fig, title: str = None):
    """
    Apply the console visual identity (font, transparent bg) to a plotly
    figure. Always explicitly sets a title (even if empty string) — plotly's
    newer map trace types (scatter_map/choropleth_map) can render the
    literal text "undefined" in the title area if title_font is styled
    without title.text ever being set, so we never leave it unset.
    """
    layout = dict(PLOTLY_TEMPLATE_LAYOUT)
    resolved_title = title if title is not None else ""
    layout["title"] = dict(text=resolved_title, font=dict(family="Nunito, sans-serif", size=16, color="#262626"))
    fig.update_layout(**layout)
    return fig
