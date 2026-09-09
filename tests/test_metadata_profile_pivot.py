from __future__ import annotations

from io import BytesIO
import hashlib
import json
from zipfile import ZipFile

from rdflib import Graph

from fair_platform.catalog import MetadataCatalog
from fair_platform.completeness import MetadataCompletenessStatus, MetadataFieldStatus
from fair_platform.export import export_research_object, refresh_derived_assets
from fair_platform.metadata_profile import MetadataCategory, PROFILE_FIELDS, PROFILE_VERSION, RequirementLevel, profile_as_dict
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.research_object import (
    EvidenceItem,
    EvidenceStatus,
    GeometryMeasurementRelationship,
    LifecycleStewardshipState,
    MeasurementOrigin,
    RelationshipType,
    relationship_type_allowed_for_origin,
)
from fair_platform.triggers import detect_reassessment_triggers, relationship_source_snapshot
from fair_platform.validation import validate_package_id_uniqueness


GID = "2qL6OSUnz6ZAzEOn1HxeD2"


def _relationship(origin: MeasurementOrigin = MeasurementOrigin.RAW_MEASUREMENT, relationship_type: RelationshipType | None = None):
    if relationship_type is None:
        relationship_type = RelationshipType.MEASURED_ON if origin in {MeasurementOrigin.RAW_MEASUREMENT, MeasurementOrigin.PROCESSED_MEASUREMENT} else RelationshipType.REFERENCES
    return GeometryMeasurementRelationship(
        subject_component_id=f"ifc:{GID}",
        subject_ifc_global_id=GID,
        subject_ifc_file_id="model.ifc",
        object_measurement_id="M01",
        relationship_type=relationship_type,
        scope="component",
        rationale="The source record explicitly identifies the selected component/specimen for this prototype evaluation case.",
        evidence=[
            EvidenceItem(
                evidence_type="source component identifier",
                comparison_result=EvidenceStatus.SUPPORTS,
                observed_value="SPEC-01",
                expected_value="SPEC-01",
                source_asset="measurement.xml",
                source_location="/record/specimen",
                reliability="direct source evidence",
            )
        ],
        created_by="Researcher",
        relationship_version="1.0.0",
        source_component_version="model-v1",
        source_measurement_version="data-v1",
    )


def _package(
    *,
    origin: MeasurementOrigin = MeasurementOrigin.RAW_MEASUREMENT,
    relationship_type: RelationshipType | None = None,
    include_license: bool = True,
    include_method: bool = True,
    external: bool = False,
    external_status: str = "REACHABLE",
):
    relationship = _relationship(origin, relationship_type)
    measurement_bytes = None if external else b"<record><specimen>SPEC-01</specimen><value unit='dB'>52</value></record>"
    method_fields = {
        "measurement_method": "documented laboratory measurement method",
        "instrument": "documented acquisition system",
        "measurement_date": "2026-01-15",
    } if include_method and origin in {MeasurementOrigin.RAW_MEASUREMENT, MeasurementOrigin.PROCESSED_MEASUREMENT} else {}
    simulation_context = {"software": "documented external solver", "software_version": "1.0"} if origin in {MeasurementOrigin.SIMULATION_RESULT, MeasurementOrigin.PREDICTED_VALUE} else {}
    manufacturer_fields = {"manufacturer": "documented manufacturer"} if origin == MeasurementOrigin.MANUFACTURER_VALUE else {}
    return FairPackageBuilder().build(
        b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;",
        "model.ifc",
        measurement_bytes,
        "measurement.xml",
        ifc_global_id=GID,
        creator="Researcher",
        version="1.0.0",
        identifier="https://doi.org/10.9999/example.metadata-profile",
        dataset_uri="https://data.example.org/M01" if external else None,
        license_uri="https://creativecommons.org/licenses/by/4.0/" if include_license else None,
        provenance={
            "original_source": "Documented source record M01",
            "creator": "Researcher",
            "generating_activity": "Documented source-data generation activity",
            "responsible_agent": "Researcher",
        },
        measurement_context={
            "measurement_type": "Airborne sound insulation",
            "origin_classification": origin.value,
            "measurement_version": "data-v1",
            "measured_quantity": "sound reduction index",
            "unit": "dB",
            **method_fields,
            **manufacturer_fields,
        },
        simulation_context=simulation_context,
        quality_information={
            "limitations": "Prototype record; scientific suitability for another component is not assessed.",
            "quality_notes": "Source quality statement retained as supplied.",
        },
        research_context={
            "intended_reuse": "Metadata/profile and component-dataset traceability evaluation.",
            "preferred_citation": "Researcher (2026), prototype acoustic component record.",
        },
        access_context={
            "access_rights": "open",
            "access_url": "https://data.example.org/M01" if external else None,
            "external_uri_status": external_status if external else "NOT_TESTED",
            "external_uri_checked_at": "2026-09-09T12:00:00Z" if external and external_status != "NOT_TESTED" else None,
        },
        relationships=[relationship.to_dict()],
        metadata={
            "title": "Prototype acoustic component dataset M01",
            "description": "Metadata-complete evaluation fixture for the selected IFC/acoustic use case.",
            "keywords": ["IFC", "acoustics", "metadata"],
            "metadata_language": "en",
            "measurement_identifier": "M01",
            "geometry_ifc_schema": "IFC4",
            "geometry_name": "Test component",
            "geometry_ifc_class": "IfcWall",
            "model_version": "model-v1",
        },
        research_object_layout=True,
    )


def _field(package, name: str) -> dict:
    return next(item for item in package.metadata_completeness_assessment["fields"] if item["field_name"] == name)


def test_metadata_profile_is_machine_readable_and_complete_as_a_definition():
    profile = profile_as_dict()
    assert profile["version"] == PROFILE_VERSION
    assert profile["label"] == "Prototype FAIR-Oriented Acoustic Component Metadata Profile"
    assert set(profile["requirement_levels"]) == {item.value for item in RequirementLevel}
    assert set(profile["categories"]) == {item.value for item in MetadataCategory}
    assert len(profile["fields"]) == len(PROFILE_FIELDS)
    required_keys = {
        "field_name", "label", "definition", "purpose", "data_type", "permitted_value_type",
        "cardinality", "requirement_level", "conditional_requirement", "source_of_value",
        "acquisition", "validation_rule", "example", "fair_dimension", "rdm_role",
        "relationship_assessment_role", "mapped_vocabulary", "limitation",
    }
    assert all(required_keys <= set(field) for field in profile["fields"])


def test_complete_prototype_record_reports_independent_outcomes():
    package = _package()
    assert package.metadata_completeness_status == MetadataCompletenessStatus.COMPLETE_FOR_PROTOTYPE.value
    assert package.scientific_suitability_status == "NOT_ASSESSED"
    outcomes = package.independent_outcomes
    assert outcomes["metadata_completeness"] == "COMPLETE_FOR_PROTOTYPE"
    assert outcomes["fair_support"] == package.fair_support_status
    assert outcomes["relationship_lifecycle"] == package.lifecycle_display_status
    assert outcomes["acoustic_scientific_suitability"] == "NOT_ASSESSED"


def test_missing_licence_is_independent_from_relationship_semantics():
    package = _package(include_license=False)
    assert package.metadata_completeness_status == MetadataCompletenessStatus.INSUFFICIENT_FOR_REUSE.value
    assert _field(package, "licence")["status"] == MetadataFieldStatus.MISSING.value
    fair = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert fair["R7"] == "FAIL"
    assert package.relationships[0]["relationship_type"] == RelationshipType.MEASURED_ON.value


def test_missing_measurement_method_fails_active_conditional_requirement():
    package = _package(include_method=False)
    assert package.metadata_completeness_status == MetadataCompletenessStatus.INSUFFICIENT_FOR_INTERPRETATION.value
    assert _field(package, "measurement_method")["status"] == MetadataFieldStatus.MISSING.value
    assert _field(package, "instrument")["status"] == MetadataFieldStatus.MISSING.value


def test_catalog_record_cannot_be_claimed_as_direct_measurement():
    allowed, reason = relationship_type_allowed_for_origin(MeasurementOrigin.CATALOG_RECORD, RelationshipType.MEASURED_ON)
    assert not allowed
    assert "MEASURED_ON" in reason
    package = _package(origin=MeasurementOrigin.CATALOG_RECORD, relationship_type=RelationshipType.MEASURED_ON)
    codes = {item["code"] for item in package.validation_report["issues"]}
    assert "RELATIONSHIP_TYPE_INCOMPATIBLE" in codes
    assert _field(package, "relationship_type")["status"] == MetadataFieldStatus.INVALID.value


def test_catalog_record_with_reference_relationship_keeps_measurement_fields_not_applicable():
    package = _package(origin=MeasurementOrigin.CATALOG_RECORD, relationship_type=RelationshipType.REFERENCES)
    assert _field(package, "measurement_method")["status"] == MetadataFieldStatus.NOT_APPLICABLE.value
    assert _field(package, "instrument")["status"] == MetadataFieldStatus.NOT_APPLICABLE.value


def test_external_metadata_only_resource_has_no_fabricated_size_or_checksum():
    package = _package(external=True)
    record = next(item for item in package.asset_records if item["role"] == "primary-acoustic-dataset")
    assert record["packaged"] is False
    assert record["size_bytes"] is None
    assert record["checksum"] is None
    assert package.measurement_reference not in package.checksums
    assert _field(package, "dataset_checksum")["status"] == MetadataFieldStatus.NOT_APPLICABLE.value
    assert _field(package, "dataset_byte_size")["status"] == MetadataFieldStatus.NOT_APPLICABLE.value
    assert _field(package, "dataset_external_uri")["status"] == MetadataFieldStatus.PRESENT.value


def test_external_uri_string_without_check_is_not_verified_accessibility():
    package = _package(external=True, external_status="NOT_TESTED")
    fair = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert fair["A3"] == "NOT_VERIFIED"
    assert _field(package, "access_status")["status"] == MetadataFieldStatus.NOT_VERIFIED.value


def test_ifc_change_trigger_can_make_relationship_semantically_stale_without_changing_metadata_result():
    package = _package()
    before = relationship_source_snapshot(package)
    after = dict(before)
    after["thickness_m"] = 0.31
    triggers = detect_reassessment_triggers(before, after)
    assert len(triggers) == 1
    assert triggers[0].resulting_state is LifecycleStewardshipState.SEMANTICALLY_STALE
    assert package.metadata_completeness_status == MetadataCompletenessStatus.COMPLETE_FOR_PROTOTYPE.value


def test_missing_external_resource_trigger_is_broken():
    package = _package(external=True)
    before = relationship_source_snapshot(package)
    after = dict(before)
    after["resource_status"] = "UNREACHABLE"
    trigger = detect_reassessment_triggers(before, after)[0]
    assert trigger.resulting_state is LifecycleStewardshipState.BROKEN


def test_multiple_candidate_trigger_requires_explicit_review():
    package = _package()
    before = relationship_source_snapshot(package)
    after = dict(before)
    after["candidate_set"] = ["M01", "M02"]
    trigger = detect_reassessment_triggers(before, after)[0]
    assert trigger.resulting_state is LifecycleStewardshipState.MULTIPLE_CANDIDATES
    assert "do not silently select" in trigger.recommended_action.lower()


def test_invalid_relationship_outcome_does_not_erase_metadata_completeness():
    package = _package()
    package.lifecycle_status = "INVALID"
    refresh_derived_assets(package)
    assert package.metadata_completeness_status == MetadataCompletenessStatus.COMPLETE_FOR_PROTOTYPE.value
    assert package.lifecycle_display_status == "INVALID"


def test_export_contains_profile_assessments_evidence_and_integrity_files():
    package = _package()
    archive_bytes = export_research_object(package, strict=True)
    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        required = {
            "ro-crate-metadata.json",
            "metadata.ttl",
            "manifest.json",
            "profiles/acoustic-metadata-profile.json",
            "geometry/model.ifc",
            "measurements/measurement.xml",
            "evidence/relationship-evidence.json",
            "reports/metadata-completeness-assessment.json",
            "reports/fair-support-assessment.json",
            "reports/relationship-lifecycle-assessment.json",
            "reports/package-validation.json",
            "checksums/sha256sums.txt",
            "README.txt",
        }
        assert required <= names
        completeness = json.loads(archive.read("reports/metadata-completeness-assessment.json"))
        fair = json.loads(archive.read("reports/fair-support-assessment.json"))
        lifecycle = json.loads(archive.read("reports/relationship-lifecycle-assessment.json"))
        assert completeness["package_id"] == package.package_id
        assert fair["assessed_package_id"] == package.package_id
        assert lifecycle["package_id"] == package.package_id
        Graph().parse(data=archive.read("metadata.ttl").decode(), format="turtle")
        Graph().parse(data=archive.read("ro-crate-metadata.json").decode(), format="json-ld")
        checksum_rows = archive.read("checksums/sha256sums.txt").decode().splitlines()
        for row in checksum_rows:
            expected, path = row.split("  ", 1)
            assert hashlib.sha256(archive.read(path)).hexdigest() == expected


def test_component_library_filters_metadata_origin_and_lifecycle():
    package = _package()
    package.lifecycle_status = "ACCEPTABLE"
    catalog = MetadataCatalog([package])
    assert catalog.search(metadata_completeness="COMPLETE_FOR_PROTOTYPE") == [package]
    assert catalog.search(dataset_origin=MeasurementOrigin.RAW_MEASUREMENT.value) == [package]
    assert catalog.search(lifecycle_status="ACCEPTABLE") == [package]
    entry = catalog.entry(package)
    assert entry["acoustic_dataset_identifier"] == "M01"
    assert entry["metadata_completeness"] == "COMPLETE_FOR_PROTOTYPE"


def test_local_package_identity_is_not_fabricated_as_repository_pid():
    package = _package()
    package.identifier = ""
    refresh_derived_assets(package)
    assert package.package_id.startswith("ACP-")
    assert _field(package, "package_identifier")["status"] == MetadataFieldStatus.PRESENT.value
    fair = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert fair["F2"] != "PASS"


def test_duplicate_package_ids_are_detected_at_library_scope():
    first = _package()
    second = _package()
    second.package_id = first.package_id
    issues = validate_package_id_uniqueness([first, second])
    assert any(item.code == "PACKAGE_ID_DUPLICATE" for item in issues)
