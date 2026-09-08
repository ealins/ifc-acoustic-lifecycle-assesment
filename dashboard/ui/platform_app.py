from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from dashboard.backend.fair_bridge import add_package, delete_package, ensure_state, get_package, packages, set_current, update_package
from dashboard.backend.ifc_parser import extract_walls_from_ifc
from dashboard.ui.fair_dashboard import badge, empty_state, hero, inject_platform_css, render_fair_cards
from fair_platform.assessment import assess_fair
from fair_platform.catalog import MetadataCatalog
from fair_platform.export import export_fair_package, finalize_package
from fair_platform.metadata import metadata_turtle
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.stewardship import FairStewardshipService

NAV_ITEMS = ["Overview", "FAIR Package Builder", "FAIR Assessment", "Lifecycle Stewardship", "Component Library"]
PROFILE_OPTIONS = {
    "Airborne sound insulation (Rw)": "AIRBORNE_SOUND_INSULATION_RW",
    "Frequency spectrum": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Vibration dataset": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Mode shapes": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Other acoustic measurement": "GENERIC_ACOUSTIC_MEASUREMENT",
}


@st.cache_data(show_spinner=False)
def inspect_ifc_bytes(payload: bytes) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as handle:
        handle.write(payload)
        path = Path(handle.name)
    try:
        return [item for item in extract_walls_from_ifc(path) if item.get("extraction_success")]
    finally:
        path.unlink(missing_ok=True)


def _sidebar() -> str:
    with st.sidebar:
        st.markdown("### ◈ FAIR Acoustic")
        st.caption("Research data management · IFC · acoustics · Linked Data")
        st.divider()
        selected = st.radio("Workspace", NAV_ITEMS, label_visibility="collapsed")
        st.divider()
        current = get_package()
        if current:
            st.caption("CURRENT PACKAGE")
            st.markdown(f"**{current.package_id}**")
            st.caption(current.title)
            st.markdown(badge(current.fair_status.value), unsafe_allow_html=True)
            st.markdown(badge(current.lifecycle_display_status), unsafe_allow_html=True)
        else:
            st.caption("No package selected")
        st.divider()
        st.caption(f"{len(packages())} package(s) persisted in the local metadata catalog")
    return selected


def _select_package(label: str, key: str):
    all_packages = packages()
    if not all_packages:
        return None
    current = get_package()
    ids = [item.package_id for item in all_packages]
    index = ids.index(current.package_id) if current and current.package_id in ids else 0
    selected = st.selectbox(label, ids, index=index, key=key, format_func=lambda pid: f"{pid} · {next(item.title for item in all_packages if item.package_id == pid)}")
    set_current(selected)
    return get_package(selected)


def render_overview() -> None:
    hero(
        "FAIR research data for acoustic building components",
        "A package-first research data management platform connecting IFC geometry, laboratory or experimental measurement datasets, semantic metadata and lifecycle stewardship without overwriting the source evidence.",
        "Research platform · package-centric architecture",
    )
    all_packages = packages()
    ready = sum(item.fair_status.value == "FAIR_READY" for item in all_packages)
    review = sum(item.lifecycle_display_status not in {"UNASSESSED", "ACCEPTABLE"} for item in all_packages)
    avg = sum(float(item.fair_assessment.get("score", 0)) for item in all_packages) / len(all_packages) if all_packages else 0
    a, b, c, d = st.columns(4)
    a.metric("Component packages", len(all_packages))
    b.metric("FAIR-ready", ready)
    c.metric("Average FAIR readiness", f"{avg:.0%}")
    d.metric("Lifecycle review", review)

    st.markdown("### Information objects")
    cols = st.columns(3)
    cards = [
        ("01 · Geometry", "IFC", "GlobalId, IFC class, material layers, thickness, semantic classification and spatial context remain geometry-side evidence."),
        ("02 · Measurements", "External datasets", "VaBDat-style XML, spectra, vibration, mode shapes and performance metrics remain independent research datasets."),
        ("03 · Metadata", "RDF / Linked Data", "PROV, authorship, methods, institution, version, uncertainty, quality, rights, identifiers and FAIR status form the catalog layer."),
    ]
    for col, (number, title, copy) in zip(cols, cards):
        col.markdown(f'<div class="surface"><div class="flow-number">{number}</div><div class="flow-title">{title}</div><div class="flow-copy">{copy}</div></div>', unsafe_allow_html=True)

    st.markdown("### Dual assessment model")
    left, right = st.columns(2)
    left.markdown("**FAIR Assessment**")
    left.write("Findability, accessibility, interoperability and reusability are evaluated from package evidence and metadata completeness.")
    right.markdown("**Lifecycle Stewardship**")
    right.write("The preserved MappingSeries / MappingAssertion lifecycle logic evaluates whether the IFC ↔ measurement relationship remains defensible over time.")

    if all_packages:
        st.markdown("### Recent packages")
        st.dataframe([
            {
                "Package": item.package_id,
                "Title": item.title,
                "IFC GlobalId": item.ifc_global_id,
                "Measurement": item.measurement_context.get("measurement_type", ""),
                "FAIR": item.fair_status.value,
                "Lifecycle": item.lifecycle_display_status,
                "Version": item.version,
            }
            for item in all_packages[:8]
        ], use_container_width=True, hide_index=True)
    else:
        empty_state("The component library is empty", "Open FAIR Package Builder to create the first geometry + measurement + metadata research package.")


def _measurement_preview(uploaded) -> None:
    if not uploaded:
        return
    payload = uploaded.getvalue()
    suffix = Path(uploaded.name).suffix.lower()
    st.caption(f"{uploaded.name} · {len(payload):,} bytes · {suffix or 'unknown format'}")
    try:
        if suffix == ".xml":
            root = ET.fromstring(payload)
            st.info(f"XML root element: `{root.tag}` · {len(list(root))} direct child element(s)")
        elif suffix == ".json":
            obj = json.loads(payload)
            keys = list(obj.keys())[:12] if isinstance(obj, dict) else []
            st.info("JSON keys: " + (", ".join(keys) if keys else "array / scalar payload"))
        elif suffix == ".csv":
            frame = pd.read_csv(BytesIO(payload), nrows=8)
            st.dataframe(frame, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.caption(f"Preview unavailable: {exc}")


def render_builder() -> None:
    hero(
        "Build a FAIR Acoustic Package",
        "Package IFC geometry, a measurement dataset and research metadata as one portable object. The source files are retained byte-for-byte; the platform adds metadata, FAIR assessment and stewardship references around them.",
        "Workspace 01 · FAIR Package Builder",
    )
    st.markdown("### 1 · Source resources")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**IFC geometry**")
        ifc_file = st.file_uploader("Upload IFC", type=["ifc"], key="platform_ifc")
        walls = inspect_ifc_bytes(ifc_file.getvalue()) if ifc_file else []
        selected_wall = None
        if walls:
            labels = []
            for wall in walls:
                thickness = wall.get("total_thickness_m")
                thickness_text = f"{thickness:.3f} m" if isinstance(thickness, (int, float)) else "thickness n/a"
                labels.append(f"{wall.get('name')} · {wall.get('ifc_class')} · {wall.get('construction_family')} · {thickness_text}")
            selected_index = st.selectbox("IFC component", range(len(walls)), format_func=lambda index: labels[index])
            selected_wall = walls[selected_index]
            st.caption(f"GlobalId `{selected_wall.get('global_id')}`")
            chips = [selected_wall.get("ifc_class"), selected_wall.get("semantic_classification")] + selected_wall.get("material_evidence", [])
            st.markdown(" ".join(f'<span class="resource-chip">{str(item)}</span>' for item in chips if item), unsafe_allow_html=True)
            if selected_wall.get("spatial_context", {}).get("name"):
                st.caption(f"Spatial context: {selected_wall['spatial_context'].get('structure_type')} · {selected_wall['spatial_context'].get('name')}")
            with st.expander("Geometry evidence"):
                st.json(selected_wall)
        elif ifc_file:
            st.warning("No IfcWall elements were extracted. You can still provide a GlobalId manually and package the IFC file.")
        ifc_global_id = st.text_input("IFC GlobalId", value=(selected_wall or {}).get("global_id", ""), key=f"global_{(selected_wall or {}).get('global_id','manual')}")

    with right:
        st.markdown("**Measurement dataset**")
        measurement_file = st.file_uploader("Upload measurement", type=["xml", "csv", "json", "txt", "dat", "h5", "hdf5", "vtk", "ttl", "rdf"], key="platform_measurement")
        _measurement_preview(measurement_file)
        measurement_identifier = st.text_input("Measurement identifier", placeholder="VaBDat-310 / LAB-RW-2026-014 / VIB-042")
        dataset_uri = st.text_input("Dataset URI / landing page", placeholder="https://repository.example.org/dataset/...")
        measurement_label = st.selectbox("Measurement type", list(PROFILE_OPTIONS))
        stewardship_profile = PROFILE_OPTIONS[measurement_label]

    st.markdown("### 2 · Measurement context")
    c1, c2, c3 = st.columns(3)
    with c1:
        method = st.text_input("Measurement method", placeholder="ISO 10140, modal test, accelerometer campaign...")
        instrument = st.text_input("Instrument / system", placeholder="Analyzer, microphone, accelerometer...")
        assembly = st.text_input("Specimen / assembly")
    with c2:
        family = st.text_input("Measured construction family", value=(selected_wall or {}).get("construction_family", ""))
        base_thickness = (selected_wall or {}).get("total_thickness_m") or 0.0
        measured_thickness = st.number_input("Measured assembly thickness (m)", min_value=0.0, value=float(base_thickness), step=0.005)
        report_reference = st.text_input("Report / experiment reference")
    with c3:
        rw_db = None
        unit = "dB"
        spectrum_c = None
        spectrum_ctr = None
        if stewardship_profile == "AIRBORNE_SOUND_INSULATION_RW":
            rw_db = st.number_input("Rw (dB)", min_value=0.0, max_value=100.0, value=50.0, step=0.5)
            unit = st.text_input("Unit", value="dB")
            spectrum_c = st.number_input("C", value=0.0, step=0.5)
            spectrum_ctr = st.number_input("Ctr", value=0.0, step=0.5)
        else:
            st.info("Generic lifecycle stewardship validates identity, availability, family, thickness, versions and provenance without forcing an Rw-specific data model.")

    st.markdown("### 3 · Descriptive metadata, provenance and reuse")
    m1, m2, m3 = st.columns(3)
    with m1:
        title = st.text_input("Package title", placeholder="Masonry wall airborne sound insulation dataset")
        description = st.text_area("Description", height=110)
        keywords = st.text_input("Keywords", placeholder="masonry, airborne sound insulation, laboratory")
    with m2:
        creator = st.text_input("Creator / author")
        institution = st.text_input("Institution")
        version = st.text_input("Package version", value="1.0.0")
        identifier = st.text_input("Package persistent identifier", placeholder="Leave blank to mint a prototype URI")
    with m3:
        license_uri = st.text_input("Reuse license / rights URI", value="https://creativecommons.org/licenses/by/4.0/")
        uncertainty = st.text_input("Measurement uncertainty", placeholder="±1.2 dB / confidence interval / sensor accuracy")
        calibration = st.text_input("Calibration / QA reference")
        quality = st.text_area("Quality statement", height=76)

    ready = bool(ifc_file and measurement_file)
    if st.button("Generate FAIR Acoustic Package", type="primary", use_container_width=True, disabled=not ready):
        geometry = selected_wall or {}
        package = FairPackageBuilder().build(
            ifc_file.getvalue(), ifc_file.name,
            measurement_file.getvalue(), measurement_file.name,
            ifc_global_id=ifc_global_id,
            creator=creator,
            version=version,
            identifier=identifier or None,
            dataset_uri=dataset_uri,
            license_uri=license_uri,
            provenance={"creator": creator, "institution": institution, "note": f"Package created from {ifc_file.name} and {measurement_file.name}"},
            measurement_context={
                "measurement_type": measurement_label,
                "stewardship_profile": stewardship_profile,
                "measurement_method": method,
                "instrument": instrument,
                "assembly": assembly,
                "construction_family": family,
                "total_thickness_m": measured_thickness,
                "report_reference": report_reference,
                "rw_db": rw_db,
                "unit": unit,
                "spectrum_adaptation_C": spectrum_c,
                "spectrum_adaptation_Ctr": spectrum_ctr,
            },
            quality_information={"uncertainty": uncertainty, "calibration_reference": calibration, "quality_statement": quality},
            metadata={
                "title": title or measurement_identifier or "Untitled acoustic component package",
                "description": description,
                "keywords": [item.strip() for item in keywords.split(",") if item.strip()],
                "measurement_identifier": measurement_identifier,
                "geometry_name": geometry.get("name", ""),
                "geometry_ifc_class": geometry.get("ifc_class", "IfcWall"),
                "geometry_semantic_classification": geometry.get("semantic_classification", ""),
                "geometry_construction_family": geometry.get("construction_family", ""),
                "geometry_total_thickness_m": geometry.get("total_thickness_m"),
                "geometry_materials": geometry.get("material_evidence", []),
                "geometry_material_layers": geometry.get("material_layers", []),
                "geometry_spatial_context": geometry.get("spatial_context", {}),
                "model_version": geometry.get("model_version", Path(ifc_file.name).stem),
                "source_ifc_sha256": geometry.get("source_sha256", ""),
            },
        )
        add_package(package)
        st.success(f"Created {package.package_id} — FAIR status: {package.fair_status.value}")
        st.download_button("Download package.zip", export_fair_package(package), file_name=f"{package.package_id}.zip", mime="application/zip", type="primary", use_container_width=True)
        with st.expander("Generated manifest"):
            st.json(json.loads(package.assets["manifest.json"]))
    elif not ready:
        st.caption("Both an IFC source and a measurement dataset are required for package generation. Metadata may remain incomplete; FAIR Assessment will report the deficiencies explicitly.")


def render_fair_assessment() -> None:
    hero("FAIR Assessment", "Inspect FAIR readiness as explicit research-data-management evidence. Each failed criterion includes the evidence used and a remediation action rather than hiding the result behind one score.", "Workspace 02 · FAIR Assessment")
    package = _select_package("Package", "fair_assessment_package")
    if not package:
        empty_state("Nothing to assess", "Create a package in FAIR Package Builder first.")
        return
    result = assess_fair(package)
    render_fair_cards(result)

    st.markdown("### Overall state")
    left, mid, right = st.columns([1.2, 1, 1])
    left.metric("FAIR status", result.fair_status.value)
    mid.metric("Composite readiness", f"{result.score:.0%}")
    right.metric("Lifecycle status", package.lifecycle_display_status)
    st.progress(result.score)

    missing = []
    rows = []
    for dimension in result.dimensions:
        for criterion in dimension.criteria:
            rows.append({"Dimension": dimension.name, "Criterion": criterion.label, "Status": "PASS" if criterion.passed else "FAIL", "Evidence": criterion.evidence})
            if not criterion.passed:
                missing.append({"Dimension": dimension.name, "Missing criterion": criterion.label, "Recommended action": criterion.remediation})
    st.markdown("### Criterion evidence")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if missing:
        st.markdown("### Remediation queue")
        st.dataframe(missing, use_container_width=True, hide_index=True)
    else:
        st.success("All configured FAIR criteria pass.")

    st.markdown("### Package resources")
    manifest = json.loads(package.assets.get("manifest.json", b"{}").decode("utf-8"))
    st.dataframe([
        {"Resource": name, **details}
        for name, details in manifest.get("resources", {}).items()
    ], use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    if c1.button("Rebuild metadata and re-assess", use_container_width=True):
        finalize_package(package)
        update_package(package)
        st.success("Metadata, checksums, manifest and FAIR result regenerated.")
    c2.download_button("Export assessed package", export_fair_package(package), f"{package.package_id}.zip", "application/zip", use_container_width=True)


def render_stewardship() -> None:
    hero("Lifecycle Stewardship", "The original lifecycle logic is retained as the stewardship layer. It monitors technical resolution, semantic compatibility, version changes, retargeting, review states and MappingAssertion revision history independently of FAIR readiness.", "Workspace 03 · Lifecycle Stewardship")
    package = _select_package("Package", "stewardship_package")
    if not package:
        empty_state("No package available", "Build a FAIR package before running lifecycle stewardship.")
        return

    top = st.columns(4)
    top[0].metric("FAIR", package.fair_status.value)
    top[1].metric("Lifecycle", package.lifecycle_display_status)
    top[2].metric("Revisions", len(package.stewardship_history))
    top[3].metric("Profile", "Rw legacy engine" if package.measurement_context.get("stewardship_profile") == "AIRBORNE_SOUND_INSULATION_RW" else "Generic package link")

    st.markdown("### Evidence relationship")
    a, b = st.columns(2)
    with a:
        st.markdown("**IFC geometry**")
        st.json({
            "GlobalId": package.ifc_global_id,
            "IFC class": package.metadata.get("geometry_ifc_class"),
            "family": package.metadata.get("geometry_construction_family"),
            "thickness_m": package.metadata.get("geometry_total_thickness_m"),
            "materials": package.metadata.get("geometry_materials"),
            "model_version": package.metadata.get("model_version"),
        })
    with b:
        st.markdown("**Measurement dataset**")
        st.json({
            "identifier": package.metadata.get("measurement_identifier"),
            "dataset_uri": package.dataset_uri,
            "type": package.measurement_context.get("measurement_type"),
            "family": package.measurement_context.get("construction_family"),
            "thickness_m": package.measurement_context.get("total_thickness_m"),
            "method": package.measurement_context.get("measurement_method"),
        })

    if st.button("Run lifecycle stewardship assessment", type="primary", use_container_width=True):
        try:
            outcome = FairStewardshipService().assess(package)
            update_package(package)
            if outcome.created_revision:
                st.success(f"Created a new stewardship revision: {outcome.status}")
            else:
                st.info(f"No evidence change detected; no new immutable revision created. Current state: {outcome.status}")
        except Exception as exc:
            st.error(f"Lifecycle stewardship failed: {exc}")

    if package.mapping_series_uri:
        st.markdown("### Current stewardship identity")
        st.code(package.mapping_series_uri, language=None)
        st.caption(f"Latest MappingAssertion: {package.latest_mapping_assertion_uri or 'none'}")

    if package.stewardship_history:
        st.markdown("### Revision history")
        st.dataframe([
            {
                "Revision": item.get("revision"),
                "Time": item.get("timestamp"),
                "Status": item.get("status"),
                "Engine status": item.get("engine_status"),
                "Mode": item.get("mode"),
                "MappingSeries": item.get("mapping_series_uri"),
                "MappingAssertion": item.get("assertion_uri"),
            }
            for item in package.stewardship_history
        ], use_container_width=True, hide_index=True)
        latest = package.stewardship_history[-1]
        with st.expander("Latest decision details", expanded=True):
            result = latest.get("result", {})
            if result.get("discrepancies"):
                st.dataframe(result["discrepancies"], use_container_width=True, hide_index=True)
            elif result.get("tier_1_link"):
                for section in ("tier_1_link", "tier_2_mapping", "tier_3_lifecycle"):
                    st.markdown(f"**{section.replace('_', ' ').title()}**")
                    st.dataframe(result.get(section, []), use_container_width=True, hide_index=True)
            else:
                st.json(result)
        with st.expander("Stewardship RDF / PROV"):
            st.code(package.metadata.get("stewardship_rdf_turtle", "No stewardship RDF yet."), language="turtle")
    else:
        empty_state("No stewardship revision yet", "Run the assessment to create the first MappingSeries / MappingAssertion evidence revision.")


def render_library() -> None:
    hero("Acoustic Component Library", "Search persisted FAIR Acoustic Packages by geometry identity, measurement context, author, FAIR state or lifecycle state. The library is backed by RDF metadata and supports direct SPARQL inspection.", "Workspace 04 · Metadata Catalog & Reuse")
    all_packages = packages()
    if not all_packages:
        empty_state("Library empty", "Create packages first; they are persisted under the local package repository and reloaded across Streamlit reruns.")
        return
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    query = f1.text_input("Search", placeholder="GlobalId, package title, author, method, material...")
    fair_values = ["ALL"] + sorted({item.fair_status.value for item in all_packages})
    life_values = ["ALL"] + sorted({item.lifecycle_display_status for item in all_packages})
    type_values = ["ALL"] + sorted({str(item.measurement_context.get("measurement_type")) for item in all_packages if item.measurement_context.get("measurement_type")})
    fair_filter = f2.selectbox("FAIR", fair_values)
    lifecycle_filter = f3.selectbox("Lifecycle", life_values)
    type_filter = f4.selectbox("Measurement", type_values)
    catalog = MetadataCatalog(all_packages)
    results = catalog.search(query, fair_filter, lifecycle_filter, type_filter)

    st.caption(f"{len(results)} package(s) in the current catalog view · {len(catalog.graph):,} RDF triples")
    for package in results:
        with st.container(border=True):
            row = st.columns([2.4, 1, 1, 1])
            row[0].markdown(f"### {package.title}\n`{package.package_id}`")
            row[1].markdown("**FAIR**")
            row[1].markdown(badge(package.fair_status.value), unsafe_allow_html=True)
            row[2].markdown("**Lifecycle**")
            row[2].markdown(badge(package.lifecycle_display_status), unsafe_allow_html=True)
            row[3].metric("Version", package.version)
            st.caption(f"IFC GlobalId: {package.ifc_global_id or 'missing'} · Measurement: {package.metadata.get('measurement_identifier') or 'unnamed'} · Creator: {package.creator or 'unknown'}")
            actions = st.columns([1, 1, 1, 3])
            if actions[0].button("Select", key=f"select_{package.package_id}"):
                set_current(package.package_id)
                st.success("Package selected for assessment and stewardship.")
            actions[1].download_button("Export ZIP", export_fair_package(package), f"{package.package_id}.zip", "application/zip", key=f"export_{package.package_id}")
            with actions[2].popover("Inspect"):
                st.json(package.to_dict())
                st.code(metadata_turtle(package), language="turtle")
            if actions[3].button("Delete local package", key=f"delete_{package.package_id}"):
                delete_package(package.package_id)
                st.rerun()

    st.markdown("### SPARQL workbench")
    default_query = """PREFIX fairac: <https://example.org/fair-acoustic/vocab/>\nPREFIX dct: <http://purl.org/dc/terms/>\nSELECT ?package ?title ?fairStatus ?lifecycleStatus WHERE {\n  ?package a fairac:FairAcousticPackage ;\n           dct:title ?title ;\n           fairac:fairStatus ?fairStatus ;\n           fairac:lifecycleStatus ?lifecycleStatus .\n}\nORDER BY ?title"""
    sparql = st.text_area("Catalog query", value=default_query, height=190)
    if st.button("Run SPARQL", use_container_width=True):
        try:
            rows = catalog.sparql(sparql)
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} row(s)")
        except Exception as exc:
            st.error(f"SPARQL query failed: {exc}")


def run_platform_app() -> None:
    st.set_page_config(page_title="FAIR Acoustic Component Platform", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
    inject_platform_css()
    ensure_state()
    selected = _sidebar()
    if selected == "Overview":
        render_overview()
    elif selected == "FAIR Package Builder":
        render_builder()
    elif selected == "FAIR Assessment":
        render_fair_assessment()
    elif selected == "Lifecycle Stewardship":
        render_stewardship()
    else:
        render_library()
