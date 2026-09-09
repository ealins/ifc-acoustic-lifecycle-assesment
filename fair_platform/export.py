from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from .assessment import apply_assessment
from .manifest import manifest_json
from .metadata import metadata_turtle
from .models import FairAcousticPackage
from .shacl import validate_package_shacl


def _checksum(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def finalize_package(package: FairAcousticPackage) -> None:
    package.checksums = {
        path: _checksum(data)
        for path, data in package.assets.items()
        if path not in {package.metadata_reference, "manifest.json"}
    }

    # Generate metadata once so FAIR assessment can test real RDF bytes.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.checksums[package.metadata_reference] = _checksum(package.assets[package.metadata_reference])

    apply_assessment(package)

    # Rebuild RDF with current FAIR state, execute the SHACL profile, and retain the report.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.metadata["shacl_validation"] = validate_package_shacl(package)

    # Final metadata includes the SHACL conformance summary itself.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.checksums[package.metadata_reference] = _checksum(package.assets[package.metadata_reference])
    package.assets["manifest.json"] = manifest_json(package).encode("utf-8")


def refresh_derived_assets(package: FairAcousticPackage) -> None:
    finalize_package(package)


def export_fair_package(package: FairAcousticPackage) -> bytes:
    finalize_package(package)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in sorted(package.assets.items()):
            archive.writestr(path, content)
    return buffer.getvalue()
