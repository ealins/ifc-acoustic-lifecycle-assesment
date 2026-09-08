from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from .manifest import manifest_json
from .metadata import metadata_turtle
from .models import FairAcousticPackage


def refresh_derived_assets(package: FairAcousticPackage) -> None:
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.assets["manifest.json"] = manifest_json(package).encode("utf-8")


def export_fair_package(package: FairAcousticPackage) -> bytes:
    refresh_derived_assets(package)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in package.assets.items():
            archive.writestr(path, content)
    return buffer.getvalue()
