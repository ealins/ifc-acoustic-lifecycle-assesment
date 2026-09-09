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
from dashboard.ui.fair_dashboard import empty_state, hero, inject_platform_css
from dashboard.ui.platform_app import render_stewardship
from dashboard.ui.research_builder import render_research_builder
from fair_platform.catalog import MetadataCatalog
from fair_platform.export import export_research_object, refresh_derived_assets
from fair_platform.metadata import metadata_turtle
from fair_platform.metadata_profile import PROFILE_FIELDS, PROFILE_LABEL, PROFILE_VERSION
from fair_platform.research_object import GeometryMeasurementRelationship, relationship_strength_statement
from fair_platform.ro_crate import RO_CRATE_METADATA


NAV_ITEMS = [
    "Overview",
    "Build Component Package",
    "Metadata Profile",
    "Component Library",
    "Metadata Completeness",
    "FAIR-Support Assessment",
    "Relationship Lifecycle Assessment",
    "RDF / JSON-LD Explorer",
    "Documentation",
]

DOCS = [
    "docs/research_positioning.md",
    "docs/acoustic_metadata_profile.md",
    "docs/acoustic_component_package.md",
    "docs/component_dataset_relationship.md",
    "docs/metadata_completeness_assessment.md",
    "docs/fair_support_assessment.md",
    "docs/relationship_lifecycle_assessment.md",
    "docs/package_specification.md",
    "docs/ids_bsdd_positioning.md",
    "docs/evaluation_methodology.md",
    "docs/migration_matrix.md",
]


def _sidebar() -> str:
    with st.sidebar:
        st.markdown("### ◈ Acoustic Component Metadata")
        st.caption("IFC · acoustic data · metadata profile · package · relationship stewardship")
        st.divider()
        selected = st.radio("Workspace", NAV_ITEMS, label_visibility="collapsed", key="ro_workspace")
        st.divider()
        package = get_package()
        if package:
            st.caption("CURRENT COMPONENT PACKAGE")
            st.markdown(f"**{package.package_id}**")
            st.caption(package.title)
            st.markdown(f"**Metadata completeness**  \\n{package.metadata_completeness_status}")
            st.markdown(f"**FAIR support**  \\n{package.fair_support_status}")
            st.markdown(f"**Relationship lifecycle**  \\n{package.lifecycle_display_status}")
            st.markdown(f"**Acoustic suitability**  \\n{package.scientific_suitability_status}")
        else:
            st.caption("No component package selected")
        st.divider()
        st.caption(f"{len(packages())} local package(s)")
        st.caption("Prototype library only · no DOI issuance · no preservation guarantee")
    return selected


def render_overview() -> None:
    hero(
        "FAIR-Oriented Acoustic Component Metadata and Package Workflow",
        "A prototype FAIR-oriented metadata profile, research-object package, and workflow for reusable acoustic component datasets linked to IFC representations.",
        "Revised thesis research positioning",
    )
    st.warning(
        "This prototype evaluates metadata coverage, package structure, FAIR support, and component-dataset relationship status. "
        "It does not establish the scientific validity or acoustic suitability of the measurement values."
    )

    st.markdown("### Research problem")
    st.write(
        "An IFC component representation and an acoustic dataset can be managed independently, but they are not automatically reusable together. "
        "The package must identify the component and dataset, describe how the acoustic record originated, preserve provenance/access/rights/version/quality metadata, and make the relationship evidence explicit and reviewable."
    )

    columns = st.columns(4)
    cards = [
        ("IFC component", "IFC remains authoritative for component identity, geometry, placement, materials, layers, spatial context, GlobalId, and source-model evidence."),
        ("Acoustic dataset", "Scientific/catalog/reference values remain in their source files. Origin is explicitly classified rather than inferred from format."),
        ("Metadata profile + package", f"{PROFILE_LABEL} v{PROFILE_VERSION} defines the selected use-case fields. The research object operationalizes the profile and preserves source assets/references."),
        ("Qualified relationship", "The component-dataset claim is typed, evidenced, versioned, reviewable, and lifecycle-assessed independently from metadata completeness and FAIR support."),
    ]
    for col, (title, text) in zip(columns, cards):
        with col:
            st.markdown(f"### {title}")
            st.write(text)

    st.markdown("### Role of FAIR, RO-Crate, IDS, and bSDD")
    st.markdown(
        "- **FAIR** guides metadata design and supplies selected evaluation indicators; this prototype does not certify FAIR compliance.\n"
        "- **RO-Crate** supplies the generic JSON-LD research-object packaging pattern; it is not a thesis invention.\n"
        "- **IDS** may validate IFC-side information requirements, but does not replace acoustic research-data metadata.\n"
        "- **bSDD** may provide shared definitions/classification URIs where actually supplied, but does not store the acoustic dataset, licence, provenance, or package lifecycle."
    )

    st.markdown("### Primary artifact and supporting mechanisms")
    st.code(
        "PRIMARY ARTIFACT\n"
        "Acoustic Component Research Object\n"
        "  ├─ defined by: FAIR-oriented Acoustic Metadata Profile + Package Model\n"
        "  ├─ operationalized by: Package Creation + Prototype Component Library\n"
        "  ├─ connected by: Qualified Component–Dataset Relationship + Evidence\n"
        "  ├─ maintained by: Relationship Lifecycle Stewardship\n"
        "  └─ evaluated by: Metadata Completeness + Selected FAIR Indicators + Package Integrity + Controlled Lifecycle Scenarios",
        language=None,
    )

    all_packages = packages()
    a, b, c, d = st.columns(4)
    a.metric("Local packages", len(all_packages))
    b.metric("Complete for prototype", sum(p.metadata_completeness_status == "COMPLETE_FOR_PROTOTYPE" for p in all_packages))
    c.metric("FAIR-support ready", sum(p.fair_support_status == "READY_FOR_PROTOTYPE_REUSE" for p in all_packages))
    d.metric("Lifecycle acceptable", sum(p.lifecycle_display_status == "ACCEPTABLE" for p in all_packages))

    st.markdown("### Metadata-centered workflow")
    st.code(
        "1 IFC → 2 Acoustic dataset → 3 Component-dataset connection → 4 Complete metadata → 5 Validate\n"
        "→ 6 Metadata completeness → 7 FAIR support → 8 Relationship lifecycle → 9 Preview → 10 Export + catalog",
        language=None,
    )


def render_metadata_profile() -> None:
    hero(
        "Metadata Profile",
        "Executable field register for the Prototype FAIR-Oriented Acoustic Component Metadata Profile. Requirement levels and conditional rules drive completeness assessment and package validation.",
        "Workspace 03 · Primary thesis artifact",
    )
    st.info(
        "The profile is specific to the selected IFC/acoustic use case. It is not a universal acoustic metadata standard. "
        "Values may be automatically extracted, user-entered, source-derived, unverified, missing, or not applicable."
    )
    categories = sorted({field.category.value for field in PROFILE_FIELDS})
    category = st.selectbox("Metadata category", ["ALL"] + categories)
    requirements = sorted({field.requirement_level.value for field in PROFILE_FIELDS})
    requirement = st.selectbox("Requirement level", ["ALL"] + requirements)
    rows = []
    for field in PROFILE_FIELDS:
        if category != "ALL" and field.category.value != category:
            continue
        if requirement != "ALL" and field.requirement_level.value != requirement:
            continue
        rows.append({
            "Field": field.field_name,
            "Label": field.label,
            "Category": field.category.value,
            "Requirement": field.requirement_level.value,
            "Conditional rule": field.conditional_requirement,
            "Source": field.source_of_value,
            "Acquisition": field.acquisition,
            "Cardinality": field.cardinality,
            "FAIR dimension": field.fair_dimension,
        })
    st.caption(f"{len(rows)} profile fields in the current view")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    field_name = st.selectbox("Inspect complete field definition", [field.field_name for field in PROFILE_FIELDS])
    definition = next(field for field in PROFILE_FIELDS if field.field_name == field_name)
    st.json(definition.to_dict())
    st.caption("Machine-readable profile snapshots are exported as `profiles/acoustic-metadata-profile.json` from this same executable definition.")


def render_library() -> None:
    hero(
        "Component Library",
        "Searchable local prototype library of acoustic component packages. Inspect metadata, provenance, relationship evidence, source versions, RDF/JSON-LD, assessment results, and downloadable package archives.",
        "Workspace 04 · Prototype component library",
    )
    st.warning("This is a prototype library, not a certified repository, DOI registration service, or guaranteed long-term preservation service.")
    all_packages = packages()
    if not all_packages:
        empty_state("Library empty", "Create a component package first.")
        return

    catalog = MetadataCatalog(all_packages)
    f1, f2, f3 = st.columns([2, 1, 1])
    query = f1.text_input("Search title, GlobalId, dataset ID, type, provenance, relationship, or metadata")
    ifc_values = ["ALL"] + sorted({str(p.metadata.get("geometry_ifc_class")) for p in all_packages if p.metadata.get("geometry_ifc_class")})
    type_values = ["ALL"] + sorted({str(p.measurement_context.get("measurement_type")) for p in all_packages if p.measurement_context.get("measurement_type")})
    ifc_filter = f2.selectbox("IFC component type", ifc_values)
    type_filter = f3.selectbox("Dataset/record type", type_values)

    g1, g2, g3, g4 = st.columns(4)
    origin_values = ["ALL"] + sorted({str(p.measurement_context.get("origin_classification")) for p in all_packages if p.measurement_context.get("origin_classification")})
    completeness_values = ["ALL"] + sorted({p.metadata_completeness_status for p in all_packages})
    fair_values = ["ALL"] + sorted({p.fair_support_status for p in all_packages})
    lifecycle_values = ["ALL"] + sorted({p.lifecycle_display_status for p in all_packages})
    origin_filter = g1.selectbox("Dataset origin", origin_values)
    completeness_filter = g2.selectbox("Metadata completeness", completeness_values)
    fair_filter = g3.selectbox("FAIR support", fair_values)
    lifecycle_filter = g4.selectbox("Relationship status", lifecycle_values)

    results = catalog.search(
        query,
        fair_support_status=fair_filter,
        metadata_completeness=completeness_filter,
        lifecycle_status=lifecycle_filter,
        measurement_type=type_filter,
        dataset_origin=origin_filter,
        ifc_type=ifc_filter,
    )
    st.caption(f"{len(results)} package(s) in the current view")
    for p in results:
        entry = catalog.entry(p)
        with st.container(border=True):
            top = st.columns([2.4, 1, 1, 1])
            top[0].markdown(f"### {p.title}\n`{p.package_id}`")
            top[1].metric("Metadata", p.metadata_completeness_status)
            top[2].metric("FAIR support", p.fair_support_status)
            top[3].metric("Lifecycle", p.lifecycle_display_status)
            st.caption(
                f"GlobalId: {entry['ifc_global_id'] or 'missing'} · IFC type: {entry['ifc_component_type'] or 'unknown'} · "
                f"Dataset: {entry['acoustic_dataset_identifier'] or 'missing'} · Origin: {entry['dataset_origin'] or 'unknown'} · "
                f"Version: {entry['package_version']} · Last review: {entry['last_review_date'] or 'not recorded'}"
            )
            actions = st.columns([1, 1, 1, 1, 1, 1.3])
            if actions[0].button("Select", key=f"select_{p.package_id}"):
                set_current(p.package_id)
                st.success("Package selected.")
            actions[1].download_button("Download", export_research_object(p, strict=False), file_name=f"{p.package_id}.zip", mime="application/zip", key=f"download_{p.package_id}")
            with actions[2].popover("Metadata"):
                st.json(p.to_dict())
            with actions[3].popover("Provenance"):
                st.json(p.provenance)
            with actions[4].popover("Evidence"):
                st.json(p.relationships)
            with actions[5].popover("RDF / JSON-LD"):
                st.code(metadata_turtle(p), language="turtle")
                try:
                    st.json(json.loads(p.assets.get(RO_CRATE_METADATA, b"{}").decode("utf-8")))
                except Exception:
                    pass
            if st.button("Delete local package", key=f"delete_{p.package_id}"):
                delete_package(p.package_id)
                st.rerun()


def render_metadata_completeness() -> None:
    hero(
        "Metadata Completeness",
        "Evaluate profile-required, conditionally required, recommended, invalid, unverified, and manual-review metadata independently from FAIR support and relationship lifecycle status.",
        "Workspace 05 · Primary evaluation mechanism",
    )
    package = get_package()
    if not package:
        empty_state("No package selected", "Create or select a component package first.")
        return
    if st.button("Re-run metadata completeness and package validation", type="primary", use_container_width=True):
        refresh_derived_assets(package)
        update_package(package)
        st.success("Metadata completeness and derived package reports refreshed.")

    assessment = package.metadata_completeness_assessment or {}
    summary = assessment.get("summary", {})
    st.markdown("### Independent outcomes")
    cols = st.columns(4)
    cols[0].metric("Metadata completeness", package.metadata_completeness_status)
    cols[1].metric("FAIR support", package.fair_support_status)
    cols[2].metric("Relationship lifecycle", package.lifecycle_display_status)
    cols[3].metric("Acoustic suitability", package.scientific_suitability_status)

    a, b, c, d = st.columns(4)
    a.metric("Required fields satisfied", f"{summary.get('required_fields_satisfied', 0)}/{summary.get('required_fields_total', 0)}")
    b.metric("Active conditional fields", summary.get("conditional_fields_active", 0))
    c.metric("Recommended present", f"{summary.get('recommended_fields_present', 0)}/{summary.get('recommended_fields_total', 0)}")
    d.metric("Invalid / unverified", int(summary.get("invalid_values", 0)) + int(summary.get("unverified_values", 0)))
    st.caption("These are metadata coverage/check counts, not a FAIR compliance score or acoustic quality score.")

    fields = assessment.get("fields", [])
    f1, f2, f3 = st.columns(3)
    category = f1.selectbox("Category", ["ALL"] + sorted({str(item.get("category")) for item in fields}))
    status = f2.selectbox("Field status", ["ALL"] + sorted({str(item.get("status")) for item in fields}))
    requirement = f3.selectbox("Requirement", ["ALL"] + sorted({str(item.get("requirement_level")) for item in fields}))
    visible = [
        item for item in fields
        if (category == "ALL" or item.get("category") == category)
        and (status == "ALL" or item.get("status") == status)
        and (requirement == "ALL" or item.get("requirement_level") == requirement)
    ]
    st.dataframe(
        [{
            "Field": item.get("field_name"),
            "Label": item.get("label"),
            "Category": item.get("category"),
            "Requirement": item.get("requirement_level"),
            "Applicable": item.get("applicable"),
            "Status": item.get("status"),
            "Source": item.get("source"),
            "Recommendation": item.get("recommendation"),
        } for item in visible],
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Assessment limitations", expanded=True):
        for limitation in assessment.get("limitations", []):
            st.write(f"- {limitation}")


def render_fair_support() -> None:
    hero(
        "FAIR-Support Assessment",
        "Evidence-based evaluation of selected Findable, Accessible, Interoperable, and Reusable indicators. The result is a reuse-readiness aid, not FAIR certification.",
        "Workspace 06 · Selected FAIR indicators",
    )
    package = get_package()
    if not package:
        empty_state("No package selected", "Create or select a component package first.")
        return
    if st.button("Re-run FAIR-support and package validation", type="primary", use_container_width=True):
        refresh_derived_assets(package)
        update_package(package)
        st.success("FAIR-support assessment and derived representations refreshed.")

    assessment = package.fair_support_assessment or {}
    outcomes = st.columns(4)
    outcomes[0].metric("Metadata completeness", package.metadata_completeness_status)
    outcomes[1].metric("FAIR support", package.fair_support_status)
    outcomes[2].metric("Relationship lifecycle", package.lifecycle_display_status)
    outcomes[3].metric("Acoustic suitability", package.scientific_suitability_status)
    st.caption("These outcomes are independent. FAIR reusability does not prove scientific acoustic validity.")

    criteria = assessment.get("criteria", [])
    dim_cols = st.columns(4)
    for col, dimension in zip(dim_cols, ["Findable", "Accessible", "Interoperable", "Reusable"]):
        items = [item for item in criteria if item.get("fair_dimension") == dimension and item.get("status") != "NOT_APPLICABLE"]
        passed = sum(item.get("status") == "PASS" for item in items)
        col.metric(dimension, f"{passed}/{len(items)} PASS")
    st.caption("Criterion counts are shown instead of a single FAIR compliance score.")

    if criteria:
        st.dataframe(
            [{
                "ID": item.get("criterion_id"),
                "Dimension": item.get("fair_dimension"),
                "Criterion": item.get("label"),
                "Priority": item.get("priority"),
                "Status": item.get("status"),
                "Evidence": item.get("evidence"),
                "Source": item.get("evidence_source"),
                "Missing": item.get("missing_information"),
                "Recommendation": item.get("recommendation"),
                "Machine-checkable": item.get("machine_checkable"),
                "Manual review": item.get("manual_review_required"),
            } for item in criteria],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("No FAIR-support assessment is stored yet.")
    with st.expander("Assessment limitations", expanded=True):
        for limitation in assessment.get("limitations", []):
            st.write(f"- {limitation}")


def _render_relationship_evidence(package) -> None:
    if not package.relationships:
        st.error("No qualified component-dataset relationship is present.")
        return
    for raw in package.relationships:
        try:
            relationship = GeometryMeasurementRelationship.from_dict(raw)
            statement = relationship_strength_statement(relationship)
        except Exception:
            statement = "Relationship record could not be reconstructed into the current profile model."
        with st.container(border=True):
            st.markdown(f"### {raw.get('relationship_type', 'unknownRelationship')} · `{raw.get('relationship_id', 'missing')}`")
            st.write(statement)
            a, b, c = st.columns(3)
            a.metric("IFC GlobalId", raw.get("subject_ifc_global_id") or "missing")
            b.metric("Dataset ID", raw.get("object_measurement_id") or "missing")
            c.metric("Relationship state", raw.get("status") or package.lifecycle_display_status)
            st.markdown("**Rationale**")
            st.write(raw.get("rationale") or "No rationale supplied.")
            evidence = raw.get("evidence", [])
            st.markdown("#### Structured evidence")
            if evidence:
                st.dataframe(evidence, use_container_width=True, hide_index=True)
            else:
                st.warning("No structured relationship evidence was supplied.")
            if raw.get("trigger_history") or package.reassessment_triggers:
                st.markdown("#### Reassessment triggers")
                st.dataframe(raw.get("trigger_history") or package.reassessment_triggers, use_container_width=True, hide_index=True)
            if raw.get("decision_history"):
                st.markdown("#### Decision history")
                st.dataframe(raw["decision_history"], use_container_width=True, hide_index=True)


def render_relationship_lifecycle() -> None:
    hero(
        "Relationship Lifecycle Assessment",
        "Supporting assessment of whether the explicit IFC component ↔ acoustic dataset connection remains acceptable, stale, broken, ambiguous, unmatched, invalid, or in need of review as sources change.",
        "Workspace 07 · Supporting lifecycle mechanism",
    )
    package = get_package()
    if not package:
        empty_state("No package selected", "Create or select a component package first.")
        return
    st.info(
        "Lifecycle assessment manages the component-dataset relationship. It does not replace the metadata profile, determine FAIR certification, or establish acoustic scientific suitability."
    )
    _render_relationship_evidence(package)
    st.divider()
    render_stewardship()


def render_rdf_explorer() -> None:
    hero(
        "RDF / JSON-LD Explorer",
        "Inspect synchronized machine-readable representations: RO-Crate-style JSON-LD for package portability, domain RDF/Turtle for provenance/relationships/assessments, and the compatibility manifest.",
        "Workspace 08 · Machine-readable research object",
    )
    package = get_package()
    if not package:
        empty_state("No package selected", "Select a component package first.")
        return
    refresh_derived_assets(package)
    crate_bytes = package.assets.get(RO_CRATE_METADATA, b"{}")
    turtle = metadata_turtle(package)
    tabs = st.tabs(["RO-Crate JSON-LD", "Domain RDF / Turtle", "Metadata profile", "Manifest", "Reports", "SPARQL catalog"])
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
        st.json(json.loads(package.assets.get("profiles/acoustic-metadata-profile.json", b"{}").decode("utf-8")))
    with tabs[3]:
        st.json(json.loads(package.assets.get("manifest.json", b"{}").decode("utf-8")))
    with tabs[4]:
        report_names = sorted(path for path in package.assets if (path.startswith("reports/") or path.startswith("evidence/")) and path.endswith(".json"))
        selected = st.selectbox("Report", report_names)
        if selected:
            st.json(json.loads(package.assets[selected].decode("utf-8")))
    with tabs[5]:
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
        "Research positioning, acoustic metadata profile, component package model, relationship evidence, metadata completeness, FAIR support, lifecycle assessment, package specification, IDS/bSDD positioning, and evaluation methodology.",
        "Workspace 09 · Thesis and implementation documentation",
    )
    st.warning("The metadata profile is a research prototype. It is not an approved universal acoustic metadata standard, FAIR certification method, certified repository, or RO-Crate community profile.")
    selected = st.selectbox("Document", DOCS, format_func=lambda value: Path(value).name)
    path = Path(selected)
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.error(f"Documentation file is not available in this deployment: {selected}")


def run_research_enhanced_app() -> None:
    st.set_page_config(
        page_title="Acoustic Component Metadata Profile",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_platform_css()
    ensure_state()
    selected = _sidebar()
    if selected == "Overview":
        render_overview()
    elif selected == "Build Component Package":
        render_research_builder()
    elif selected == "Metadata Profile":
        render_metadata_profile()
    elif selected == "Component Library":
        render_library()
    elif selected == "Metadata Completeness":
        render_metadata_completeness()
    elif selected == "FAIR-Support Assessment":
        render_fair_support()
    elif selected == "Relationship Lifecycle Assessment":
        render_relationship_lifecycle()
    elif selected == "RDF / JSON-LD Explorer":
        render_rdf_explorer()
    else:
        render_documentation()
