from __future__ import annotations

import json
from typing import Any

from .models import FairAcousticPackage


def build_manifest(package: FairAcousticPackage) -> dict[str, Any]:
    def resource(path: str, media_type: str, **extra) -> dict[str, Any]:
        payload = package.assets.get(path, b"")
        return {
            "path": path,
            "media_type": media_type,
            "size_bytes": len(payload),
            "checksum": package.checksums.get(path),
            **extra,
        }

    return {
        "schema": "https://example.org/fair-acoustic/manifest/v1",
        "package_id": package.package_id,
        "identifier": package.identifier,
        "title": package.title,
        "creator": package.creator,
        "created": package.created,
        "version": package.version,
        "license": package.license,
        "resources": {
            "geometry": resource(
                package.geometry_reference,
                "application/x-step",
                ifc_global_id=package.ifc_global_id,
                source_filename=package.metadata.get("source_geometry_filename"),
            ),
            "measurement": resource(
                package.measurement_reference,
                package.metadata.get("measurement_media_type", "application/octet-stream"),
                dataset_uri=package.dataset_uri,
                measurement_identifier=package.metadata.get("measurement_identifier"),
                source_filename=package.metadata.get("source_measurement_filename"),
            ),
            "metadata": resource(package.metadata_reference, "text/turtle"),
        },
        "fair": {
            "status": package.fair_status.value,
            "score": package.fair_assessment.get("score"),
            "findable": package.findable,
            "accessible": package.accessible,
            "interoperable": package.interoperable,
            "reusable": package.reusable,
            "assessment": package.fair_assessment,
        },
        "stewardship": {
            "mapping_series": package.mapping_series_uri,
            "latest_assertion": package.latest_mapping_assertion_uri,
            "lifecycle_status": package.lifecycle_display_status,
            "engine_status": package.lifecycle_status,
            "revision_count": len(package.stewardship_history),
        },
        "checksums": package.checksums,
    }


def manifest_json(package: FairAcousticPackage) -> str:
    return json.dumps(build_manifest(package), indent=2, ensure_ascii=False)
