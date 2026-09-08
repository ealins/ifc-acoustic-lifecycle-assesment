from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from rdflib import Graph

from .models import FairAcousticPackage, FairAssessmentResult, FairCriterionResult, FairDimensionResult, FairStatus

STANDARD_MEASUREMENT_EXTENSIONS = {".xml", ".csv", ".json", ".txt", ".dat", ".h5", ".hdf5", ".vtk", ".ttl", ".rdf"}


def _has_text(value) -> bool:
    return value is not None and str(value).strip() != ""


def _identifier_like(value: str | None) -> bool:
    if not _has_text(value):
        return False
    text = str(value).strip()
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https", "urn"} or text.lower().startswith("doi:")


def _rdf_parseable(package: FairAcousticPackage) -> bool:
    data = package.assets.get(package.metadata_reference)
    if not data:
        return False
    fmt = "turtle" if package.metadata_reference.endswith(".ttl") else None
    try:
        Graph().parse(data=data.decode("utf-8"), format=fmt)
        return True
    except Exception:
        return False


def _criterion(key: str, label: str, passed: bool, evidence: str, remediation: str) -> FairCriterionResult:
    return FairCriterionResult(key=key, label=label, passed=bool(passed), evidence=evidence, remediation=remediation)


def assess_fair(package: FairAcousticPackage) -> FairAssessmentResult:
    searchable_fields = [
        package.metadata.get("title"),
        package.metadata.get("description"),
        package.metadata.get("keywords"),
        package.metadata.get("measurement_identifier"),
    ]
    searchable_metadata = any(_has_text(value) for value in searchable_fields)
    measurement_bytes = package.assets.get(package.measurement_reference, b"")
    metadata_bytes = package.assets.get(package.metadata_reference, b"")
    measurement_extension = Path(package.measurement_reference).suffix.lower()

    findable = FairDimensionResult("Findable", [
        _criterion(
            "persistent_identifier",
            "Persistent identifier",
            _identifier_like(package.identifier),
            package.identifier or "No package identifier",
            "Mint or provide an HTTP(S), URN or DOI-style persistent identifier for the package.",
        ),
        _criterion(
            "searchable_metadata",
            "Searchable descriptive metadata",
            searchable_metadata,
            "Title/description/keywords/measurement identifier present" if searchable_metadata else "No searchable descriptive field",
            "Add a title, description, keywords or a measurement identifier to the package metadata.",
        ),
        _criterion(
            "ifc_global_id",
            "IFC GlobalId",
            _has_text(package.ifc_global_id),
            package.ifc_global_id or "Missing",
            "Select an IFC component with a GlobalId or enter the GlobalId explicitly.",
        ),
    ])

    accessible = FairDimensionResult("Accessible", [
        _criterion(
            "dataset_uri",
            "Dataset access URI",
            _identifier_like(package.dataset_uri),
            package.dataset_uri or "Missing",
            "Provide a stable URI identifying the measurement dataset or its repository landing page.",
        ),
        _criterion(
            "measurement_exists",
            "Measurement included",
            bool(measurement_bytes),
            f"{len(measurement_bytes)} bytes in {package.measurement_reference}" if measurement_bytes else "Measurement asset missing",
            "Attach the acoustic measurement dataset to the package.",
        ),
        _criterion(
            "metadata_accessible",
            "Metadata included",
            bool(metadata_bytes),
            f"{len(metadata_bytes)} bytes in {package.metadata_reference}" if metadata_bytes else "Metadata asset missing",
            "Generate and include metadata.ttl in the package.",
        ),
    ])

    standard_representation = (
        package.geometry_reference.lower().endswith(".ifc")
        and package.metadata_reference.lower().endswith((".ttl", ".rdf", ".jsonld"))
        and measurement_extension in STANDARD_MEASUREMENT_EXTENSIONS
    )
    interoperable = FairDimensionResult("Interoperable", [
        _criterion(
            "ifc_linked",
            "IFC geometry linked",
            bool(package.assets.get(package.geometry_reference)) and _has_text(package.ifc_global_id),
            f"{package.geometry_reference} ↔ {package.ifc_global_id or 'missing GlobalId'}",
            "Include geometry.ifc and identify the component by IFC GlobalId.",
        ),
        _criterion(
            "rdf_linked",
            "RDF metadata parseable",
            _rdf_parseable(package),
            package.metadata_reference,
            "Generate standards-based RDF metadata in Turtle/RDF/JSON-LD and ensure it parses successfully.",
        ),
        _criterion(
            "standard_representations",
            "Standard representations",
            standard_representation,
            f"IFC + {measurement_extension or 'unknown measurement format'} + {Path(package.metadata_reference).suffix}",
            "Use IFC for geometry, RDF for metadata and a documented/open measurement representation.",
        ),
    ])

    provenance_present = any(_has_text(v) for v in package.provenance.values())
    quality_present = any(_has_text(v) for v in package.quality_information.values())
    context_present = _has_text(package.measurement_context.get("measurement_method")) and _has_text(package.measurement_context.get("measurement_type"))
    reusable = FairDimensionResult("Reusable", [
        _criterion(
            "provenance",
            "Provenance",
            provenance_present,
            str(package.provenance) if provenance_present else "Missing",
            "Document creator/institution and provenance of the measurement and geometry sources.",
        ),
        _criterion(
            "version",
            "Version",
            _has_text(package.version),
            package.version or "Missing",
            "Assign an explicit package version.",
        ),
        _criterion(
            "quality_information",
            "Quality and uncertainty information",
            quality_present,
            str(package.quality_information) if quality_present else "Missing",
            "Add uncertainty, calibration, quality-control or completeness information.",
        ),
        _criterion(
            "reuse_license",
            "Reuse license",
            _has_text(package.license),
            package.license or "Missing",
            "Declare a reuse license or rights statement.",
        ),
        _criterion(
            "measurement_context",
            "Measurement context",
            context_present,
            str(package.measurement_context) if package.measurement_context else "Missing",
            "Document at least measurement type and measurement method.",
        ),
    ])

    dimensions = [findable, accessible, interoperable, reusable]
    state_map = {
        "Findable": FairStatus.NOT_FINDABLE,
        "Accessible": FairStatus.NOT_ACCESSIBLE,
        "Interoperable": FairStatus.NOT_INTEROPERABLE,
        "Reusable": FairStatus.NOT_REUSABLE,
    }
    blocking_states = [state_map[d.name].value for d in dimensions if not d.passed]

    if all(d.passed for d in dimensions):
        overall = FairStatus.FAIR_READY
    else:
        zero_dimensions = [d for d in dimensions if d.score == 0]
        overall = state_map[zero_dimensions[0].name] if zero_dimensions else FairStatus.PARTIALLY_FAIR

    return FairAssessmentResult(findable, accessible, interoperable, reusable, overall, blocking_states)


def apply_assessment(package: FairAcousticPackage) -> FairAssessmentResult:
    result = assess_fair(package)
    package.fair_status = result.fair_status
    package.findable = result.findable.passed
    package.accessible = result.accessible.passed
    package.interoperable = result.interoperable.passed
    package.reusable = result.reusable.passed
    package.fair_assessment = result.to_dict()
    return result
