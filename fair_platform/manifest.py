from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import FairAcousticPackage


def _media_type(package: FairAcousticPackage, path: str) -> str:
    record = next((item for item in package.asset_records if item.get("path") == path), None)
    if record and record.get("media_type"):
        return str(record["media_type"])
    if path == package.geometry_reference:
        return "application/x-step"
    if path == package.measurement_reference:
        return str(package.metadata.get("measurement_media_type") or "application/octet-stream")
    if path.endswith(".ttl"):
        return "text/turtle"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".txt"):
        return "text/plain"
    return "application/octet-stream"


def build_manifest(package: FairAcousticPackage) -> dict[str, Any]:
    asset_index: dict[str, Any] = {}
    records = {item.get("path"): item for item in package.asset_records if item.get("path")}
    for path, payload in sorted(package.assets.items()):
        record = records.get(path, {})
        asset_index[path] = {
            "path": path,
            "asset_id": record.get("asset_id") or f"asset:{path}",
            "role": record.get("role") or (
                "ifc-model" if path == package.geometry_reference
                else "primary-acoustic-dataset" if path == package.measurement_reference
                else "portable-metadata" if path == "ro-crate-metadata.json"
                else "domain-rdf" if path == package.metadata_reference
                else "application-manifest" if path == "manifest.json"
                else "assessment-report" if path.startswith("reports/")
                else "checksum-report" if path.startswith("checksums/")
                else "research-object-resource"
            ),
            "media_type": _media_type(package, path),
            "size_bytes": len(payload),
            "checksum": package.checksums.get(path),
            "original_filename": record.get("original_filename") or record.get("source_filename"),
            "version": record.get("version"),
            "packaged": True,
        }

    return {
        "schema": "https://example.org/fair-acoustic/manifest/v3",
        "object_type": package.object_type,
        "profile": package.research_object_profile,
        "metadata_authority": {
            "in_memory_domain_model": "authoritative application state",
            "ro-crate-metadata.json": "principal portable research-object representation",
            package.metadata_reference: "domain-specific RDF relationships, provenance and stewardship representation",
            "manifest.json": "simplified application/compatibility manifest derived from the in-memory model",
        },
        "package_id": package.package_id,
        "identifier": package.identifier or None,
        "title": package.title,
        "creator": package.creator,
        "created": package.created,
        "modified": package.modified,
        "version": package.version,
        "license": package.license,
        "access": package.access_context,
        "resources": {
            "geometry": asset_index.get(package.geometry_reference, {}),
            "measurement": {
                **asset_index.get(package.measurement_reference, {}),
                "dataset_uri": package.dataset_uri,
                "measurement_identifier": package.metadata.get("measurement_identifier"),
                "origin_classification": (package.metadata.get("measurement_inspection") or {}).get("origin_classification"),
                "inspection": package.metadata.get("measurement_inspection"),
            },
            "ro_crate_metadata": asset_index.get("ro-crate-metadata.json", {}),
            "domain_rdf": asset_index.get(package.metadata_reference, {}),
        },
        "asset_index": asset_index,
        "relationships": package.relationships,
        "research": {"context": package.research_context},
        "simulation": {"context": package.simulation_context},
        "fair_support": {
            "status": package.fair_support_status,
            "assessment": package.fair_support_assessment,
            "scope_note": "Selected prototype FAIR-support indicators; not a formal FAIR certification.",
        },
        "legacy_fair_compatibility": {
            "status": package.fair_status.value,
            "assessment": package.fair_assessment,
        },
        "stewardship": {
            "mapping_series": package.mapping_series_uri,
            "latest_assertion": package.latest_mapping_assertion_uri,
            "lifecycle_status": package.lifecycle_status,
            "revision_count": len(package.stewardship_history),
            "reassessment_triggers": package.reassessment_triggers,
        },
        "scientific_suitability": {
            "status": package.scientific_suitability_status,
            "scope_note": "Acoustic scientific validity/suitability is not inferred from FAIR or lifecycle metadata.",
        },
        "validation": {
            "package": package.validation_report,
            "shacl": package.metadata.get("shacl_validation", {}),
        },
        "checksums": package.checksums,
    }


def manifest_json(package: FairAcousticPackage) -> str:
    return json.dumps(build_manifest(package), indent=2, ensure_ascii=False)
