"""Thesis-facing workspace for IFC-linked vibrometry data packages.

The app presents the proposed research-data-management workflow without
claiming that it modifies IFC or stores dense vibration arrays inside IFC.
Existing research-object package functions remain available through the
package builder.
"""

from __future__ import annotations

import streamlit as st

from dashboard.backend.fair_bridge import ensure_state, packages
from dashboard.ui.fair_dashboard import hero, inject_platform_css
from dashboard.ui.research_builder import render_research_builder
from fair_platform.export import export_research_object


NAV_ITEMS = (
    "Thesis Overview",
    "Package Builder",
    "Data Architecture",
    "IFC Linkage",
    "Validation & Traceability",
    "FAIR Evidence",
    "Package Library",
    "Method & Scope",
)


def _inject_thesis_css() -> None:
    """Apply a focused dark research-workspace treatment."""
    inject_platform_css()
    st.markdown(
        """
        <style>
        :root {
          --ink: #E8F0FA;
          --muted: #A7B6C9;
          --line: #2A3A50;
          --accent: #62D6C8;
          --soft: #132235;
        }
        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at 82% -10%, rgba(75, 155, 200, .25), transparent 30%),
            radial-gradient(circle at 10% 15%, rgba(65, 203, 179, .12), transparent 28%),
            #08131F;
        }
        [data-testid="stHeader"] { background: rgba(8, 19, 31, .86); }
        .block-container { max-width: 1390px; padding-top: 1.3rem; }
        [data-testid="stSidebar"] { background: #0A1725; border-right: 1px solid #203249; }
        [data-testid="stSidebar"] * { color: #D9E5F3; }
        .platform-hero {
          color: #E8F0FA !important;
          border: 1px solid #31506A !important;
          background:
            linear-gradient(118deg, rgba(15, 41, 61, .98), rgba(17, 56, 74, .92) 60%, rgba(31, 87, 99, .83)) !important;
          box-shadow: 0 20px 50px rgba(0, 0, 0, .24) !important;
        }
        .platform-hero h1, .platform-hero p { color: #E8F0FA !important; }
        .platform-hero .kicker { color: #80E4D6 !important; }
        .thesis-strip {
          display: flex; flex-wrap: wrap; gap: .6rem; align-items: center;
          margin: -.15rem 0 1.35rem;
        }
        .thesis-tag {
          color: #BAF5ED; background: rgba(98, 214, 200, .11); border: 1px solid rgba(98, 214, 200, .32);
          padding: .35rem .7rem; border-radius: 999px; font-size: .78rem; font-weight: 700;
        }
        .research-note, .architecture-card, .scope-card, .validation-card {
          border: 1px solid #29445C; background: rgba(13, 33, 51, .82); border-radius: 16px;
          padding: 1.05rem 1.15rem; min-height: 100%;
        }
        .research-note { border-left: 4px solid #62D6C8; }
        .research-note h3, .architecture-card h3, .scope-card h3, .validation-card h3 { color: #E8F0FA; margin: 0 0 .45rem; }
        .research-note p, .architecture-card p, .scope-card p, .validation-card p, .architecture-card li, .scope-card li, .validation-card li { color: #B7C7D9; }
        .architecture-step { color: #7CEADD; font-size: .74rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }
        .flow-line { color: #77DCD1; text-align: center; padding: .75rem 0 0; font-size: 1.4rem; }
        .metric-caption { color: #9EB2C8; font-size: .82rem; margin-top: -.4rem; }
        [data-testid="stMetric"] { background: rgba(15, 39, 59, .76); border: 1px solid #29445C; border-radius: 14px; padding: .85rem 1rem; }
        [data-testid="stMetricLabel"] p, [data-testid="stMetricValue"] { color: #E8F0FA !important; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .35rem; }
        [data-testid="stTabs"] button { color: #AFC0D1; border-radius: 9px 9px 0 0; }
        [data-testid="stTabs"] button[aria-selected="true"] { color: #7CEADD; background: #102A3D; }
        .stButton button, .stDownloadButton button { border-radius: 10px; border-color: #3F8F91; }
        .stButton button[kind="primary"] { background: #267C79; color: white; }
        code { color: #9CF0E4 !important; background: #10283B !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar() -> str:
    with st.sidebar:
        st.markdown("## VIBRO•IFC")
        st.caption("Thesis RDM demonstrator")
        st.caption("Hierarchical data · semantic metadata · OpenBIM context")
        st.divider()
        selected = st.radio("Workspace", NAV_ITEMS, label_visibility="collapsed", key="thesis_workspace")
        st.divider()
        st.markdown("**Design premise**")
        st.caption("The original TXT/CSV measurement payload is retained. IFC stores component context and a document pointer—not scan values.")
        st.divider()
        st.markdown("**Open inspection**")
        st.caption("Text/CSV viewer · Bonsai / BlenderBIM · Browser · Python verification")
    return selected


def _page_intro(title: str, description: str, section: str) -> None:
    hero(title, description, section)
    st.markdown(
        """
        <div class="thesis-strip">
          <span class="thesis-tag">SLDV / vibrometry</span>
          <span class="thesis-tag">TXT / CSV measurement payload</span>
          <span class="thesis-tag">JSON-LD semantics</span>
          <span class="thesis-tag">IFC component context</span>
          <span class="thesis-tag">FAIR-oriented packaging</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _html_card(class_name: str, title: str, body: str) -> None:
    st.markdown(
        f'<div class="{class_name}"><h3>{title}</h3>{body}</div>',
        unsafe_allow_html=True,
    )


def _package_metrics() -> None:
    objects = packages()
    measurement_types = {
        str(item.measurement_context.get("measurement_type", ""))
        for item in objects
        if item.measurement_context.get("measurement_type")
    }
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Packages in workspace", len(objects))
    c2.metric("IFC-linked components", sum(bool(item.ifc_global_id) for item in objects))
    c3.metric("Data profiles represented", len(measurement_types))
    c4.metric("Ready for prototype reuse", sum(item.fair_support_status == "READY_FOR_PROTOTYPE_REUSE" for item in objects))


def render_overview() -> None:
    _page_intro(
        "Vibrometry data, made reusable with its building context.",
        "A thesis demonstrator for packaging scanning laser Doppler vibrometry results as inspectable, traceable research data linked to an IFC building component.",
        "Research data management workflow",
    )
    _package_metrics()
    st.markdown("### The research problem")
    left, right = st.columns([1.35, 1])
    with left:
        _html_card(
            "research-note",
            "From isolated exports to a reusable evidence package",
            "<p>Building-acoustic experiments can produce thousands of scan-point spectra, frequency-response arrays, operational deflection shapes, coherence values, and derived results. A spreadsheet or vendor project alone does not explain which physical component was tested, what each array means, or how a result was produced.</p>",
        )
    with right:
        _html_card(
            "research-note",
            "Thesis contribution",
            "<p>The workflow joins an unchanged TXT/CSV measurement payload, laboratory context, semantic JSON-LD metadata, a precise IFC component reference, validation evidence, and a portable package envelope—without changing the IFC schema or creating a custom viewer.</p>",
        )

    st.markdown("### Three-layer package architecture")
    numerical, semantic, package = st.columns(3)
    with numerical:
        _html_card(
            "architecture-card",
            "01 · Measurement payload",
            "<div class='architecture-step'>TXT / CSV source</div><p>The original exported measurement file remains authoritative. The package records its hash, parser context, columns and any declared point-specific evidence without converting it to another numerical container.</p><p><code>measurements/scan.csv</code><br><code>measurements/scan.txt</code></p>",
        )
    with semantic:
        _html_card(
            "architecture-card",
            "02 · Meaning & links",
            "<div class='architecture-step'>JSON-LD metadata</div><p>Laboratory method, units, processing lineage, limitations and IFC component identity are recorded as an executable application-profile record.</p><p><code>measurementPayload</code><br><code>labContext</code><br><code>ifcLinkRecord</code></p>",
        )
    with package:
        _html_card(
            "architecture-card",
            "03 · Portable package",
            "<div class='architecture-step'>Research-object envelope</div><p>The source measurement payload, IFC model, JSON-LD sidecar, manifest, validation report, README and licence form one documented package. RO-Crate-style metadata supports portable inspection.</p><p><code>measurements/</code> <code>metadata/</code><br><code>geometry/</code> <code>reports/</code></p>",
        )

    st.markdown("### Demonstrator flow")
    flow_cols = st.columns([1, .14, 1, .14, 1, .14, 1])
    flow_cols[0].markdown("**Raw export**<br><span class='metric-caption'>SLDV TXT · CSV</span>", unsafe_allow_html=True)
    flow_cols[1].markdown("<div class='flow-line'>→</div>", unsafe_allow_html=True)
    flow_cols[2].markdown("**Describe**<br><span class='metric-caption'>Python · lab context · JSON-LD sidecar</span>", unsafe_allow_html=True)
    flow_cols[3].markdown("<div class='flow-line'>→</div>", unsafe_allow_html=True)
    flow_cols[4].markdown("**Associate**<br><span class='metric-caption'>IFC GlobalId · checksum · document reference</span>", unsafe_allow_html=True)
    flow_cols[5].markdown("<div class='flow-line'>→</div>", unsafe_allow_html=True)
    flow_cols[6].markdown("**Verify**<br><span class='metric-caption'>Values · paths · semantics · component resolution</span>", unsafe_allow_html=True)

    st.info(
        "Scope boundary: this demonstrator records a component-level association and a declared scan coordinate system. It does not claim 3D registration, mesh projection, simulation solving, or a new IFC schema."
    )


def render_data_architecture() -> None:
    _page_intro(
        "Three authoritative inputs",
        "The workflow preserves the original measurement payload and automatically connects it to laboratory and IFC context.",
        "Layer 01 · source evidence",
    )
    st.markdown("### Proposed hierarchy")
    st.code(
        """measurements/scan.csv or scan.txt   # original measurement payload
metadata/vibrometry-sidecar.jsonld  # laboratory + IFC + payload metadata
geometry/source-model.ifc           # authoritative IFC context
reports/vibrometry-cross-layer-validation.json""",
        language="text",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        _html_card("architecture-card", "Storage strategy", "<ul><li>Preserve the uploaded TXT/CSV bytes unchanged.</li><li>Record filename, media type, byte count and SHA-256.</li><li>Keep the source payload inside the package.</li></ul>")
    with c2:
        _html_card("architecture-card", "Measurement semantics", "<ul><li>Declare the measured quantity and unit.</li><li>Describe scan setup and processing.</li><li>Report a candidate axis only when it is file-derived.</li></ul>")
    with c3:
        _html_card("architecture-card", "Inspection targets", "<ul><li>Text/CSV tools: source rows and columns.</li><li>Python: repeatable source diagnostics.</li><li>Browser: human-readable metadata and report.</li></ul>")

    st.markdown("### Design decisions linked to the research questions")
    decisions = [
        ("RQ1 · Source preservation", "The original TXT/CSV payload remains available for inspection; the package records its byte identity and derived diagnostics without converting it."),
        ("Laboratory context", "The sidecar records the documented method, scan setup, quantity, unit, processing, calibration status and limitations."),
        ("No value duplication in metadata", "JSON-LD identifies the source file and its meaning. It does not serialise dense vibrometry values as RDF literals."),
    ]
    for title, body in decisions:
        with st.expander(title):
            st.write(body)


def render_ifc_linkage() -> None:
    _page_intro(
        "OpenBIM association without IFC schema modification",
        "The package and BIM model identify the same tested component while high-volume measurement arrays remain external to IFC.",
        "Layer 02 · IFC component context",
    )
    st.markdown("### Hybrid association pattern")
    first, second, third = st.columns(3)
    with first:
        _html_card(
            "architecture-card",
            "Package-side link record",
            "<p><code>ifcLinkRecord</code> records the IFC filename, SHA-256 checksum, IFC schema, target <code>GlobalId</code>, entity type, material/assembly context and declared scan coordinate system.</p><p>It lets the package remain interpretable outside an authoring tool.</p>",
        )
    with second:
        _html_card(
            "architecture-card",
            "Native IFC document pointer",
            "<p>An <code>IfcDocumentReference</code>, associated through <code>IfcRelAssociatesDocument</code>, points the tested component to the external package manifest.</p><p>The original IFC stays intact; an annotated derivative can carry this optional reference.</p>",
        )
    with third:
        _html_card(
            "architecture-card",
            "Viewer-friendly summary",
            "<p><code>Pset_VibrometryMeasurement</code> carries only compact facts: date, scan-point count, frequency range, observed quantity, unit, data-store location and manifest link.</p><p>No raw arrays are stored in IFC properties.</p>",
        )

    st.markdown("### What is verified")
    checks = st.columns(4)
    for col, heading, value in zip(
        checks,
        ("Identity", "Model version", "Component semantics", "Bidirectional reference"),
        ("GlobalId resolves", "IFC checksum matches", "Expected entity and available material context", "Package → component and IFC → manifest"),
    ):
        with col:
            col.metric(heading, "Checked")
            col.caption(value)

    st.warning(
        "The association is deliberately component-level. A scan grid may be described declaratively, but the workflow does not assert point-cloud registration or a spatial mapping algorithm it has not performed."
    )


def render_validation() -> None:
    _page_intro(
        "Validation, traceability & open inspection",
        "Evidence is tested at the numerical, structural, semantic and IFC-context levels so a later user can inspect—not merely trust—the package.",
        "Layer 03 · validation demonstrator",
    )
    st.markdown("### Multi-level validation suite")
    items = (
        ("Structural", "TXT/CSV file gate, source diagnostics, hashes, JSON-LD syntax and SHACL profile checks."),
        ("Source integrity", "The packaged TXT/CSV and IFC bytes are compared with the hashes recorded in the sidecar."),
        ("Semantic", "Competency checks answer: which component, which quantity and unit, which source and which processing activity?"),
        ("IFC context", "IfcOpenShell resolves GlobalId, checks entity type and captures available material/assembly evidence."),
    )
    for col, (heading, body) in zip(st.columns(4), items):
        with col:
            _html_card("validation-card", heading, f"<p>{body}</p>")

    st.markdown("### Inspection workflow")
    st.dataframe(
        [
            {"Tool": "Text/CSV viewer", "Inspects": "Original rows, delimiters and source columns", "Evidence": "Source payload is directly inspectable"},
            {"Tool": "Bonsai / BlenderBIM", "Inspects": "IFC component, attached document reference and summary property set", "Evidence": "Component context is visible in an OpenBIM viewer"},
            {"Tool": "Web browser", "Inspects": "JSON-LD / RO-Crate-style manifest, README and validation report", "Evidence": "Package meaning is reviewable without proprietary software"},
            {"Tool": "Python verifier", "Inspects": "Checksums, TXT/CSV diagnostics, semantic fields and GlobalId resolution", "Evidence": "Repeatable automated verification"},
        ],
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Example competency questions"):
        st.markdown(
            "- Which IFC component was measured, in which IFC file version?\n"
            "- What does `/measurements/velocity` represent and what unit applies?\n"
            "- Which source asset and processing activity produced a selected result?\n"
            "- Does the component GlobalId resolve and does the stored model checksum match?"
        )


def render_fair_evidence() -> None:
    _page_intro(
        "FAIR-support evidence, not a certification claim",
        "The package makes selected FAIR-oriented reuse conditions observable through open formats, identifiers, controlled semantics, provenance and documented rights.",
        "Evaluation lens · FAIR data maturity",
    )
    fair_rows = [
        {"Dimension": "Findable", "Package evidence": "Identifier, labels, acquisition metadata, IFC GlobalId", "Verification": "Manifest parsing and metadata indexing"},
        {"Dimension": "Accessible", "Package evidence": "TXT/CSV, JSON-LD, IFC and documented access instructions", "Verification": "Open with standard text/CSV tools, IfcOpenShell and a browser"},
        {"Dimension": "Interoperable", "Package evidence": "SOSA/SSN, QUDT, PROV-O and explicit IFC context", "Verification": "Resolvable vocabulary references and semantic checks"},
        {"Dimension": "Reusable", "Package evidence": "Lineage, material context, licence, limitations and validation records", "Verification": "Audit trail and competency checks"},
    ]
    st.dataframe(fair_rows, use_container_width=True, hide_index=True)
    st.caption("Assessment is an evidence-oriented project profile. It does not represent formal FAIR certification or a guarantee of repository-level preservation and access control.")

    st.markdown("### Semantic roles")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("**SOSA/SSN**\n\nObservation, procedure, sensor and feature-of-interest context.")
    c2.markdown("**QUDT**\n\nQuantity and unit identifiers for arrays and summary values.")
    c3.markdown("**PROV-O**\n\nSource assets, activities, agents and derivation history.")
    c4.markdown("**IFC**\n\nComponent identity, geometry and material/assembly context.")


def render_package_library() -> None:
    _page_intro(
        "Local acoustic data-package library",
        "Inspect generated research-object packages and export their portable archive. Existing packages remain available while the thesis profile develops iteratively.",
        "Package catalogue",
    )
    objects = packages()
    if not objects:
        st.info("No package is available yet. Use **Package Builder** to upload an IFC model and a vibrometry-derived measurement asset.")
        return

    keyword, status = st.columns([2, 1])
    query = keyword.text_input("Search component, GlobalId, file or measurement identifier")
    options = ["All"] + sorted({item.fair_support_status for item in objects})
    selected_status = status.selectbox("FAIR-support state", options)
    query = query.strip().lower()
    visible = []
    for item in objects:
        searchable = " ".join((item.title, item.package_id, item.ifc_global_id or "", str(item.metadata), str(item.measurement_context))).lower()
        if query and query not in searchable:
            continue
        if selected_status != "All" and item.fair_support_status != selected_status:
            continue
        visible.append(item)

    st.caption(f"{len(visible)} package(s) shown")
    for item in visible:
        with st.container(border=True):
            head, state, download = st.columns([2.3, 1, 1])
            head.markdown(f"### {item.title}\n`{item.package_id}`")
            state.metric("FAIR-support", item.fair_support_status)
            download.download_button(
                "Download package",
                export_research_object(item, strict=False),
                file_name=f"{item.package_id}.zip",
                mime="application/zip",
                key=f"thesis_download_{item.package_id}",
            )
            a, b, c, d = st.columns(4)
            a.caption(f"**IFC GlobalId**\n\n{item.ifc_global_id or 'Not recorded'}")
            b.caption(f"**Data type**\n\n{item.measurement_context.get('measurement_type', 'Not recorded')}")
            c.caption(f"**Origin**\n\n{item.measurement_context.get('origin_classification', 'Not recorded')}")
            d.caption(f"**Lifecycle**\n\n{item.lifecycle_display_status}")
            with st.expander("Package metadata and relationship evidence"):
                st.json(item.to_dict())


def render_method_scope() -> None:
    _page_intro(
        "Method, research questions & boundaries",
        "The website is a research demonstrator for a six-month thesis workflow, focused on reusable experimental data rather than an all-purpose BIM, acoustic simulation or digital-twin platform.",
        "Thesis framing",
    )
    questions = [
        ("RQ1", "How can original SLDV TXT/CSV payloads be preserved and described for traceable reuse?"),
        ("RQ2", "How can variables, units, provenance and IFC component context be described semantically without modifying IFC?"),
        ("RQ3", "How can selected values be traced from a raw export into a package and verified through open tools and scripts?"),
        ("RQ4", "To what extent does the package support structural validity, machine readability, IFC context, inspection and FAIR-oriented reuse?"),
    ]
    for label, question in questions:
        st.markdown(f"**{label}** · {question}")

    st.markdown("### Explicit scope boundaries")
    scope_a, scope_b, scope_c = st.columns(3)
    with scope_a:
        _html_card("scope-card", "Included", "<ul><li>Original SLDV TXT/CSV preservation and inspection</li><li>Semantic metadata and package construction</li><li>IFC component association and validation</li><li>Open-tool inspection workflow</li></ul>")
    with scope_b:
        _html_card("scope-card", "Not developed", "<ul><li>3D registration or mesh-projection algorithm</li><li>IFC EXPRESS schema extension</li><li>Custom visualisation viewer</li><li>Acoustic simulation solver</li></ul>")
    with scope_c:
        _html_card("scope-card", "Standards position", "<ul><li>Use existing standards and practices where suitable</li><li>Do not claim a universal acoustic schema</li><li>Do not claim FAIR certification</li><li>Keep source values outside text metadata</li></ul>")

    st.markdown("### Proposed work plan")
    st.dataframe(
        [
            {"Month": "1", "Focus": "Source profiling & feasibility", "Output": "Raw export profile, IFC inspection, competency questions"},
            {"Month": "2", "Focus": "Schema design", "Output": "TXT/CSV application profile, JSON-LD metadata and link record"},
            {"Month": "3", "Focus": "Package implementation", "Output": "Source-preserving package builder and IFC context extraction"},
            {"Month": "4", "Focus": "Validation demonstrator", "Output": "Structural, numerical and IFC verification evidence"},
            {"Month": "5", "Focus": "Evaluation", "Output": "FAIR-support, retrieval and competency assessment"},
            {"Month": "6", "Focus": "Finalisation", "Output": "Reproducibility package, thesis and defence material"},
        ],
        use_container_width=True,
        hide_index=True,
    )


def run_vibrometry_thesis_app() -> None:
    st.set_page_config(
        page_title="VIBRO•IFC | Thesis RDM Demonstrator",
        page_icon="◌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_state()
    _inject_thesis_css()
    selected = _sidebar()

    if selected == "Thesis Overview":
        render_overview()
    elif selected == "Package Builder":
        _page_intro(
            "Build an IFC-linked vibrometry package",
            "Upload a paired IFC model and a primary measurement asset, establish an explicit qualified relationship, and generate a locally inspectable research-object package.",
            "Workflow implementation",
        )
        st.info("This thesis workflow accepts original SLDV TXT/CSV payloads only. It preserves their bytes and links them to laboratory and IFC context; it does not create an HDF5 derivative.")
        render_research_builder()
    elif selected == "Data Architecture":
        render_data_architecture()
    elif selected == "IFC Linkage":
        render_ifc_linkage()
    elif selected == "Validation & Traceability":
        render_validation()
    elif selected == "FAIR Evidence":
        render_fair_evidence()
    elif selected == "Package Library":
        render_package_library()
    else:
        render_method_scope()
