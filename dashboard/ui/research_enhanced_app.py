from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.backend.fair_bridge import (
    delete_package,
    ensure_state,
    get_package,
    packages,
    set_current,
    update_package,
)
from dashboard.ui.fair_dashboard import badge, empty_state, hero, inject_platform_css
from dashboard.ui.platform_app import render_stewardship
from dashboard.ui.research_builder import render_research_builder
from fair_platform.catalog import MetadataCatalog
from fair_platform.export import export_research_object, refresh_derived_assets
from fair_platform.metadata import metadata_turtle
from fair_platform.research_object import relationship_strength_statement, GeometryMeasurementRelationship
from fair_platform.ro_crate import RO_CRATE_METADATA


NAV_ITEMS = [
    "Overview",
    "Build Research Object",
    "Component Library",
    "Relationship Evidence",
    "FAIR-Support Assessment",
    "Lifecycle Stewardship",
    "RDF/JSON-LD Explorer",
    "Documentation",
]

DOCS = [
    "docs/research_positioning.md",
    "docs/acoustic_component_ro_profile.md",
    "docs/metadata_profile.md",
    "docs/relationship_evidence_model.md",
    "docs/fair_assessment_profile.md",
    "docs/lifecycle_stewardship.md",
    "docs/package_specification.md",
    "docs/migration_matrix.md",
]


def _sidebar() -> str:
    with st.sidebar:
        st.markdown("### ◈ Acoustic Research Object")
        st.caption("IFC · acoustic data · qualified evidence · RO-Crate · stewardship")
        st.divider()
        selected = st.radio("Workspace", NAV_ITEMS, label_visibility="collapsed", key="ro_workspace")
        st.divider()
        package = get_package()
        if package:
            st.caption("CURRENT RESEARCH OBJECT")
            st.markdown(f"**{package.package_id}**")
            st.caption(package.title)
            st.markdown(f"**FAIR support**  \\n{package.fair_support_status}")
            st.markdown(f"**Lifecycle**  \\n{package.lifecycle_display_status}")
            st.markdown(f"**Acoustic suitability**  \\n{package.scientific_suitability_status}")
        else:
            st.caption("No research object selected")
        st.divider()
        st.caption(f"{len(packages())} local research object(s)")
        st.caption("Prototype catalog only · no DOI issuance · no preservation guarantee")
    return selected


def render_overview() -> None:
    hero(
        "Acoustic Component Research Objects",
        "A prototype FAIR-oriented acoustic component research-object profile and workflow for IFC-linked measurement datasets, with qualified relationship evidence and lifecycle stewardship.",
        "Research positioning",
    )
    st.warning(
        "This prototype evaluates metadata, package structure, and relationship stewardship. "
        "It does not establish the scientific validity or acoustic suitability of measurement values."
    )
    columns = st.columns(4)
    cards = [
        ("IFC", "Component geometry, semantics and identity. The IFC file remains authoritative; metadata only summarizes the selected component."),
        ("Acoustic data", "Measurement, processed/derived data, reference/manufacturer values, predictions and simulation results are explicitly distinguished."),
        ("Metadata + RO-Crate", "The in-memory model is authoritative; RO-Crate JSON-LD is the portable representation, Turtle is domain RDF, and manifest.json is derived compatibility metadata."),
        ("Stewardship", "FAIR-support evaluates selected metadata indicators; lifecycle evaluates whether the geometry↔measurement claim remains defensible. Acoustic suitability stays separate."),
    ]
    for col, (title, text) in zip(columns, cards):
        with col:
            st.markdown(f"### {title}")
            st.write(text)

    st.markdown("### Complementary standards and concepts")
    st.markdown(
        "- **FAIR** supplies design and evaluation principles; it is not the research object itself.\n"
        "- **RO-Crate / research-object principles** provide the generic packaging baseline.\n"
        "- **IFC** represents building-component information and identity.\n"
        "- **IDS** can express IFC-side delivery requirements; it is not an alternative to FAIR.\n"
        "- **bSDD** can support shared property semantics where real concept URIs are available.\n"
        "- **RDF/Linked Data** makes package entities, qualified relationships, provenance and assessments machine-readable."
    )

    all_packages = packages()
    a, b, c, d = st.columns(4)
    a.metric("Local objects", len(all_packages))
    b.metric("Prototype-ready", sum(p.fair_support_status == "READY_FOR_PROTOTYPE_REUSE" for p in all_packages))
    c.metric("Lifecycle acceptable", sum(p.lifecycle_display_status == "ACCEPTABLE" for p in all_packages))
    d.metric("Relationships", sum(len(p.relationships) for p in all_packages))

    st.markdown("### Workflow")
    st.code(
        "1 Load IFC → 2 Load acoustic data → 3 Create qualified relationship → 4 Complete metadata\n"
        "→ 5 Validate → 6 Review FAIR/lifecycle/manual items → 7 Export RO-Crate-style research object",
        language=None,
    )


def render_library() -> None:
    hero(
        "Component Library",
        "A local prototype catalog of acoustic component research objects. Search and inspect packages, relationships, source assets, RDF/JSON-LD and assessment reports. This is not a certified repository and does not issue DOIs.",
        "Workspace 03 · Prototype catalog",
    )
    all_packages = packages()
    if not all_packages:
        empty_state("Library empty", "Create a research object first.")
        return

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    query = f1.text_input("Search title, GlobalId, IFC type, component type, measurement type or metadata")
    fair_values = ["ALL"] + sorted({p.fair_support_status for p in all_packages})
    lifecycle_values = ["ALL"] + sorted({p.lifecycle_display_status for p in all_packages})
    measurement_values = ["ALL"] + sorted({str(p.measurement_context.get("measurement_type")) for p in all_packages if p.measurement_context.get("measurement_type")})
    fair_filter = f2.selectbox("FAIR support", fair_values)
    lifecycle_filter = f3.selectbox("Lifecycle", lifecycle_values)
    measurement_filter = f4.selectbox("Measurement type", measurement_values)

    needle = query.strip().lower()
    results = []
    for p in all_packages:
        haystack = " ".join([
            p.package_id,
            p.identifier or "",
            p.title,
            p.ifc_global_id or "",
            str(p.metadata),
            str(p.measurement_context),
            str(p.relationships),
        ]).lower()
        if needle and needle not in haystack:
            continue
        if fair_filter != "ALL" and p.fair_support_status != fair_filter:
            continue
        if lifecycle_filter != "ALL" and p.lifecycle_display_status != lifecycle_filter:
            continue
        if measurement_filter != "ALL" and str(p.measurement_context.get("measurement_type")) != measurement_filter:
            continue
        results.append(p)

    st.caption(f"{len(results)} research object(s) in the current view")
    for p in results:
        with st.container(border=True):
            top = st.columns([2.3, 1, 1, 1])
            top[0].markdown(f"### {p.title}\n`{p.package_id}`")
            top[1].metric("FAIR support", p.fair_support_status)
            top[2].metric("Lifecycle", p.lifecycle_display_status)
            top[3].metric("Relationships", len(p.relationships))
            st.caption(
                f"GlobalId: {p.ifc_global_id or 'missing'} · IFC type: {p.metadata.get('geometry_ifc_class') or 'unknown'} · "
                f"Measurement: {p.metadata.get('measurement_identifier') or 'missing'} · Origin: {p.measurement_context.get('origin_classification') or 'unknown'}"
            )
            actions = st.columns([1, 1, 1, 1, 2])
            if actions[0].button("Select", key=f"ro_select_{p.package_id}"):
                set_current(p.package_id)
                st.success("Research object selected.")
            actions[1].download_button(
                "Download ZIP",
                export_research_object(p, strict=False),
                file_name=f"{p.package_id}.zip",
                mime="application/zip",
                key=f"ro_download_{p.package_id}",
            )
            with actions[2].popover("Metadata"):
                st.json(p.to_dict())
            with actions[3].popover("Relationships"):
                st.json(p.relationships)
            if actions[4].button("Delete local object", key=f"ro_delete_{p.package_id}"):
                delete_package(p.package_id)
                st.rerun()


def render_relationship_evidence() -> None:
    hero(
        "Relationship Evidence",
        "Inspect the qualified claim connecting IFC component identity to acoustic data. Direct measurement, equivalence, prediction and reference relationships are intentionally not treated as equivalent.",
        "Workspace 04 · Qualified geometry-measurement relationship",
    )
    package = get_package()
    if not package:
        empty_state("No object selected", "Create or select a research object in the Component Library.")
        return
    if not package.relationships:
        st.error("No qualified geometry-measurement relationship is present. This research object requires review.")
        return

    for raw in package.relationships:
        try:
            relationship = GeometryMeasurementRelationship.from_dict(raw)
            statement = relationship_strength_statement(relationship)
        except Exception:
            relationship = None
            statement = "Relationship record could not be reconstructed into the current profile model."
        with st.container(border=True):
            st.markdown(f"### {raw.get('relationship_type', 'unknownRelationship')} · `{raw.get('relationship_id', 'missing')}`")
            st.write(statement)
            a, b, c = st.columns(3)
            a.metric("IFC GlobalId", raw.get("subject_ifc_global_id") or "missing")
            b.metric("Measurement ID", raw.get("object_measurement_id") or "missing")
            c.metric("Relationship status", raw.get("status") or "UNASSESSED")
            st.markdown("**Rationale**")
            st.write(raw.get("rationale") or "No rationale supplied.")
            st.markdown("**Matching / excluded attributes**")
            st.json({"matching": raw.get("matching_attributes", []), "excluded": raw.get("excluded_attributes", [])})
            st.markdown("#### Structured evidence")
            evidence = raw.get("evidence", [])
            if evidence:
                st.dataframe(evidence, use_container_width=True, hide_index=True)
            else:
                st.warning("No structured relationship evidence was supplied.")
            if raw.get("trigger_history"):
                st.markdown("#### Reassessment trigger history")
                st.dataframe(raw["trigger_history"], use_container_width=True, hide_index=True)
            if raw.get("decision_history"):
                st.markdown("#### Decision history")
                st.dataframe(raw["decision_history"], use_container_width=True, hide_index=True)


def render_fair_support() -> None:
    hero(
        "FAIR-Support Assessment",
        "Evidence-based evaluation of selected Findable, Accessible, Interoperable and Reusable indicators for this prototype profile. The result is a reuse-readiness aid, not FAIR certification.",
        "Workspace 05 · Selected FAIR indicators",
    )
    package = get_package()
    if not package:
        empty_state("No object selected", "Create or select a research object first.")
        return

    if st.button("Re-run FAIR-support and package validation", type="primary", use_container_width=True):
        refresh_derived_assets(package)
        update_package(package)
        st.success("Assessment and derived package representations refreshed.")

    assessment = package.fair_support_assessment or {}
    st.markdown("### Independent outcomes")
    a, b, c = st.columns(3)
    a.metric("FAIR support", package.fair_support_status)
    b.metric("Lifecycle stewardship", package.lifecycle_display_status)
    c.metric("Acoustic suitability", package.scientific_suitability_status)
    st.caption("These outcomes are independent. Metadata completeness is not scientific acoustic validity.")

    dimensions = assessment.get("dimensions", {})
    if dimensions:
        cols = st.columns(4)
        for col, name in zip(cols, ["Findable", "Accessible", "Interoperable", "Reusable"]):
            data = dimensions.get(name, {})
            col.metric(name, f"{float(data.get('score', 0)):.0%}")

    criteria = assessment.get("criteria", [])
    if criteria:
        st.markdown("### Criterion evidence")
        st.dataframe(
            [
                {
                    "ID": item.get("criterion_id"),
                    "Dimension": item.get("fair_dimension"),
                    "Criterion": item.get("label"),
                    "Priority": item.get("priority"),
                    "Status": item.get("status"),
                    "Evidence": item.get("evidence"),
                    "Missing": item.get("missing_information"),
                    "Recommendation": item.get("recommendation"),
                    "Manual review": item.get("manual_review_required"),
                }
                for item in criteria
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("No FAIR-support assessment is stored yet.")

    with st.expander("Assessment limitations", expanded=True):
        for limitation in assessment.get("limitations", []):
            st.write(f"- {limitation}")
    with st.expander("Package validation report"):
        st.json(package.validation_report or {})


def render_lifecycle() -> None:
    st.info(
        "Lifecycle stewardship evaluates whether the geometry↔measurement relationship remains defensible as sources, versions or evidence change. It does not determine FAIR certification or acoustic scientific suitability."
    )
    render_stewardship()


def render_rdf_explorer() -> None:
    hero(
        "RDF / JSON-LD Explorer",
        "Inspect the two synchronized portable metadata representations: RO-Crate-style JSON-LD for package portability and domain RDF/Turtle for qualified relationships, provenance and stewardship.",
        "Workspace 07 · Machine-readable evidence",
    )
    package = get_package()
    if not package:
        empty_state("No object selected", "Select a research object first.")
        return
    refresh_derived_assets(package)
    crate_bytes = package.assets.get(RO_CRATE_METADATA, b"{}")
    turtle = metadata_turtle(package)
    tabs = st.tabs(["RO-Crate JSON-LD", "Domain RDF / Turtle", "Manifest", "Reports", "SPARQL catalog"])
    with tabs[0]:
        try:
            st.json(json.loads(crate_bytes.decode("utf-8")))
        except Exception:
            st.code(crate_bytes.decode("utf-8", errors="replace"), language="json")
        st.download_button("Download ro-crate-metadata.json", crate_bytes, RO_CRATE_METADATA, "application/ld+json")
    with tabs[1]:
        st.code(turtle, language="turtle")
        st.download_button("Download metadata.ttl", turtle, f"{package.package_id}-metadata.ttl", "text/turtle")
    with tabs[2]:
        st.json(json.loads(package.assets.get("manifest.json", b"{}").decode("utf-8")))
    with tabs[3]:
        report_names = sorted(path for path in package.assets if path.startswith("reports/") and path.endswith(".json"))
        selected = st.selectbox("Report", report_names)
        if selected:
            st.json(json.loads(package.assets[selected].decode("utf-8")))
    with tabs[4]:
        catalog = MetadataCatalog(packages())
        default_query = """PREFIX dct: <http://purl.org/dc/terms/>\nSELECT ?resource ?title WHERE { ?resource dct:title ?title . } ORDER BY ?title"""
        query = st.text_area("SPARQL", value=default_query, height=140)
        if st.button("Run SPARQL"):
            try:
                st.dataframe(catalog.sparql(query), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"SPARQL query failed: {exc}")


def render_documentation() -> None:
    hero(
        "Documentation",
        "Research positioning, prototype research-object profile, metadata profile, relationship evidence model, FAIR-support criteria, lifecycle stewardship and package specification.",
        "Workspace 08 · Thesis and implementation documentation",
    )
    st.warning("The profile is a research prototype. It is not an approved community acoustic metadata standard, certified FAIR method, or RO-Crate community profile.")
    selected = st.selectbox("Document", DOCS, format_func=lambda value: Path(value).name)
    path = Path(selected)
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.error(f"Documentation file is not available in this deployment: {selected}")


def run_research_enhanced_app() -> None:
    st.set_page_config(
        page_title="Acoustic Component Research Object",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_platform_css()
    ensure_state()
    selected = _sidebar()
    if selected == "Overview":
        render_overview()
    elif selected == "Build Research Object":
        render_research_builder()
    elif selected == "Component Library":
        render_library()
    elif selected == "Relationship Evidence":
        render_relationship_evidence()
    elif selected == "FAIR-Support Assessment":
        render_fair_support()
    elif selected == "Lifecycle Stewardship":
        render_lifecycle()
    elif selected == "RDF/JSON-LD Explorer":
        render_rdf_explorer()
    else:
        render_documentation()
