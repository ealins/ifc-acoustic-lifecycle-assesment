"""Persistent Streamlit bridge for FAIR packages."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from fair_platform.models import FairAcousticPackage
from fair_platform.repository import PackageRepository

PACKAGES_KEY = "fair_packages"
CURRENT_KEY = "current_fair_package_id"
LOADED_KEY = "fair_repository_loaded"


def repository() -> PackageRepository:
    root = Path(os.getenv("FAIR_PACKAGE_STORE", "packages"))
    return PackageRepository(root)


def ensure_state(force_reload: bool = False) -> None:
    if force_reload or not st.session_state.get(LOADED_KEY):
        st.session_state[PACKAGES_KEY] = repository().list_packages()
        st.session_state[LOADED_KEY] = True
    if CURRENT_KEY not in st.session_state:
        st.session_state[CURRENT_KEY] = st.session_state[PACKAGES_KEY][0].package_id if st.session_state[PACKAGES_KEY] else None


def packages() -> list[FairAcousticPackage]:
    ensure_state()
    return st.session_state[PACKAGES_KEY]


def _replace(package: FairAcousticPackage) -> None:
    current = [item for item in packages() if item.package_id != package.package_id]
    current.append(package)
    current.sort(key=lambda item: item.created, reverse=True)
    st.session_state[PACKAGES_KEY] = current


def add_package(package: FairAcousticPackage) -> None:
    repository().save(package)
    _replace(package)
    st.session_state[CURRENT_KEY] = package.package_id


def update_package(package: FairAcousticPackage) -> None:
    repository().save(package)
    _replace(package)
    st.session_state[CURRENT_KEY] = package.package_id


def get_package(package_id: str | None = None) -> FairAcousticPackage | None:
    ensure_state()
    target = package_id or st.session_state.get(CURRENT_KEY)
    return next((item for item in packages() if item.package_id == target), None)


def set_current(package_id: str) -> None:
    ensure_state()
    st.session_state[CURRENT_KEY] = package_id


def delete_package(package_id: str) -> None:
    repository().delete(package_id)
    ensure_state(force_reload=True)
    if st.session_state.get(CURRENT_KEY) == package_id:
        st.session_state[CURRENT_KEY] = packages()[0].package_id if packages() else None
