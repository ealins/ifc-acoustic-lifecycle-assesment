"""Lifecycle stewardship workspace backed by the existing validation engine."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dashboard.backend.fair_bridge import ensure_state, get_package, packages, set_current
from dashboard.backend.validators import RecordEvidence, TieredValidator, WallEvidence
from dashboard.ui.fair_dashboard import hero, inject_platform_css

st.set_page_config(page_title="Lifecycle Stewardship", page_icon="↻", layout="wide")
inject_platform_css()
ensure_state()

hero(
    "Lifecycle Stewardship",
    "Reuse the existing three-tier lifecycle engine as a FAIR stewardship mechanism: verify link integrity, semantic correspondence, version evidence and review requirements over time.",
    "Workspace 03 · Steward",
)

all_packages = packages()
if not all_packages:
    st.warning("No FAIR package exists yet.")
    st.stop()

selected_id = st.selectbox("Package", [p.package_id for p in all_packages], index=max(0, len(all_packages)-1))
set_current(selected_id)
package = get_package(selected_id)

geometry_family = package.metadata.get("geometry_construction_family", "") or "Unknown Family"
geometry_thickness = package.metadata.get("geometry_total_thickness_m")
geometry_materials = package.metadata.get("geometry_materials", [])
measurement_family = package.measurement_context.get("construction_family", "") or "Unknown Family"
measurement_thickness = package.measurement_context.get("total_thickness_m")

summary = st.columns(4)
summary[0].metric("Current FAIR", package.fair_status.value)
summary[1].metric("Lifecycle", package.lifecycle_status)
summary[2].metric("IFC version", package.metadata.get("model_version", "n/a"))
summary[3].metric("Package version", package.version)

st.markdown("### Evidence pair")
a, b = st.columns(2)
with a:
    st.markdown("**IFC geometry evidence**")
    st.write({
        "GlobalId": package.ifc_global_id,
        "family": geometry_family,
        "thickness_m": geometry_thickness,
        "materials": geometry_materials,
    })
with b:
    st.markdown("**Measurement evidence**")
    st.write({
        "identifier": package.metadata.get("measurement_identifier", package.package_id),
        "dataset_uri": package.dataset_uri,
        "family": measurement_family,
        "thickness_m": measurement_thickness,
        "assembly": package.measurement_context.get("assembly"),
    })

if st.button("Run lifecycle stewardship assessment", type="primary", use_container_width=True):
    wall = WallEvidence(
        global_id=package.ifc_global_id or "",
        name=package.metadata.get("geometry_name", "IFC component"),
        construction_family=geometry_family,
        total_thickness_m=geometry_thickness,
        material_evidence=geometry_materials,
        model_version=package.metadata.get("model_version", package.version),
    )
    record = RecordEvidence(
        uri=package.dataset_uri or "",
        identifier=package.metadata.get("measurement_identifier", package.package_id),
        assembly=package.measurement_context.get("assembly", ""),
        construction_family=measurement_family,
        total_thickness_m=measurement_thickness,
        record_version=package.version,
        available=bool(package.measurement_reference in package.assets),
    )
    try:
        result = TieredValidator(0.02).validate_all(wall, record)
        package.lifecycle_status = result.overall_status.value
        st.session_state[f"stewardship_{package.package_id}"] = result
        st.success(f"Lifecycle stewardship state: {package.lifecycle_status}")
    except Exception as exc:
        st.error(f"Stewardship assessment failed: {exc}")

result = st.session_state.get(f"stewardship_{package.package_id}")
if result:
    st.markdown("### Stewardship decision")
    st.markdown(f"**{result.overall_status.value}** — {result.rationale}")
    columns = st.columns(3)
    tiers = [
        ("Link integrity", result.tier_1_link),
        ("Semantic correspondence", result.tier_2_mapping),
        ("Lifecycle evidence", result.tier_3_lifecycle),
    ]
    for col, (title, checks) in zip(columns, tiers):
        with col:
            passed = sum(1 for check in checks if check.passed)
            st.metric(title, f"{passed}/{len(checks)}")
            for check in checks:
                st.caption(f"{'✅' if check.passed else '❌'} {check.name}: {check.description}")

st.divider()
st.caption("The existing lifecycle engine and status model are preserved. This workspace changes their research role: lifecycle assessment is now the stewardship layer of the FAIR package.")
