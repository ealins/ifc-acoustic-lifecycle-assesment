"""Streamlit app: dashboard and engine for the v0.6 SLDV sidecar profile."""
from __future__ import annotations

import streamlit as st

from vibro_ifc import pages

NAV = {
    "Overview": pages.render_overview,
    "Sidecar v0.6": pages.render_sidecar_v06,
    "All records": pages.render_records,
    "Method and scope": pages.render_method,
}


def run() -> None:
    st.set_page_config(page_title="VIBRO-IFC | Sidecar dashboard", layout="wide", initial_sidebar_state="expanded")
    with st.sidebar:
        st.markdown("## VIBRO-IFC")
        st.caption("SLDV measurements linked to IFC")
        choice = st.radio("Page", list(NAV), label_visibility="collapsed")
    NAV[choice]()
