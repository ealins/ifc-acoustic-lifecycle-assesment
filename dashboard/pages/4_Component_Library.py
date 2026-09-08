"""Searchable in-session FAIR Acoustic Component Library."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dashboard.backend.fair_bridge import ensure_state, packages, set_current
from dashboard.ui.fair_dashboard import hero, inject_platform_css
from fair_platform.catalog import PackageCatalog
from fair_platform.export import export_fair_package

st.set_page_config(page_title="Component Library", page_icon="▦", layout="wide")
inject_platform_css()
ensure_state()

hero(
    "Acoustic Component Library",
    "Browse FAIR packages as reusable research components. Search across package identity, IFC GlobalId, creator and measurement context, then inspect or export the complete package.",
    "Workspace 04 · Reuse",
)

all_packages = packages()
if not all_packages:
    st.info("The library is empty. Generate a package first.")
    st.stop()

filter1, filter2 = st.columns([2, 1])
query = filter1.text_input("Search", placeholder="GlobalId, creator, method, package id...")
statuses = ["ALL"] + sorted({p.fair_status.value for p in all_packages})
status_filter = filter2.selectbox("FAIR status", statuses)
results = PackageCatalog.search(all_packages, query=query, fair_status=status_filter)

st.caption(f"{len(results)} package(s) in current view")

for package in reversed(results):
    with st.container(border=True):
        top = st.columns([2.2, 1, 1, 1])
        top[0].markdown(f"### {package.package_id}\n`{package.ifc_global_id or 'no GlobalId'}`")
        top[1].metric("FAIR", package.fair_status.value)
        top[2].metric("Lifecycle", package.lifecycle_status)
        top[3].metric("Version", package.version)

        tags = [
            package.measurement_context.get("measurement_method"),
            package.measurement_context.get("construction_family"),
            package.creator,
        ]
        st.caption(" · ".join(str(tag) for tag in tags if tag))

        a, b, c = st.columns([1, 1, 2])
        if a.button("Use package", key=f"use_{package.package_id}"):
            set_current(package.package_id)
            st.success("Set as current package for Assessment and Stewardship.")
        b.download_button(
            "Export ZIP",
            export_fair_package(package),
            file_name=f"{package.package_id}.zip",
            mime="application/zip",
            key=f"zip_{package.package_id}",
        )
        with c.expander("Metadata"):
            st.json(package.to_dict())
