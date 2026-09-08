from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import FairAcousticPackage


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_manifest(package: FairAcousticPackage) -> dict[str, Any]:
    resources = {
        "geometry": {
            "path": package.geometry_reference,
            "media_type": "application/x-step",
            "ifc_global_id": package.ifc_global_id,
        },
        "measurement": {
            "path": package.measurement_reference,
            "media_type": package.metadata.get("measurement_media_type", "application/octet-stream"),
            "dataset_uri": package.dataset_uri,
        },
        "metadata": {
            "path": package.metadata_reference,
            "media_type": "text/turtle",
        },
    }

    checksums = {
        name: _sha256(content)
        for name, content in package.assets.items()
        if name != "manifest.json"
    }

    return {
        "package_id": package.package_id,
        "identifier": package.identifier,
        "creator": package.creator,
        "created": package.created,
        "version": package.version,
        "license": package.license,
        "resources": resources,
        "stewardship": {
            "mapping_series": package.mapping_series_uri,
            "latest_assertion": package.latest_mapping_assertion_uri,
            "lifecycle_status": package.lifecycle_status,
        },
        "fair": {
            "status": package.fair_status.value,
            "findable": package.findable,
            "accessible": package.accessible,
            "interoperable": package.interoperable,
            "reusable": package.reusable,
        },
        "checksums": checksums,
    }


def manifest_json(package: FairAcousticPackage) -> str:
    return json.dumps(build_manifest(package), indent=2, ensure_ascii=False)
