"""Bridge between Streamlit session state and FAIR domain objects."""
from __future__ import annotations

import streamlit as st

from fair_platform.models import FairAcousticPackage


PACKAGES_KEY = "fair_packages"
CURRENT_KEY = "current_fair_package_id"


def ensure_state() -> None:
    if PACKAGES_KEY not in st.session_state:
        st.session_state[PACKAGES_KEY] = []
    if CURRENT_KEY not in st.session_state:
        st.session_state[CURRENT_KEY] = None


def packages() -> list[FairAcousticPackage]:
    ensure_state()
    return st.session_state[PACKAGES_KEY]


def add_package(package: FairAcousticPackage) -> None:
    ensure_state()
    existing = [p for p in packages() if p.package_id != package.package_id]
    existing.append(package)
    st.session_state[PACKAGES_KEY] = existing
    st.session_state[CURRENT_KEY] = package.package_id


def get_package(package_id: str | None = None) -> FairAcousticPackage | None:
    ensure_state()
    target = package_id or st.session_state[CURRENT_KEY]
    return next((p for p in packages() if p.package_id == target), None)


def set_current(package_id: str) -> None:
    ensure_state()
    st.session_state[CURRENT_KEY] = package_id
