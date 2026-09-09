from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from rdflib import Graph

from .models import FairAcousticPackage, utc_now
from .research_object import MeasurementOrigin


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
        crate = json.loads(package.assets.get("ro-crate-metadata.json", b"").decode("utf-8"))
        if not isinstance(crate, dict) or "@context" not in crate or "@graph" not in crate:
            raise ValueError("JSON-LD object must contain @context and @graph")
    except Exception as exc:
        issues.append(ValidationIssue("JSONLD_INVALID", "ERROR", f"ro-crate-metadata.json is not valid structural JSON-LD: {exc}", "ro-crate-metadata.json"))
    return issues


def validate_research_object(package: FairAcousticPackage) -> dict[str, Any]:
    issues: list[ValidationIssue] = []

    def add(code: str, severity: str, message: str, entity: str, field: str | None = None) -> None:
        issues.append(ValidationIssue(code, severity, message, entity, field))

    if not package.package_id:
        add("PACKAGE_ID_MISSING", "ERROR", "Research object has no package identifier.", "research_object", "package_id")
    if not package.title.strip():
        add("PACKAGE_TITLE_MISSING", "ERROR", "Research object title is missing; no title was fabricated.", package.package_id, "title")
    if not package.ifc_global_id:
        add("IFC_GLOBALID_MISSING", "ERROR", "No selected IFC GlobalId is recorded for the component relationship.", package.package_id, "ifc_global_id")
    for required in (package.geometry_reference, package.measurement_reference):
        if required not in package.assets:
            add("PRIMARY_ASSET_MISSING", "ERROR", f"Required source asset '{required}' is missing from the package.", package.package_id, "assets")
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

    measurement_id = str(package.metadata.get("measurement_identifier") or "")
    if not measurement_id:
        add("MEASUREMENT_ID_MISSING", "ERROR", "Primary acoustic dataset has no explicit dataset identifier.", package.measurement_reference, "measurement_identifier")
    origin = str((package.metadata.get("measurement_inspection") or {}).get("origin_classification") or package.measurement_context.get("origin_classification") or MeasurementOrigin.UNKNOWN.value)
    if origin == MeasurementOrigin.UNKNOWN.value:
        add("MEASUREMENT_ORIGIN_UNKNOWN", "WARNING", "Acoustic dataset origin is unknown; origin was not inferred from file structure.", measurement_id or package.measurement_reference, "origin_classification")

    relationship_ids: set[str] = set()
    for relationship in package.relationships:
        rid = str(relationship.get("relationship_id") or "")
        if not rid:
            add("RELATIONSHIP_ID_MISSING", "ERROR", "A geometry-measurement relationship has no identifier.", package.package_id, "relationships")
            continue
        if rid in relationship_ids:
            add("RELATIONSHIP_ID_DUPLICATE", "ERROR", f"Relationship identifier '{rid}' occurs more than once.", rid, "relationship_id")
        relationship_ids.add(rid)
        if relationship.get("subject_ifc_global_id") != package.ifc_global_id:
            add("RELATIONSHIP_COMPONENT_UNKNOWN", "ERROR", f"Relationship '{rid}' does not reference the selected IFC GlobalId.", rid, "subject_ifc_global_id")
        if measurement_id and relationship.get("object_measurement_id") != measurement_id:
            add("RELATIONSHIP_MEASUREMENT_UNKNOWN", "ERROR", f"Relationship '{rid}' does not reference the package measurement identifier.", rid, "object_measurement_id")
        if not str(relationship.get("rationale") or "").strip():
            add("RELATIONSHIP_RATIONALE_MISSING", "ERROR", f"Relationship '{rid}' has no rationale.", rid, "rationale")
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
            if source_asset and source_asset not in package.assets and not valid_uri(str(source_asset)):
                add("EVIDENCE_SOURCE_UNKNOWN", "ERROR", f"Evidence '{eid}' references unknown source '{source_asset}'.", eid, "source_asset")
        if not relationship.get("last_reviewed_at"):
            add("RELATIONSHIP_REVIEW_NOT_RECORDED", "INFO", f"Relationship '{rid}' has no recorded review date.", rid, "last_reviewed_at")

    if not package.license:
        add("LICENCE_MISSING", "WARNING", f"Reusable metadata is incomplete because no licence or reuse statement was provided for {package.package_id}.", package.package_id, "license")
    if not package.provenance:
        add("PROVENANCE_MISSING", "WARNING", f"Provenance is missing for {package.package_id}.", package.package_id, "provenance")
    if package.dataset_uri and not valid_uri(package.dataset_uri):
        add("EXTERNAL_URI_INVALID", "ERROR", f"Measurement dataset URI '{package.dataset_uri}' is syntactically invalid.", measurement_id or package.measurement_reference, "dataset_uri")
    elif package.dataset_uri and str(package.access_context.get("external_uri_status") or "NOT_TESTED").upper() in {"", "NOT_TESTED", "NOT_VERIFIED"}:
        add("EXTERNAL_URI_NOT_VERIFIED", "INFO", f"External measurement URI '{package.dataset_uri}' is recorded but reachability has not been verified.", measurement_id or package.measurement_reference, "dataset_uri")

    issues.extend(validate_serializations(package))
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
        "issues": [item.to_dict() for item in issues],
    }
