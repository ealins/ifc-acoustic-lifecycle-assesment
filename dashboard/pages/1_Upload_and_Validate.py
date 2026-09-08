"""FAIR Package Builder."""
from pathlib import Path
import sys
import tempfile

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dashboard.backend.fair_bridge import add_package, ensure_state
from dashboard.backend.ifc_parser import extract_walls_from_ifc
from dashboard.ui.fair_dashboard import hero, inject_platform_css
from fair_platform.export import export_fair_package
from fair_platform.package_builder import FairPackageBuilder

st.set_page_config(page_title="FAIR Package Builder", page_icon="＋", layout="wide")
inject_platform_css()
ensure_state()

hero(
    "FAIR Package Builder",
    "Create a research package from IFC geometry, an acoustic measurement dataset and the metadata required for discovery, interpretation and reuse.",
    "Workspace 01 · Build",
)

if "builder_ifc_walls" not in st.session_state:
    st.session_state.builder_ifc_walls = []

col_ifc, col_measurement = st.columns(2, gap="large")

with col_ifc:
    st.markdown("### 1 · IFC geometry")
    ifc_file = st.file_uploader("IFC model", type=["ifc"], key="fair_ifc")
    selected_wall = None
    if ifc_file:
        if st.button("Inspect IFC elements", use_container_width=True):
            try:
                with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
                    tmp.write(ifc_file.getvalue())
                    tmp_path = Path(tmp.name)
                st.session_state.builder_ifc_walls = [
                    wall for wall in extract_walls_from_ifc(tmp_path)
                    if wall.get("extraction_success")
                ]
                tmp_path.unlink(missing_ok=True)
            except Exception as exc:
                st.error(f"IFC extraction failed: {exc}")

    walls = st.session_state.builder_ifc_walls
    if walls:
        def wall_label(w):
            thickness = w.get("total_thickness_m")
            t = f"{thickness:.3f} m" if isinstance(thickness, (int, float)) else "thickness n/a"
            return f"{w.get('name', 'Unnamed')} · {w.get('construction_family', 'Unknown')} · {t}"
        selected_wall = st.selectbox("Component", walls, format_func=wall_label)
        st.caption(f"GlobalId: `{selected_wall.get('global_id')}`")
        st.write("Materials:", ", ".join(selected_wall.get("material_evidence", [])))
    else:
        st.caption("Upload an IFC and inspect it, or provide the GlobalId manually below.")

    ifc_global_id = st.text_input(
        "IFC GlobalId",
        value=(selected_wall or {}).get("global_id", ""),
        help="Persistent IFC element identity used by FAIR Findability and lifecycle stewardship.",
    )

with col_measurement:
    st.markdown("### 2 · Measurement dataset")
    measurement_file = st.file_uploader(
        "Acoustic / vibration measurement",
        type=["xml", "csv", "json", "txt", "dat", "h5", "hdf5", "vtk"],
        key="fair_measurement",
    )
    measurement_identifier = st.text_input("Measurement identifier", placeholder="e.g. VaBDat-310 or LAB-RW-2026-014")
    dataset_uri = st.text_input("Dataset URI", placeholder="https://repository.example.org/dataset/...")
    method = st.text_input("Measurement method", placeholder="e.g. ISO 10140 airborne sound insulation")
    instrument = st.text_input("Instrument", placeholder="Measurement system / sensor / analyzer")

st.markdown("### 3 · Research metadata")
meta1, meta2, meta3 = st.columns(3)
with meta1:
    creator = st.text_input("Creator / author")
    institution = st.text_input("Institution")
    version = st.text_input("Package version", value="1.0.0")
with meta2:
    license_uri = st.text_input("Reuse license", value="https://creativecommons.org/licenses/by/4.0/")
    uncertainty = st.text_input("Uncertainty", placeholder="e.g. ±1.2 dB")
    quality = st.text_area("Quality statement", placeholder="Calibration, completeness, QA/QC notes...", height=100)
with meta3:
    measurement_family = st.text_input("Measured construction family", value=(selected_wall or {}).get("construction_family", ""))
    default_thickness = (selected_wall or {}).get("total_thickness_m")
    measurement_thickness = st.number_input("Measured assembly thickness (m)", min_value=0.0, value=float(default_thickness or 0.0), step=0.005)
    assembly = st.text_input("Assembly / specimen description")

st.markdown("### 4 · Generate")
ready = bool(ifc_file and measurement_file)
if st.button("Generate FAIR Acoustic Package", type="primary", use_container_width=True, disabled=not ready):
    builder = FairPackageBuilder()
    geometry_meta = selected_wall or {}
    package = builder.build(
        ifc_file.getvalue(),
        ifc_file.name,
        measurement_file.getvalue(),
        measurement_file.name,
        ifc_global_id=ifc_global_id,
        creator=creator,
        version=version,
        dataset_uri=dataset_uri,
        license_uri=license_uri,
        provenance={"creator": creator, "institution": institution},
        measurement_context={
            "measurement_method": method,
            "instrument": instrument,
            "construction_family": measurement_family,
            "total_thickness_m": measurement_thickness,
            "assembly": assembly,
        },
        quality_information={"uncertainty": uncertainty, "quality_statement": quality},
        metadata={
            "measurement_identifier": measurement_identifier,
            "geometry_name": geometry_meta.get("name", ""),
            "geometry_construction_family": geometry_meta.get("construction_family", ""),
            "geometry_total_thickness_m": geometry_meta.get("total_thickness_m"),
            "geometry_materials": geometry_meta.get("material_evidence", []),
            "model_version": geometry_meta.get("model_version", Path(ifc_file.name).stem),
        },
    )
    add_package(package)
    st.success(f"Created {package.package_id} · {package.fair_status.value}")
    st.download_button(
        "Download package.zip",
        export_fair_package(package),
        file_name=f"{package.package_id}.zip",
        mime="application/zip",
        use_container_width=True,
    )
    with st.expander("Package manifest preview", expanded=True):
        st.json(package.to_dict())

if not ready:
    st.caption("An IFC file and a measurement dataset are required to generate a package. Missing FAIR metadata can still be assessed explicitly after creation.")
