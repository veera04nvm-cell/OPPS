import streamlit as st

from utils import theme

st.set_page_config(page_title="Help Guide", page_icon="❓", layout="wide")
theme.inject_theme()
theme.masthead(
    title="🔅 Help Guide",
    subtitle="A quick walkthrough of how to use this dashboard and read every chart and map.",
)

st.header("🔅 1. Getting around")
st.markdown(
    """
The dashboard has three pages, listed in the sidebar on the left:

- **📊 Data Insights** - explore historical crash and traffic-stop patterns: where they
  happen, when they happen, and how well today's patrol schedule matches that demand.
- **🗺️ Allocation Comparison** - compare three different ways of assigning officers to
  zones, for any date and shift in the deployment week.
- **❓ Help Guide** - this page.

On the **Data Insights** page, use the filters in the left sidebar (Zones, Days of week,
Hour range) to narrow down what you're looking at. Every chart on the page updates
automatically, and the blue/colored note under each chart re-writes itself to describe
what's currently shown.
"""
)

st.divider()

st.header("🔅 2. The three patrol strategies")
st.markdown(
    """
| Strategy | What it means |
|---|---|
| **Uniform Plan** *(current practice)* | The same number of officers is assigned to every zone, regardless of how much crime or traffic activity happens there. |
| **Static Plan** *(demand-based)* | Officer counts are set once, ahead of time, based on historical crash and stop patterns in each zone and shift. |
| **Dynamic Plan** *(demand-based, day-of)* | Officer counts adjust to more recent, day-specific patterns - it reacts to what's happening close to the actual shift. |

**In short:** Uniform Plan ignores demand entirely - it's the simplest, current default.
Static Plan and Dynamic Plan both try to match patrol coverage to where and when incidents
actually happen; the difference between them is how recent the information they react to is.

**What "Uniform," "Static," and "Dynamic" mean, in more detail:**

- **Uniform** splits officers equally across all 8 zones, no matter how much demand each
  zone has. It's the easiest to run and the current baseline, but it doesn't account for
  the fact that some zones consistently see far more crashes and stops than others.
- **Static** builds one fixed allocation plan ahead of time from several weeks of
  historical demand data, then applies that same plan across the whole deployment period.
  It reflects demand much better than Uniform, but doesn't adjust if a particular day
  turns out busier or quieter than its historical average.
- **Dynamic** re-checks recent, day-specific demand patterns and adjusts officer counts
  accordingly, rather than relying on one fixed plan for the whole period. It's the most
  responsive to real conditions, at the cost of being a more complex plan to produce and
  communicate to officers each shift.
"""
)

st.divider()

st.header("🔅 3. How to read the maps")
st.markdown(
    """
- **Officer placement maps** - each 🚓 icon represents one recommended patrol officer,
  scattered at random points within its assigned zone. More icons in a zone means more
  officers recommended there for that date and shift. The exact position within the zone
  isn't meaningful - only the count per zone is.
- **Coverage gap maps** - these use a purple-to-orange color scale:
    - 🟣 **Purple = under-patrolled.** The zone is getting *less* patrol coverage than its
      share of demand (crashes/stops) would justify.
    - 🟠 **Orange = over-patrolled.** The zone is getting *more* patrol coverage than its
      demand justifies.
    - White/light = roughly balanced - coverage closely matches demand.
"""
)

st.divider()

st.header("🔅 4. How to read the charts")
st.markdown(
    """
- **Hotspot maps** (red dots = crashes, blue dots = traffic stops) show individual
  incident locations for whatever filters are currently applied.
- **Rate-per-mile bar charts** adjust for the fact that some zones simply have more roads
  than others - a zone with a high crash count but also a lot of road miles might have a
  *lower* rate than a small zone with fewer crashes but very few road miles. The rate is
  the fairer comparison.
- **Hour-of-day and day-of-week charts** show when incidents cluster, which should inform
  shift-level staffing decisions, not just which zone gets more officers.
- **Officer capacity heatmap** shows how much of a shift is actually available for
  proactive patrol once briefing, paperwork, meals, and call response time are subtracted.
  Darker shading means more free time to patrol; lighter shading means the shift is
  mostly consumed by other duties.
- **Misalignment chart** on the Data Insights page compares the *current* even-split
  schedule against actual demand - this is the case for why a demand-based plan may help.
"""
)

st.divider()

st.header("🔅 5. Quick tips")
st.markdown(
    """
- Start on **Data Insights** to understand *why* a demand-based plan might help in the
  first place.
- Move to **Allocation Comparison** to see *what* each plan would actually assign, zone by
  zone, for a specific date and shift.
- The colored note box under each chart is meant to be read on its own - it's written in
  plain language and updates with your filters, so you don't need to interpret the raw
  numbers yourself.
- If something looks off (a zone with zero officers, a chart that won't load), it's most
  often a missing data file for that particular date - check with whoever maintains the
  dashboard.
"""
)
