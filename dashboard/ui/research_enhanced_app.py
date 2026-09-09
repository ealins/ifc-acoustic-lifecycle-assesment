from __future__ import annotations

import streamlit as st

from dashboard.backend.fair_bridge import ensure_state, get_package
from dashboard.ui.enhanced_app import (
    _sidebar,
    render_enhanced_assessment,
    render_enhanced_library,
    render_enhanced_overview,
    render_platform_evidence,
)
from dashboard.ui.fair_dashboard import inject_platform_css
from dashboard.ui.platform_app import render_stewardship
from dashboard.ui.research_builder import render_research_builder


def render_research_platform_evidence() -> None:
    render_platform_evidence()
    package = get_package()
    if not package:
        return

    st.markdown("### Acoustic research & simulation evidence")
    research = package.research_context or {}
    simulation = package.simulation_context or {}
    simulation_resources = package.metadata.get("simulation_resources", []) or []
    research_resources = package.metadata.get("research_resources", []) or []

    a, b, c, d = st.columns(4)
    a.metric("Study mode", research.get("study_mode", "not specified"))
    b.metric("Numerical method", simulation.get("numerical_method", "not specified"))
    c.metric("Simulation artefacts", len(simulation_resources))
    d.metric("Research artefacts", len(research_resources))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Research design & reproducibility")
        st.json(research or {"status": "No research context stored for this package."})
    with right:
        st.markdown("#### Simulation provenance")
        st.json(simulation or {"status": "No simulation context stored for this package."})

    resources = []
    for item in simulation_resources + research_resources:
        resources.append(
            {
                "Role": item.get("role"),
                "Path": item.get("path"),
                "Source filename": item.get("source_filename"),
                "Media type": item.get("media_type"),
                "Bytes": item.get("size_bytes"),
                "Checksum": package.checksums.get(item.get("path")),
            }
        )
    if resources:
        st.markdown("#### Reproducibility resource inventory")
        st.dataframe(resources, use_container_width=True, hide_index=True)


def run_research_enhanced_app() -> None:
    st.set_page_config(
        page_title="FAIR Acoustic Component Platform",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_platform_css()
    ensure_state()
    selected = _sidebar()
    if selected == "Overview":
        render_enhanced_overview()
    elif selected == "FAIR Package Builder":
        render_research_builder()
    elif selected == "FAIR Assessment":
        render_enhanced_assessment()
    elif selected == "Lifecycle Stewardship":
        render_stewardship()
    elif selected == "Component Library":
        render_enhanced_library()
    else:
        render_research_platform_evidence()
