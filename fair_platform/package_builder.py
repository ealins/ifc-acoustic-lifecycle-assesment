from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from .export import finalize_package
from .measurement import inspect_measurement
from .models import FairAcousticPackage


def _safe_filename(value: str) -> str:
    name = Path(str(value or "resource.bin")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "resource.bin"


def _add_research_assets(
    assets: dict[str, bytes],
    source_assets: dict[str, bytes] | None,
    prefix: str,
    role: str,
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
        records.append(
            {
                "path": candidate,
                "source_filename": Path(str(source_name)).name,
                "role": role,
                "media_type": mimetypes.guess_type(base)[0] or "application/octet-stream",
                "size_bytes": len(data),
            }
        )
    return records


class FairPackageBuilder:
    """Build FAIR acoustic research objects without modifying source evidence bytes.

    The original geometry + primary acoustic dataset contract is preserved for
    lifecycle stewardship. Optional simulation and research artefacts extend the
    package into a reproducible research object without changing MappingSeries or
    MappingAssertion semantics.
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
        simulation_assets: dict[str, bytes] | None = None,
        research_assets: dict[str, bytes] | None = None,
        metadata: dict | None = None,
    ) -> FairAcousticPackage:
        if not geometry_bytes:
            raise ValueError("IFC geometry is required")
        if not measurement_bytes:
            raise ValueError("A primary acoustic dataset is required")

        package_id = f"FAP-{uuid4().hex[:10].upper()}"
        package_identifier = identifier or f"https://example.org/fair-acoustic/package/{package_id}"
        measurement_suffix = Path(measurement_filename).suffix.lower() or ".bin"
        measurement_reference = f"measurement{measurement_suffix}"
        media_type = mimetypes.guess_type(measurement_filename)[0] or "application/octet-stream"
        inspection = inspect_measurement(measurement_filename, bytes(measurement_bytes))

        package_assets = {
            "geometry.ifc": bytes(geometry_bytes),
            measurement_reference: bytes(measurement_bytes),
        }
        simulation_resources = _add_research_assets(
            package_assets, simulation_assets, "simulation", "simulation"
        )
        research_resources = _add_research_assets(
            package_assets, research_assets, "research", "research"
        )

        package_metadata = dict(metadata or {})
        package_metadata.update(
            {
                "source_geometry_filename": geometry_filename,
                "source_measurement_filename": measurement_filename,
                "measurement_media_type": media_type,
                "measurement_inspection": inspection,
                "simulation_resources": simulation_resources,
                "research_resources": research_resources,
            }
        )

        package = FairAcousticPackage(
            package_id=package_id,
            geometry_reference="geometry.ifc",
            measurement_reference=measurement_reference,
            metadata_reference="metadata.ttl",
            provenance=dict(provenance or {}),
            version=version,
            identifier=package_identifier,
            creator=creator or None,
            license=license_uri or None,
            measurement_context=dict(measurement_context or {}),
            quality_information=dict(quality_information or {}),
            research_context=dict(research_context or {}),
            simulation_context=dict(simulation_context or {}),
            ifc_global_id=ifc_global_id or None,
            dataset_uri=dataset_uri or None,
            metadata=package_metadata,
            assets=package_assets,
        )
        finalize_package(package)
        return package
