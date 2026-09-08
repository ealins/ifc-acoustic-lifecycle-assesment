from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from .assessment import apply_assessment
from .export import refresh_derived_assets
from .models import FairAcousticPackage


class FairPackageBuilder:
    """Create FAIR package aggregates without mutating source IFC or measurement data."""

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
        metadata: dict | None = None,
    ) -> FairAcousticPackage:
        package_id = f"FAP-{uuid4().hex[:10].upper()}"
        package_identifier = identifier or f"https://example.org/fair-acoustic/package/{package_id}"
        measurement_suffix = Path(measurement_filename).suffix.lower() or ".bin"
        measurement_reference = f"measurement{measurement_suffix}"
        media_type = mimetypes.guess_type(measurement_filename)[0] or "application/octet-stream"

        package_metadata = dict(metadata or {})
        package_metadata.update({
            "source_geometry_filename": geometry_filename,
            "source_measurement_filename": measurement_filename,
            "measurement_media_type": media_type,
        })

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
            ifc_global_id=ifc_global_id or None,
            dataset_uri=dataset_uri or None,
            metadata=package_metadata,
            assets={
                "geometry.ifc": geometry_bytes,
                measurement_reference: measurement_bytes,
            },
        )

        apply_assessment(package)
        refresh_derived_assets(package)
        return package
