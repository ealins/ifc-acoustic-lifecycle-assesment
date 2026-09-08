"""FAIR assessment dashboard."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dashboard.backend.fair_bridge import ensure_state, get_package, packages, set_current
from dashboard.ui.fair_dashboard import hero, inject_platform_css, render_fair_cards
from fair_platform.assessment import apply_assessment
from fair_platform.export import export_fair_package

st.set_page_config(page_title="FAIR Assessment", page_icon="◎", layout="wide")
inject_platform_css()
ensure_state()

hero(
    "FAIR Assessment",
    "Evaluate the package against explicit Findable, Accessible, Interoperable and Reusable checks. Every score remains explainable at criterion level.",
    "Workspace 02 · Assess",
)

all_packages = packages()
if not all_packages:
    st.warning("No package exists yet. Create one in FAIR Package Builder first.")
    st.stop()

selected_id = st.selectbox("Package", [p.package_id for p in all_packages], index=max(0, len(all_packages)-1))
set_current(selected_id)
package = get_package(selected_id)
result = apply_assessment(package)

render_fair_cards(result)

st.markdown("### Overall FAIR state")
left, middle, right = st.columns([1.2, 1, 1])
left.metric("FAIR status", result.fair_status.value)
middle.metric("Composite readiness", f"{result.score:.0%}")
right.metric("Lifecycle status", package.lifecycle_status)

if result.blocking_states:
    st.caption("Deficiency classes: " + " · ".join(result.blocking_states))
else:
    st.success("All configured FAIR checks pass for the current package state.")

st.markdown("### Criterion-level evidence")
for label, dimension in [
    ("Findable", result.findable),
    ("Accessible", result.accessible),
    ("Interoperable", result.interoperable),
    ("Reusable", result.reusable),
]:
    with st.expander(f"{label} · {dimension.score:.0%}", expanded=not dimension.passed):
        for name, passed in dimension.checks.items():
            st.write(f"{'✅' if passed else '❌'} **{name.replace('_', ' ').title()}**")

st.markdown("### Package identity")
st.code(package.identifier, language=None)
cols = st.columns(3)
cols[0].write(f"**IFC GlobalId**\n\n`{package.ifc_global_id or 'missing'}`")
cols[1].write(f"**Dataset URI**\n\n{package.dataset_uri or 'missing'}")
cols[2].write(f"**License**\n\n{package.license or 'missing'}")

st.download_button(
    "Export assessed package",
    export_fair_package(package),
    file_name=f"{package.package_id}.zip",
    mime="application/zip",
    type="primary",
)
