from __future__ import annotations

import hashlib
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from .assessment import apply_assessment
from .fair_support_policy import apply_fair_support_profile
from .manifest import manifest_json
from .metadata import metadata_turtle
from .models import FairAcousticPackage
from .ro_crate import RO_CRATE_METADATA, ro_crate_json
from .shacl import validate_package_shacl
from .validation import validate_research_object


DERIVED_PATHS = {
    "manifest.json",
    RO_CRATE_METADATA,
    "checksums/sha256sums.txt",
    "README.txt",
    "reports/fair-assessment.json",
    "reports/lifecycle-assessment.json",
    "reports/relationship-evidence.json",
    "reports/package-validation.json",
}


def _checksum(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8")


def _checksum_report(package: FairAcousticPackage) -> bytes:
    rows = []
    for path, checksum in sorted(package.checksums.items()):
        rows.append(f"{checksum.replace('sha256:', '')}  {path}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _readme(package: FairAcousticPackage) -> bytes:
    return (
        "Acoustic Component Research Object\n"
        "==================================\n\n"
        f"Package: {package.package_id}\n"
        f"Profile: {package.research_object_profile}\n\n"
        "Metadata synchronization rules:\n"
        "1. The in-memory domain model is authoritative during application execution.\n"
        "2. ro-crate-metadata.json is the principal portable research-object representation.\n"
        "3. metadata.ttl is the domain RDF/provenance/stewardship serialization.\n"
        "4. manifest.json is a simplified application compatibility manifest derived from the model.\n\n"
        "This prototype evaluates metadata, package structure, and relationship stewardship. "
        "It does not establish the scientific validity or acoustic suitability of measurement values.\n"
    ).encode("utf-8")


def finalize_package(package: FairAcousticPackage) -> None:
    """Synchronize all derived portable representations from the in-memory model."""
    for path in list(package.assets):
        if path in DERIVED_PATHS or path == package.metadata_reference:
            package.assets.pop(path, None)

    # Source/research asset hashes are available to both RDF and RO-Crate generation.
    package.checksums = {path: _checksum(data) for path, data in package.assets.items()}

    # Legacy compatibility assessment still receives a real RDF serialization.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    apply_assessment(package)

    # Generate a preliminary portable JSON-LD graph before FAIR-support assessment,
    # because JSON-LD/RO-Crate parseability is itself one of the selected indicators.
    package.assets[RO_CRATE_METADATA] = ro_crate_json(package).encode("utf-8")
    apply_fair_support_profile(package)

    # Regenerate RDF and RO-Crate with the current assessment state, then run SHACL.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.metadata["shacl_validation"] = validate_package_shacl(package)
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.assets[RO_CRATE_METADATA] = ro_crate_json(package).encode("utf-8")

    package.assets["reports/fair-assessment.json"] = _json_bytes(package.fair_support_assessment)
    package.assets["reports/lifecycle-assessment.json"] = _json_bytes({
        "package_id": package.package_id,
        "lifecycle_status": package.lifecycle_status,
        "scientific_suitability_status": package.scientific_suitability_status,
        "mapping_series_uri": package.mapping_series_uri,
        "latest_mapping_assertion_uri": package.latest_mapping_assertion_uri,
        "reassessment_triggers": package.reassessment_triggers,
        "stewardship_history": package.stewardship_history,
        "scope_note": "Lifecycle stewardship evaluates the defensibility of geometry-measurement relationships, not FAIR certification or acoustic scientific validity.",
    })
    package.assets["reports/relationship-evidence.json"] = _json_bytes({
        "package_id": package.package_id,
        "relationships": package.relationships,
    })
    package.assets["README.txt"] = _readme(package)

    # All retrievable package resources except the checksum list and manifest are
    # hashed. Those two are intentionally excluded from self-referential hashing.
    package.checksums = {
        path: _checksum(data)
        for path, data in package.assets.items()
        if path not in {"manifest.json", "checksums/sha256sums.txt"}
    }
    package.assets["checksums/sha256sums.txt"] = _checksum_report(package)
    package.assets["manifest.json"] = manifest_json(package).encode("utf-8")

    package.validation_report = validate_research_object(package)
    package.assets["reports/package-validation.json"] = _json_bytes(package.validation_report)
    package.checksums["reports/package-validation.json"] = _checksum(package.assets["reports/package-validation.json"])
    package.assets["checksums/sha256sums.txt"] = _checksum_report(package)
    package.assets["manifest.json"] = manifest_json(package).encode("utf-8")


def refresh_derived_assets(package: FairAcousticPackage) -> None:
    finalize_package(package)


def export_fair_package(package: FairAcousticPackage) -> bytes:
    """Backward-compatible export; validation evidence is included but not enforced."""
    finalize_package(package)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in sorted(package.assets.items()):
            archive.writestr(path, content)
    return buffer.getvalue()


def _zip_bytes(package: FairAcousticPackage) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in sorted(package.assets.items()):
            archive.writestr(path, content)
    return buffer.getvalue()


def export_research_object(package: FairAcousticPackage, *, strict: bool = True) -> bytes:
    """Validate and export the preferred research-object archive without double-finalizing."""
    finalize_package(package)
    if strict and not package.validation_report.get("valid"):
        messages = [item.get("message") for item in package.validation_report.get("issues", []) if item.get("severity") == "ERROR"]
        raise ValueError("Research object validation failed: " + "; ".join(messages))
    return _zip_bytes(package)
