from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from .export import finalize_package
from .measurement import inspect_measurement
from .models import AcousticComponentResearchObject, FairAcousticPackage


def _safe_filename(value: str) -> str:
    name = Path(str(value or "resource.bin")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "resource.bin"


def _asset_record(path: str, source_name: str, role: str, payload: bytes, *, version: str | None = None) -> dict:
    return {
        "asset_id": f"asset:{path}",
        "path": path,
        "original_filename": Path(str(source_name)).name,
        "role": role,
        "media_type": mimetypes.guess_type(source_name)[0] or "application/octet-stream",
        "size_bytes": len(payload),
        "version": version,
        "packaged": True,
    }


def _add_research_assets(
    assets: dict[str, bytes],
    source_assets: dict[str, bytes] | None,
    prefix: str,
    role: str,
    *,
    version: str | None = None,
) -> list[dict]:
    records: list[dict] = []
    used: set[str] = set(assets)
    for source_name, payload in (source_assets or {}).items():
        base = _safe_filename(source_name)
        stem = Path(base).stem
        suffix = Path(base).suffix
        candidate = f"{prefix}/{base}"
        counter = 2
        while candidate in used:
            candidate = f"{prefix}/{stem}_{counter}{suffix}"
            counter += 1
        used.add(candidate)
        data = bytes(payload)
        assets[candidate] = data
        records.append(_asset_record(candidate, source_name, role, data, version=version))
    return records


class FairPackageBuilder:
    """Backward-compatible builder for the AcousticComponentResearchObject model.

    New research-object workflows should set ``research_object_layout=True`` so
    source assets are exported under ``geometry/`` and ``measurements/``. The
    legacy root layout remains available to preserve existing integrations/tests.
    No creator, institution, licence, persistent identifier, method, instrument,
    standard, or relationship evidence is fabricated when it was not supplied.
    """

    def build(
        self,
        geometry_bytes: bytes,
        geometry_filename: str,
        measurement_bytes: bytes,
        measurement_filename: str,
        *,
        ifc_global_id: str,
        creator: str,
        version: str,
        identifier: str | None = None,
        dataset_uri: str | None = None,
        license_uri: str | None = None,
        provenance: dict | None = None,
        measurement_context: dict | None = None,
        quality_information: dict | None = None,
        research_context: dict | None = None,
        simulation_context: dict | None = None,
        access_context: dict | None = None,
        relationships: list[dict] | None = None,
        simulation_assets: dict[str, bytes] | None = None,
        research_assets: dict[str, bytes] | None = None,
        metadata: dict | None = None,
        research_object_layout: bool = False,
    ) -> FairAcousticPackage:
        if not geometry_bytes:
            raise ValueError("IFC geometry is required")
        if not measurement_bytes:
            raise ValueError("A primary acoustic dataset is required")

        package_id = f"ACP-{uuid4().hex[:10].upper()}"
        geometry_name = _safe_filename(geometry_filename)
        measurement_name = _safe_filename(measurement_filename)
        measurement_suffix = Path(measurement_name).suffix.lower() or ".bin"
        if research_object_layout:
            geometry_reference = f"geometry/{geometry_name}"
            measurement_reference = f"measurements/{measurement_name}"
        else:
            geometry_reference = "geometry.ifc"
            measurement_reference = f"measurement{measurement_suffix}"

        context = dict(measurement_context or {})
        inspection = inspect_measurement(
            measurement_filename,
            bytes(measurement_bytes),
            declared_origin=context.get("origin_classification"),
        )
        media_type = mimetypes.guess_type(measurement_filename)[0] or "application/octet-stream"

        package_assets = {
            geometry_reference: bytes(geometry_bytes),
            measurement_reference: bytes(measurement_bytes),
        }
        asset_records = [
            _asset_record(geometry_reference, geometry_filename, "ifc-model", package_assets[geometry_reference], version=(metadata or {}).get("model_version")),
            _asset_record(measurement_reference, measurement_filename, "primary-acoustic-dataset", package_assets[measurement_reference], version=context.get("measurement_version")),
        ]
        asset_records.extend(_add_research_assets(package_assets, simulation_assets, "simulation", "simulation-artefact", version=(simulation_context or {}).get("software_version")))
        asset_records.extend(_add_research_assets(package_assets, research_assets, "research", "research-reproducibility-artefact", version=version))

        package_metadata = dict(metadata or {})
        package_metadata.update({
            "source_geometry_filename": geometry_filename,
            "source_measurement_filename": measurement_filename,
            "measurement_media_type": media_type,
            "measurement_inspection": inspection,
            "simulation_resources": [record for record in asset_records if record.get("role") == "simulation-artefact"],
            "research_resources": [record for record in asset_records if record.get("role") == "research-reproducibility-artefact"],
            "identifier_kind": "user-supplied" if identifier else "missing",
        })

        package = AcousticComponentResearchObject(
            package_id=package_id,
            geometry_reference=geometry_reference,
            measurement_reference=measurement_reference,
            metadata_reference="metadata.ttl",
            provenance=dict(provenance or {}),
            version=version,
            identifier=str(identifier or ""),
            creator=creator or None,
            license=license_uri or None,
            measurement_context=context,
            quality_information=dict(quality_information or {}),
            research_context=dict(research_context or {}),
            simulation_context=dict(simulation_context or {}),
            access_context=dict(access_context or {}),
            ifc_global_id=ifc_global_id or None,
            dataset_uri=dataset_uri or None,
            relationships=list(relationships or []),
            asset_records=asset_records,
            metadata=package_metadata,
            assets=package_assets,
        )
        finalize_package(package)
        return package
