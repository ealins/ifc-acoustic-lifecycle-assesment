from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse

from rdflib import Graph

from .metadata_profile import PROFILE_VERSION
from .models import FairAcousticPackage, utc_now
from .research_object import MeasurementOrigin, RelationshipType, relationship_type_allowed_for_origin


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    entity: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def safe_relative_archive_path(path: str) -> bool:
    candidate = PurePosixPath(str(path).replace("\\", "/"))
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts


def valid_uri(value: str | None) -> bool:
    if not value:
        return False
    return urlparse(str(value).strip()).scheme in {"http", "https", "urn", "doi"}


def sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_serializations(package: FairAcousticPackage) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        Graph().parse(data=package.assets.get(package.metadata_reference, b"").decode("utf-8"), format="turtle")
    except Exception as exc:
        issues.append(ValidationIssue("TURTLE_INVALID", "ERROR", f"Domain RDF/Turtle cannot be parsed: {exc}", package.metadata_reference))
    try:
        crate_text = package.assets.get("ro-crate-metadata.json", b"").decode("utf-8")
        crate = json.loads(crate_text)
        if not isinstance(crate, dict) or "@context" not in crate or "@graph" not in crate:
            raise ValueError("JSON-LD object must contain @context and @graph")
        Graph().parse(data=crate_text, format="json-ld")
    except Exception as exc:
        issues.append(ValidationIssue("JSONLD_INVALID", "ERROR", f"ro-crate-metadata.json cannot be parsed as JSON-LD: {exc}", "ro-crate-metadata.json"))
    try:
        profile = json.loads(package.assets.get("profiles/acoustic-metadata-profile.json", b"").decode("utf-8"))
        if profile.get("version") != PROFILE_VERSION or not isinstance(profile.get("fields"), list):
            raise ValueError("profile version/field registry does not match the active executable metadata profile")
    except Exception as exc:
        issues.append(ValidationIssue("METADATA_PROFILE_INVALID", "ERROR", f"Machine-readable acoustic metadata profile snapshot is invalid: {exc}", "profiles/acoustic-metadata-profile.json"))
    return issues


def _known_asset_references(package: FairAcousticPackage) -> set[str]:
    refs = set(package.assets)
    for record in package.asset_records:
        for key in ("path", "asset_id", "original_filename", "source_filename", "source_uri"):
            value = record.get(key)
            if value:
                refs.add(str(value))
    return refs


def _measurement_record(package: FairAcousticPackage) -> dict[str, Any]:
    return next(
        (
            item for item in package.asset_records
            if item.get("path") == package.measurement_reference
            or item.get("role") == "primary-acoustic-dataset"
        ),
        {},
    )


def _validate_report_identity(package: FairAcousticPackage, path: str, key: str = "package_id") -> list[ValidationIssue]:
    payload = package.assets.get(path)
    if not payload:
        return [ValidationIssue("REPORT_MISSING", "ERROR", f"Required assessment report '{path}' is missing.", package.package_id, path)]
    try:
        report = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        return [ValidationIssue("REPORT_INVALID", "ERROR", f"Assessment report '{path}' cannot be parsed as JSON: {exc}", path)]
    report_package = report.get(key)
    if report_package != package.package_id:
        return [ValidationIssue("REPORT_PACKAGE_MISMATCH", "ERROR", f"Assessment report '{path}' identifies package '{report_package}' instead of '{package.package_id}'.", path, key)]
    return []


def validate_package_id_uniqueness(packages: Iterable[FairAcousticPackage]) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for package in packages:
        if package.package_id in seen:
            issues.append(ValidationIssue("PACKAGE_ID_DUPLICATE", "ERROR", f"Package identifier '{package.package_id}' occurs more than once in the prototype library.", package.package_id, "package_id"))
        seen.add(package.package_id)
    return issues


def validate_research_object(package: FairAcousticPackage) -> dict[str, Any]:
    issues: list[ValidationIssue] = []

    def add(code: str, severity: str, message: str, entity: str, field: str | None = None) -> None:
        issues.append(ValidationIssue(code, severity, message, entity, field))

    explicit_title = str(package.metadata.get("title") or "").strip()
    if not package.package_id:
        add("PACKAGE_ID_MISSING", "ERROR", "Research object has no local package identifier.", "research_object", "package_id")
    if not explicit_title:
        add("PACKAGE_TITLE_MISSING", "ERROR", "Research object title is missing; the UI fallback label is not treated as supplied descriptive metadata.", package.package_id, "title")
    if not package.ifc_global_id:
        add("IFC_GLOBALID_MISSING", "ERROR", "No selected IFC GlobalId is recorded for the component relationship.", package.package_id, "ifc_global_id")
    if package.geometry_reference not in package.assets:
        add("PRIMARY_IFC_ASSET_MISSING", "ERROR", f"Required IFC source asset '{package.geometry_reference}' is missing from the package.", package.package_id, "geometry_reference")

    measurement_record = _measurement_record(package)
    measurement_packaged = bool(measurement_record.get("packaged", package.measurement_reference in package.assets))
    if measurement_packaged and package.measurement_reference not in package.assets:
        add("PRIMARY_DATASET_MISSING", "ERROR", f"Acoustic dataset '{package.measurement_reference}' is declared packaged but is absent from the package.", package.package_id, "measurement_reference")
    if not measurement_packaged and not package.dataset_uri:
        add("EXTERNAL_DATASET_URI_MISSING", "ERROR", "Primary acoustic dataset is not packaged and no external dataset URI is recorded.", package.package_id, "dataset_uri")

    for path in package.assets:
        if not safe_relative_archive_path(path):
            add("UNSAFE_ARCHIVE_PATH", "ERROR", f"Asset path '{path}' is not a safe relative archive path.", path, "path")
    for path, expected in package.checksums.items():
        if path not in package.assets:
            add("CHECKSUM_TARGET_MISSING", "ERROR", f"Checksum exists for '{path}', but the asset is missing.", path, "checksums")
        elif sha256(package.assets[path]) != expected:
            add("CHECKSUM_MISMATCH", "ERROR", f"Checksum mismatch for '{path}'.", path, "checksums")

    seen_assets: set[str] = set()
    for record in package.asset_records:
        asset_id = str(record.get("asset_id") or record.get("path") or "")
        if not asset_id:
            add("ASSET_ID_MISSING", "ERROR", "An asset record has no identifier or path.", package.package_id, "asset_records")
        elif asset_id in seen_assets:
            add("ASSET_ID_DUPLICATE", "ERROR", f"Asset identifier '{asset_id}' occurs more than once.", asset_id, "asset_id")
        seen_assets.add(asset_id)
        path = record.get("path")
        if path and record.get("packaged", True) and path not in package.assets:
            add("DECLARED_ASSET_MISSING", "ERROR", f"Declared packaged asset '{path}' is absent.", asset_id or package.package_id, "path")
        if not record.get("packaged", True):
            if record.get("checksum"):
                add("EXTERNAL_CHECKSUM_UNSUPPORTED", "ERROR", f"External asset '{asset_id}' has a checksum even though its bytes were not retrieved by this package workflow.", asset_id, "checksum")
            if record.get("size_bytes") is not None:
                add("EXTERNAL_SIZE_UNVERIFIED", "ERROR", f"External asset '{asset_id}' has a byte size even though source bytes were not retrieved.", asset_id, "size_bytes")

    measurement_id = str(package.metadata.get("measurement_identifier") or "")
    if not measurement_id:
        add("MEASUREMENT_ID_MISSING", "ERROR", "Primary acoustic dataset has no explicit dataset identifier.", package.measurement_reference, "measurement_identifier")
    origin = str(package.measurement_context.get("origin_classification") or (package.metadata.get("measurement_inspection") or {}).get("origin_classification") or MeasurementOrigin.UNKNOWN_ORIGIN.value)
    if origin in {MeasurementOrigin.UNKNOWN_ORIGIN.value, "unknown"}:
        add("MEASUREMENT_ORIGIN_UNKNOWN", "WARNING", "Acoustic dataset origin is unknown; origin was not inferred from file structure.", measurement_id or package.measurement_reference, "origin_classification")

    known_asset_refs = _known_asset_references(package)
    relationship_ids: set[str] = set()
    for relationship in package.relationships:
        rid = str(relationship.get("relationship_id") or "")
        if not rid:
            add("RELATIONSHIP_ID_MISSING", "ERROR", "A component-dataset relationship has no identifier.", package.package_id, "relationships")
            continue
        if rid in relationship_ids:
            add("RELATIONSHIP_ID_DUPLICATE", "ERROR", f"Relationship identifier '{rid}' occurs more than once.", rid, "relationship_id")
        relationship_ids.add(rid)
        if relationship.get("subject_ifc_global_id") != package.ifc_global_id:
            add("RELATIONSHIP_COMPONENT_UNKNOWN", "ERROR", f"Relationship '{rid}' does not reference the selected IFC GlobalId '{package.ifc_global_id}'.", rid, "subject_ifc_global_id")
        if measurement_id and relationship.get("object_measurement_id") != measurement_id:
            add("RELATIONSHIP_MEASUREMENT_UNKNOWN", "ERROR", f"Relationship '{rid}' references dataset '{relationship.get('object_measurement_id')}' instead of package dataset '{measurement_id}'.", rid, "object_measurement_id")
        relation_type = str(relationship.get("relationship_type") or RelationshipType.UNKNOWN.value)
        allowed, reason = relationship_type_allowed_for_origin(origin, relation_type)
        if not allowed:
            add("RELATIONSHIP_TYPE_INCOMPATIBLE", "ERROR", f"Relationship '{rid}' is incompatible with dataset origin '{origin}': {reason}", rid, "relationship_type")
        if not str(relationship.get("rationale") or "").strip():
            add("RELATIONSHIP_RATIONALE_MISSING", "ERROR", f"Relationship '{rid}' has no rationale explaining why the dataset applies to the selected IFC component.", rid, "rationale")
        evidence = relationship.get("evidence") or []
        if not evidence:
            add("RELATIONSHIP_EVIDENCE_MISSING", "ERROR", f"Relationship '{rid}' has no structured evidence items.", rid, "evidence")
        evidence_ids: set[str] = set()
        for item in evidence:
            eid = str(item.get("evidence_id") or "")
            if not eid:
                add("EVIDENCE_ID_MISSING", "ERROR", f"Relationship '{rid}' contains evidence with no identifier.", rid, "evidence")
            elif eid in evidence_ids:
                add("EVIDENCE_ID_DUPLICATE", "ERROR", f"Evidence identifier '{eid}' occurs more than once.", rid, "evidence")
            evidence_ids.add(eid)
            source_asset = item.get("source_asset")
            if source_asset and str(source_asset) not in known_asset_refs and not valid_uri(str(source_asset)):
                add("EVIDENCE_SOURCE_UNKNOWN", "ERROR", f"Evidence '{eid}' references unknown source '{source_asset}'.", eid, "source_asset")
        source_dataset_version = relationship.get("source_measurement_version")
        current_dataset_version = package.measurement_context.get("measurement_version")
        if source_dataset_version and current_dataset_version and str(source_dataset_version) != str(current_dataset_version):
            add("RELATIONSHIP_DATASET_VERSION_MISMATCH", "ERROR", f"Relationship '{rid}' was assessed against dataset version '{source_dataset_version}' but the package contains version '{current_dataset_version}'.", rid, "source_measurement_version")
        source_ifc_version = relationship.get("source_component_version")
        current_ifc_version = package.metadata.get("model_version")
        if source_ifc_version and current_ifc_version and str(source_ifc_version) != str(current_ifc_version):
            add("RELATIONSHIP_IFC_VERSION_MISMATCH", "ERROR", f"Relationship '{rid}' was assessed against IFC version '{source_ifc_version}' but the package contains version '{current_ifc_version}'.", rid, "source_component_version")
        if relationship.get("source_ifc_checksum") and relationship.get("source_ifc_checksum") != package.checksums.get(package.geometry_reference):
            add("RELATIONSHIP_IFC_CHECKSUM_MISMATCH", "ERROR", f"Relationship '{rid}' records an IFC checksum that does not match the packaged IFC source.", rid, "source_ifc_checksum")
        if measurement_packaged and relationship.get("source_dataset_checksum") and relationship.get("source_dataset_checksum") != package.checksums.get(package.measurement_reference):
            add("RELATIONSHIP_DATASET_CHECKSUM_MISMATCH", "ERROR", f"Relationship '{rid}' records a dataset checksum that does not match the packaged acoustic source.", rid, "source_dataset_checksum")
        if not relationship.get("last_reviewed_at"):
            add("RELATIONSHIP_REVIEW_NOT_RECORDED", "INFO", f"Relationship '{rid}' has no recorded review date; no review is inferred.", rid, "last_reviewed_at")

    if not package.license:
        add("LICENCE_MISSING", "WARNING", f"Reuse metadata are incomplete because no licence or reuse-rights statement was provided for acoustic dataset {measurement_id or package.measurement_reference}.", package.package_id, "license")
    elif str(package.license).startswith(("http://", "https://", "urn:", "doi:")) and not valid_uri(str(package.license)):
        add("LICENCE_URI_INVALID", "ERROR", f"Licence URI '{package.license}' is syntactically invalid.", package.package_id, "license")
    if not package.provenance:
        add("PROVENANCE_MISSING", "WARNING", f"Provenance is missing for {package.package_id}; no creator, source, or generating activity is inferred.", package.package_id, "provenance")

    for key in ("access_url", "landing_page"):
        value = package.access_context.get(key)
        if value and not valid_uri(str(value)):
            add("ACCESS_URI_INVALID", "ERROR", f"Access metadata field '{key}' contains syntactically invalid URI '{value}'.", package.package_id, key)
    if package.dataset_uri and not valid_uri(package.dataset_uri):
        add("EXTERNAL_URI_INVALID", "ERROR", f"Acoustic dataset URI '{package.dataset_uri}' is syntactically invalid.", measurement_id or package.measurement_reference, "dataset_uri")
    elif package.dataset_uri:
        access_status = str(package.access_context.get("external_uri_status") or "NOT_TESTED").upper()
        if access_status in {"", "NOT_TESTED", "NOT_VERIFIED", "UNKNOWN"}:
            add("EXTERNAL_URI_NOT_VERIFIED", "INFO", f"External acoustic dataset URI '{package.dataset_uri}' is recorded but reachability has not been verified.", measurement_id or package.measurement_reference, "dataset_uri")
        elif access_status == "UNREACHABLE":
            add("EXTERNAL_RESOURCE_UNREACHABLE", "WARNING", f"External acoustic dataset URI '{package.dataset_uri}' is recorded as unreachable; metadata can remain available while data accessibility is impaired.", measurement_id or package.measurement_reference, "dataset_uri")

    completeness = package.metadata_completeness_assessment or {}
    for field_result in completeness.get("fields", []):
        if not field_result.get("applicable"):
            continue
        level = field_result.get("requirement_level")
        status = field_result.get("status")
        if level not in {"PROTOTYPE_REQUIRED", "CONDITIONALLY_REQUIRED"}:
            continue
        if status == "MISSING":
            add("METADATA_REQUIRED_MISSING", "ERROR", f"Required metadata field '{field_result.get('label')}' is missing for the current dataset/profile context. {field_result.get('recommendation') or ''}".strip(), package.package_id, field_result.get("field_name"))
        elif status == "INVALID":
            add("METADATA_VALUE_INVALID", "ERROR", f"Metadata field '{field_result.get('label')}' is invalid. {field_result.get('note') or ''}".strip(), package.package_id, field_result.get("field_name"))
        elif status in {"NOT_VERIFIED", "MANUAL_REVIEW"}:
            add("METADATA_REVIEW_INCOMPLETE", "WARNING", f"Metadata field '{field_result.get('label')}' requires verification or manual review: {field_result.get('note') or status}.", package.package_id, field_result.get("field_name"))

    issues.extend(validate_serializations(package))
    issues.extend(_validate_report_identity(package, "reports/metadata-completeness-assessment.json"))
    issues.extend(_validate_report_identity(package, "reports/fair-support-assessment.json", key="assessed_package_id"))
    issues.extend(_validate_report_identity(package, "reports/relationship-lifecycle-assessment.json"))
    issues.extend(_validate_report_identity(package, "evidence/relationship-evidence.json"))

    summary = {
        "errors": sum(item.severity == "ERROR" for item in issues),
        "warnings": sum(item.severity == "WARNING" for item in issues),
        "info": sum(item.severity == "INFO" for item in issues),
    }
    return {
        "validated_at": utc_now(),
        "package_id": package.package_id,
        "valid": summary["errors"] == 0,
        "summary": summary,
        "independent_outcomes": package.independent_outcomes,
        "issues": [item.to_dict() for item in issues],
    }
