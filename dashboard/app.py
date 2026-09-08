"""FAIR Acoustic Component Platform — Streamlit landing page."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.backend.fair_bridge import ensure_state, packages
from dashboard.ui.fair_dashboard import hero, inject_platform_css

st.set_page_config(
    page_title="FAIR Acoustic Component Platform",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_platform_css()
ensure_state()

hero(
    "Research data packages for acoustic building components",
    "Connect IFC geometry, experimental measurements and semantic metadata in one FAIR-oriented package, then keep the relationship trustworthy through lifecycle stewardship.",
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Packages", len(packages()))
c2.metric("Geometry", "IFC")
c3.metric("Metadata", "RDF / Turtle")
c4.metric("Stewardship", "Version-aware")

st.markdown("### Platform workflow")
flow = st.columns(4)
items = [
    ("01", "Build", "Upload IFC + measurement data and describe the research context."),
    ("02", "Assess FAIR", "Inspect Findable, Accessible, Interoperable and Reusable checks."),
    ("03", "Steward", "Run the preserved lifecycle engine over the linked evidence."),
    ("04", "Reuse", "Search the component library and export portable FAIR packages."),
]
for col, (number, title, text) in zip(flow, items):
    col.markdown(
        f'<div class="section-card"><span class="pill">{number}</span><h3>{title}</h3><p>{text}</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("### Research architecture")
left, right = st.columns([1.4, 1])
with left:
    st.markdown(
        """
        **FAIR Acoustic Package** is the aggregate research object. It combines IFC geometry, a measurement dataset and RDF metadata without overwriting the source files.

        **Lifecycle Stewardship** remains a separate assessment dimension. A package can therefore be FAIR-ready while stale, or currently acceptable while still missing reuse metadata such as a license.
        """
    )
with right:
    st.code(
        "IFC Geometry\n      +\nMeasurement Dataset\n      +\nRDF Metadata\n      ↓\nFAIR Package\n      ↓\nFAIR Assessment + Lifecycle Stewardship",
        language=None,
    )

st.info("Use the sidebar to open the four FAIR workspaces. The previous lifecycle code remains in the repository and is reused by the Stewardship workspace.")
