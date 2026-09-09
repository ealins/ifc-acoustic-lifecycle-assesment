from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from .export import finalize_package
from .measurement import inspect_measurement
from .metadata_profile import PROFILE_ID as METADATA_PROFILE_ID, PROFILE_VERSION as METADATA_PROFILE_VERSION
from .models import AcousticComponentResearchObject, FairAcousticPackage
from .research_object import MeasurementOrigin


def _safe_filename(value: str) -> str:
    name = Path(str(value or "resource.bin")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "resource.bin"


def _asset_record(
    path: str,
    source_name: str,
    role: str,
    payload: bytes,
    *,
    version: str | None = None,
) -> dict:
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


def _external_asset_record(
    path: str,
    source_name: str,
    role: str,
    source_uri: str,
    *,
    version: str | None = None,
    access_context: dict | None = None,
) -> dict:
    access = dict(access_context or {})
    return {
        "asset_id": f"asset:{path}",
        "path": path,
        "original_filename": Path(str(source_name)).name,
        "role": role,
        "media_type": mimetypes.guess_type(source_name)[0] or "application/octet-stream",
        "size_bytes": None,
        "checksum": None,
        "version": version,
        "packaged": False,
        "source_uri": source_uri,
        "access_rights": access.get("access_rights"),
        "reachability_status": access.get("external_uri_status") or "NOT_TESTED",
        "last_check_time": access.get("external_uri_checked_at"),
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

    New workflows should set ``research_object_layout=True`` so source assets are
    exported under ``geometry/`` and ``measurements/``. A primary acoustic dataset
    may be packaged locally or represented as an external metadata-only reference.
    External resources that were not retrieved never receive fabricated byte sizes
    or checksums. No creator, institution, licence, PID, method, instrument,
    standard, uncertainty, provenance, or relationship evidence is fabricated.
    """

    def build(
        self,
        geometry_bytes: bytes,
        geometry_filename: str,
        measurement_bytes: bytes | None,
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
        additional_acoustic_assets: dict[str, bytes] | None = None,
        metadata: dict | None = None,
        research_object_layout: bool = False,
    ) -> FairAcousticPackage:
        if not geometry_bytes:
            raise ValueError("IFC geometry is required")
        if not measurement_bytes and not dataset_uri:
            raise ValueError("A primary acoustic dataset must be packaged or represented by an external URI")

        package_id = f"ACP-{uuid4().hex[:10].upper()}"
        geometry_name = _safe_filename(geometry_filename)
        measurement_name = _safe_filename(measurement_filename or "external-acoustic-dataset.bin")
        measurement_suffix = Path(measurement_name).suffix.lower() or ".bin"
        if research_object_layout:
            geometry_reference = f"geometry/{geometry_name}"
            measurement_reference = f"measurements/{measurement_name}"
        else:
            geometry_reference = "geometry.ifc"
            measurement_reference = f"measurement{measurement_suffix}"

        context = dict(measurement_context or {})
        access = dict(access_context or {})
        payload = bytes(measurement_bytes or b"")
        inspection = (
            inspect_measurement(
                measurement_filename,
                payload,
                declared_origin=context.get("origin_classification"),
            )
            if payload
            else {
                "format": "external-reference",
                "origin_classification": context.get("origin_classification") or MeasurementOrigin.UNKNOWN_ORIGIN.value,
                "inspection_scope": "metadata-only external reference; source bytes were not retrieved",
                "warnings": ["External acoustic bytes were not retrieved; content structure and checksum are not verified."],
            }
        )
        media_type = mimetypes.guess_type(measurement_filename)[0] or "application/octet-stream"

        package_assets = {geometry_reference: bytes(geometry_bytes)}
        geometry_record = _asset_record(
            geometry_reference,
            geometry_filename,
            "ifc-model",
            package_assets[geometry_reference],
            version=(metadata or {}).get("model_version"),
        )
        if payload:
            package_assets[measurement_reference] = payload
            measurement_record = _asset_record(
                measurement_reference,
                measurement_filename,
                "primary-acoustic-dataset",
                payload,
                version=context.get("measurement_version"),
            )
        else:
            measurement_record = _external_asset_record(
                measurement_reference,
                measurement_filename,
                "primary-acoustic-dataset",
                str(dataset_uri),
                version=context.get("measurement_version"),
                access_context=access,
            )

        asset_records = [geometry_record, measurement_record]
        related_records = _add_research_assets(
            package_assets,
            additional_acoustic_assets,
            "measurements",
            "related-acoustic-dataset",
            version=context.get("measurement_version"),
        )
        asset_records.extend(related_records)
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
            "metadata_profile": METADATA_PROFILE_ID,
            "metadata_profile_version": METADATA_PROFILE_VERSION,
            "ifc_asset_id": geometry_record["asset_id"],
            "geometry_media_type": geometry_record["media_type"],
        })

        dataset_id = package_metadata.get("measurement_identifier")
        acoustic_datasets = [{
            "dataset_id": dataset_id,
            "asset_id": measurement_record["asset_id"],
            "role": "primary-acoustic-dataset",
            "relative_path": measurement_reference if measurement_record.get("packaged") else None,
            "external_uri": dataset_uri if not measurement_record.get("packaged") or dataset_uri else None,
            "original_filename": measurement_record.get("original_filename"),
            "media_type": measurement_record.get("media_type"),
            "size_bytes": measurement_record.get("size_bytes"),
            "version": measurement_record.get("version"),
            "origin_classification": context.get("origin_classification") or inspection.get("origin_classification"),
            "packaged": bool(measurement_record.get("packaged")),
        }]
        for record in related_records:
            acoustic_datasets.append({
                "dataset_id": None,
                "asset_id": record.get("asset_id"),
                "role": record.get("role"),
                "relative_path": record.get("path"),
                "external_uri": None,
                "original_filename": record.get("original_filename"),
                "media_type": record.get("media_type"),
                "size_bytes": record.get("size_bytes"),
                "version": record.get("version"),
                "origin_classification": None,
                "packaged": True,
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
            access_context=access,
            ifc_global_id=ifc_global_id or None,
            dataset_uri=dataset_uri or None,
            metadata_profile=METADATA_PROFILE_ID,
            metadata_profile_version=METADATA_PROFILE_VERSION,
            acoustic_datasets=acoustic_datasets,
            relationships=list(relationships or []),
            asset_records=asset_records,
            metadata=package_metadata,
            assets=package_assets,
        )
        finalize_package(package)
        return package
