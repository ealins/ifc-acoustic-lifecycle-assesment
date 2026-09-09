from __future__ import annotations

import json

import streamlit as st

from dashboard.backend.fair_bridge import get_package, packages
from dashboard.ui.fair_dashboard import badge, empty_state, hero, inject_platform_css
from dashboard.ui.platform_app import (
    render_builder,
    render_fair_assessment,
    render_library,
    render_overview,
    render_stewardship,
)
from fair_platform.catalog import MetadataCatalog
from fair_platform.export import export_fair_package
from fair_platform.metadata import metadata_turtle
from fair_platform.shacl import validate_package_shacl

NAV_ITEMS = [
    "Overview",
    "FAIR Package Builder",
    "FAIR Assessment",
    "Lifecycle Stewardship",
    "Component Library",
    "Platform Evidence",
]

CAPABILITIES = [
    {
        "#": 1,
        "Capability": "FAIR domain layer",
        "Implementation": "FairAcousticPackage + criterion/dimension result models + dual FAIR/lifecycle state",
        "Evidence": "fair_platform/models.py",
        "Visible in UI": "Overview, FAIR Assessment, Platform Evidence",
        "Status": "ACTIVE",
    },
    {
        "#": 2,
        "Capability": "FAIR assessment engine",
        "Implementation": "Criterion-level F/A/I/R checks with evidence and remediation",
        "Evidence": "fair_platform/assessment.py",
        "Visible in UI": "FAIR Assessment → Criterion evidence / Remediation queue",
        "Status": "ACTIVE",
    },
    {
        "#": 3,
        "Capability": "Package management",
        "Implementation": "Filesystem PackageRepository, checksums, RDF, manifest and ZIP export",
        "Evidence": "fair_platform/repository.py · export.py · manifest.py",
        "Visible in UI": "Builder, FAIR Assessment, Component Library, Platform Evidence",
        "Status": "ACTIVE",
    },
    {
        "#": 4,
        "Capability": "Metadata Catalog",
        "Implementation": "RDFLib graph + DCAT/DCTERMS/PROV + SPARQL + executable SHACL",
        "Evidence": "fair_platform/catalog.py · metadata.py · shacl.py · metadata/fair_shapes.ttl",
        "Visible in UI": "Component Library + Platform Evidence",
        "Status": "ACTIVE",
    },
    {
        "#": 5,
        "Capability": "Lifecycle Stewardship",
        "Implementation": "Rw adapter to existing engine.evaluate_lifecycle(); generic datasets use TieredValidator",
        "Evidence": "fair_platform/stewardship.py",
        "Visible in UI": "Lifecycle Stewardship → identity, revisions, decision details, PROV",
        "Status": "ACTIVE",
    },
    {
        "#": 6,
        "Capability": "IFC geometry evidence",
        "Implementation": "GlobalId, IFC class, material layers, thickness, classification, spatial context, source hash",
        "Evidence": "dashboard/backend/ifc_parser.py",
        "Visible in UI": "Builder → Geometry evidence; Lifecycle Stewardship",
        "Status": "ACTIVE",
    },
    {
        "#": 7,
        "Capability": "Measurement datasets",
        "Implementation": "XML/CSV/JSON/HDF5/VTK/text structural inspection + preserved source bytes",
        "Evidence": "fair_platform/measurement.py",
        "Visible in UI": "Platform Evidence → Measurement inspection",
        "Status": "ACTIVE",
    },
    {
        "#": 8,
        "Capability": "Canonical UI",
        "Implementation": "Overview, Builder, FAIR Assessment, Stewardship, Library, Platform Evidence",
        "Evidence": "dashboard/ui/enhanced_app.py · platform_app.py",
        "Visible in UI": "Sidebar navigation",
        "Status": "ACTIVE",
    },
    {
        "#": 9,
        "Capability": "Research documentation",
        "Implementation": "Thesis README + architecture/migration document + implementation evidence record",
        "Evidence": "README.md · docs/FAIR_PIVOT_ARCHITECTURE.md · IMPLEMENTATION_EVIDENCE.md",
        "Visible in UI": "Platform Evidence → Architecture and boundaries",
        "Status": "ACTIVE",
    },
    {
        "#": 10,
        "Capability": "Lifecycle preservation",
        "Implementation": "FAIR adapters wrap existing lifecycle core; core engine files remain authoritative",
        "Evidence": "engine.py · association_lifecycle.py · lifecycle_engine/*",
        "Visible in UI": "Lifecycle Stewardship → Engine profile and revision output",
        "Status": "PRESERVED",
    },
    {
        "#": 11,
        "Capability": "Tests / CI",
        "Implementation": "FAIR, package I/O, stewardship, measurement and SHACL regression tests",
        "Evidence": "tests/* · .github/workflows/test.yml",
        "Visible in UI": "Platform Evidence → Verification scope",
        "Status": "ACTIVE",
    },
]


def _sidebar() -> str:
    with st.sidebar:
        st.markdown("### ◈ FAIR Acoustic")
        st.caption("Research data management · IFC · acoustics · Linked Data")
        st.divider()
        selected = st.radio("Workspace", NAV_ITEMS, label_visibility="collapsed", key="enhanced_workspace")
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
        st.caption(f"{len(packages())} persisted package(s)")
        st.caption("Platform Evidence exposes what is implemented, what is validated, and what remains prototype infrastructure.")
    return selected


def _capability_table(compact: bool = False) -> None:
    rows = CAPABILITIES if not compact else [
        {"Capability": item["Capability"], "Status": item["Status"], "Visible in UI": item["Visible in UI"]}
        for item in CAPABILITIES
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_enhanced_overview() -> None:
    render_overview()
    st.markdown("### Implementation evidence at a glance")
    st.caption("These are implementation locations and UI surfaces, not marketing claims. Open **Platform Evidence** for live package-level proof and explicit prototype boundaries.")
    _capability_table(compact=True)


def render_enhanced_assessment() -> None:
    render_fair_assessment()
    package = get_package()
    if not package:
        return
    st.markdown("### RDF metadata profile validation (SHACL)")
    report = package.metadata.get("shacl_validation") or validate_package_shacl(package)
    a, b, c = st.columns(3)
    a.metric("SHACL engine", "Available" if report.get("available") else "Unavailable")
    b.metric("Conformance", "PASS" if report.get("conforms") else "FAIL")
    c.metric("Violations", int(report.get("violation_count", 0)))
    if report.get("results"):
        st.dataframe(report["results"], use_container_width=True, hide_index=True)
    else:
        st.success("Generated package metadata conforms to the configured SHACL profile.") if report.get("conforms") else st.info(report.get("report_text", "No SHACL report available."))


def render_enhanced_library() -> None:
    render_library()
    all_packages = packages()
    if not all_packages:
        return
    catalog = MetadataCatalog(all_packages)
    st.markdown("### Metadata Catalog export")
    col1, col2 = st.columns(2)
    col1.metric("Catalog RDF triples", len(catalog.graph))
    col2.download_button(
        "Download catalog.ttl",
        data=catalog.graph.serialize(format="turtle"),
        file_name="fair-acoustic-catalog.ttl",
        mime="text/turtle",
        use_container_width=True,
    )


def render_platform_evidence() -> None:
    hero(
        "Platform Evidence",
        "A researcher-facing audit view of what the repository actually implements. It distinguishes source files, executable validation, persisted package evidence and prototype limitations so capabilities can be verified rather than inferred from the README.",
        "Workspace 05 · Implementation audit",
    )

    st.markdown("### 11 requested capabilities — implementation map")
    _capability_table(compact=False)

    st.markdown("### Architectural boundary")
    st.code(
        "IFC Geometry + Measurement Dataset + Metadata\n"
        "                    ↓\n"
        "            FairAcousticPackage\n"
        "          ↙                   ↘\n"
        "  FAIR Assessment       Lifecycle Stewardship\n"
        "  F / A / I / R         MappingSeries / Assertion\n"
        "          ↘                   ↙\n"
        "       Metadata Catalog + portable ZIP",
        language=None,
    )

    st.markdown("### What is deliberately not overstated")
    st.warning(
        "Persistence is currently a local filesystem research repository (`packages/<package-id>/`), not a multi-user database or institutional repository. "
        "Prototype package URIs are identifiers, but they are not real DOI/Handle registrations unless you supply a repository-issued PID. "
        "HDF5/VTK inspection exposes structure and detected signal names; it does not claim domain-complete interpretation of every laboratory schema."
    )

    all_packages = packages()
    catalog = MetadataCatalog(all_packages)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Persisted packages", len(all_packages))
    m2.metric("Catalog triples", len(catalog.graph))
    m3.metric("FAIR-ready", sum(item.fair_status.value == "FAIR_READY" for item in all_packages))
    m4.metric("Stewardship revisions", sum(len(item.stewardship_history) for item in all_packages))

    if not all_packages:
        empty_state(
            "No package-level evidence exists yet",
            "The implementation map above is visible immediately. Create a package in FAIR Package Builder to populate live resource integrity, SHACL, FAIR, measurement and stewardship evidence below.",
        )
        return

    current = get_package() or all_packages[0]
    st.markdown(f"### Live package evidence · {current.package_id}")

    manifest = json.loads(current.assets.get("manifest.json", b"{}").decode("utf-8"))
    resources = []
    for name, details in manifest.get("resources", {}).items():
        resources.append({
            "Resource": name,
            "Path": details.get("path"),
            "Source filename": details.get("source_filename"),
            "Bytes": details.get("size_bytes"),
            "Checksum": details.get("checksum"),
        })
    st.markdown("#### Package resource integrity")
    st.dataframe(resources, use_container_width=True, hide_index=True)

    st.markdown("#### Measurement inspection")
    inspection = current.metadata.get("measurement_inspection") or {}
    i1, i2, i3 = st.columns(3)
    i1.metric("Format", str(inspection.get("format", "unknown")).upper())
    i2.metric("Inspection", "VALID" if inspection.get("valid") else "FAILED")
    i3.metric("Detected signals", len(inspection.get("semantic_signals", []) or []))
    st.write(inspection.get("summary", "No measurement inspection evidence stored."))
    if inspection.get("semantic_signals"):
        st.caption("Detected structural signals: " + ", ".join(inspection["semantic_signals"]))
    with st.expander("Measurement structural details", expanded=True):
        st.json(inspection)

    st.markdown("#### FAIR criterion evidence")
    rows = []
    assessment = current.fair_assessment or {}
    for key in ("findable", "accessible", "interoperable", "reusable"):
        dimension = assessment.get(key, {})
        for criterion in dimension.get("criteria", []):
            rows.append({
                "Dimension": dimension.get("name", key.title()),
                "Criterion": criterion.get("label"),
                "Pass": criterion.get("passed"),
                "Evidence": criterion.get("evidence"),
                "Remediation": criterion.get("remediation"),
            })
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### SHACL execution evidence")
    shacl = current.metadata.get("shacl_validation") or validate_package_shacl(current)
    s1, s2, s3 = st.columns(3)
    s1.metric("Engine available", "YES" if shacl.get("available") else "NO")
    s2.metric("Conforms", "YES" if shacl.get("conforms") else "NO")
    s3.metric("Violations", int(shacl.get("violation_count", 0)))
    if shacl.get("results"):
        st.dataframe(shacl["results"], use_container_width=True, hide_index=True)
    with st.expander("SHACL report text"):
        st.code(shacl.get("report_text", ""), language=None)

    st.markdown("#### Lifecycle stewardship evidence")
    l1, l2, l3 = st.columns(3)
    l1.metric("Lifecycle state", current.lifecycle_display_status)
    l2.metric("MappingSeries", "MINTED" if current.mapping_series_uri else "NOT YET")
    l3.metric("Immutable revisions", len(current.stewardship_history))
    if current.stewardship_history:
        st.dataframe([
            {
                "Revision": item.get("revision"),
                "Mode": item.get("mode"),
                "Status": item.get("status"),
                "MappingSeries": item.get("mapping_series_uri"),
                "MappingAssertion": item.get("assertion_uri"),
            }
            for item in current.stewardship_history
        ], use_container_width=True, hide_index=True)

    st.markdown("#### Exported research object")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Download package.zip",
        export_fair_package(current),
        f"{current.package_id}.zip",
        "application/zip",
        use_container_width=True,
    )
    d2.download_button(
        "Download metadata.ttl",
        metadata_turtle(current),
        f"{current.package_id}-metadata.ttl",
        "text/turtle",
        use_container_width=True,
    )
    d3.download_button(
        "Download catalog.ttl",
        catalog.graph.serialize(format="turtle"),
        "fair-acoustic-catalog.ttl",
        "text/turtle",
        use_container_width=True,
    )

    with st.expander("manifest.json", expanded=False):
        st.json(manifest)

    st.markdown("### Verification scope")
    st.info(
        "CI compiles the FAIR and dashboard modules and runs regression tests for FAIR assessment, package I/O, lifecycle stewardship, dataset inspection and SHACL validation. "
        "This verifies the prototype software contract; it does not certify institutional repository availability or scientific validity of uploaded measurements."
    )


def run_enhanced_app() -> None:
    st.set_page_config(
        page_title="FAIR Acoustic Component Platform",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_platform_css()
    from dashboard.backend.fair_bridge import ensure_state
    ensure_state()
    selected = _sidebar()
    if selected == "Overview":
        render_enhanced_overview()
    elif selected == "FAIR Package Builder":
        render_builder()
    elif selected == "FAIR Assessment":
        render_enhanced_assessment()
    elif selected == "Lifecycle Stewardship":
        render_stewardship()
    elif selected == "Component Library":
        render_enhanced_library()
    else:
        render_platform_evidence()
