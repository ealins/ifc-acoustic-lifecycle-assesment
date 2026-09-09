from __future__ import annotations

import hashlib
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from .assessment import apply_assessment
from .completeness import apply_metadata_completeness
from .fair_support_policy import apply_fair_support_profile
from .manifest import manifest_json
from .metadata import metadata_turtle
from .metadata_profile import profile_as_dict
from .models import FairAcousticPackage
from .ro_crate import RO_CRATE_METADATA, ro_crate_json
from .shacl import validate_package_shacl
from .validation import validate_research_object


METADATA_PROFILE_PATH = "profiles/acoustic-metadata-profile.json"
DERIVED_PATHS = {
    "manifest.json",
    RO_CRATE_METADATA,
    METADATA_PROFILE_PATH,
    "checksums/sha256sums.txt",
    "README.txt",
    "evidence/relationship-evidence.json",
    "reports/metadata-completeness-assessment.json",
    "reports/fair-support-assessment.json",
    "reports/relationship-lifecycle-assessment.json",
    # Backward-compatible report paths retained for older integrations/tests.
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
    outcomes = package.independent_outcomes
    return (
        "Acoustic Component Research Object\n"
        "==================================\n\n"
        f"Package: {package.package_id}\n"
        f"Research-object profile: {package.research_object_profile}\n"
        f"Acoustic metadata profile: {package.metadata_profile} (v{package.metadata_profile_version})\n\n"
        "Independent evaluation outcomes:\n"
        f"- Metadata completeness: {outcomes['metadata_completeness']}\n"
        f"- FAIR support: {outcomes['fair_support']}\n"
        f"- Relationship lifecycle: {outcomes['relationship_lifecycle']}\n"
        f"- Acoustic scientific suitability: {outcomes['acoustic_scientific_suitability']}\n\n"
        "Metadata synchronization rules:\n"
        "1. The in-memory domain model is authoritative during application execution.\n"
        "2. ro-crate-metadata.json is the principal portable research-object representation.\n"
        "3. metadata.ttl is the domain RDF/provenance/relationship/assessment serialization.\n"
        "4. manifest.json is a simplified application compatibility manifest derived from the model.\n"
        "5. profiles/acoustic-metadata-profile.json is generated from the executable Python metadata profile.\n\n"
        "This prototype evaluates metadata coverage, package structure, selected FAIR support, and "
        "component-dataset relationship status. It does not establish the scientific validity or "
        "acoustic suitability of measurement values.\n"
    ).encode("utf-8")


def _lifecycle_report(package: FairAcousticPackage) -> dict:
    return {
        "package_id": package.package_id,
        "lifecycle_status": package.lifecycle_status,
        "scientific_suitability_status": package.scientific_suitability_status,
        "mapping_series_uri": package.mapping_series_uri,
        "latest_mapping_assertion_uri": package.latest_mapping_assertion_uri,
        "reassessment_triggers": package.reassessment_triggers,
        "stewardship_history": package.stewardship_history,
        "scope_note": "Lifecycle stewardship evaluates the defensibility of component-dataset relationships, not FAIR certification or acoustic scientific validity.",
    }


def _relationship_report(package: FairAcousticPackage) -> dict:
    return {
        "package_id": package.package_id,
        "relationships": package.relationships,
        "scope_note": "Relationship evidence records why a dataset is linked to an IFC component. Evidence completeness is independent from metadata completeness and scientific suitability.",
    }


def finalize_package(package: FairAcousticPackage) -> None:
    """Synchronize all derived portable representations from the in-memory model."""
    for path in list(package.assets):
        if path in DERIVED_PATHS or path == package.metadata_reference:
            package.assets.pop(path, None)

    # Source/research asset hashes are available to metadata/profile assessment.
    # External resources that were not retrieved are absent from assets and receive no checksum.
    package.checksums = {path: _checksum(data) for path, data in package.assets.items()}

    # Legacy compatibility assessment still receives a real RDF serialization.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    apply_assessment(package)

    # Metadata completeness is independent from FAIR and relationship lifecycle.
    apply_metadata_completeness(package)

    # Generate preliminary portable JSON-LD before FAIR-support assessment because
    # JSON-LD/RO-Crate parseability is one of the selected indicators.
    package.assets[RO_CRATE_METADATA] = ro_crate_json(package).encode("utf-8")
    apply_fair_support_profile(package)

    # Regenerate serializations with current independent assessment state, then SHACL.
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.metadata["shacl_validation"] = validate_package_shacl(package)
    package.assets[package.metadata_reference] = metadata_turtle(package).encode("utf-8")
    package.assets[RO_CRATE_METADATA] = ro_crate_json(package).encode("utf-8")
    package.assets[METADATA_PROFILE_PATH] = _json_bytes(profile_as_dict())

    completeness_bytes = _json_bytes(package.metadata_completeness_assessment)
    fair_bytes = _json_bytes(package.fair_support_assessment)
    lifecycle_bytes = _json_bytes(_lifecycle_report(package))
    relationship_bytes = _json_bytes(_relationship_report(package))

    package.assets["reports/metadata-completeness-assessment.json"] = completeness_bytes
    package.assets["reports/fair-support-assessment.json"] = fair_bytes
    package.assets["reports/relationship-lifecycle-assessment.json"] = lifecycle_bytes
    package.assets["evidence/relationship-evidence.json"] = relationship_bytes

    # Compatibility paths for pre-pivot integrations.
    package.assets["reports/fair-assessment.json"] = fair_bytes
    package.assets["reports/lifecycle-assessment.json"] = lifecycle_bytes
    package.assets["reports/relationship-evidence.json"] = relationship_bytes
    package.assets["README.txt"] = _readme(package)

    # All retrievable package resources except checksum list and manifest are hashed.
    # Those two are excluded from self-referential hashing.
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
