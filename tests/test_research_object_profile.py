from __future__ import annotations

from io import BytesIO
import hashlib
import json
from zipfile import ZipFile

import pytest
from rdflib import Graph

from dashboard.backend.ifc_parser import IFCExtractor
from fair_platform.catalog import MetadataCatalog
from fair_platform.export import export_research_object, refresh_derived_assets
from fair_platform.measurement import inspect_measurement
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.research_object import (
    EvidenceItem,
    EvidenceStatus,
    GeometryMeasurementRelationship,
    LifecycleStewardshipState,
    MeasurementOrigin,
    RelationshipType,
)
from fair_platform.triggers import detect_reassessment_triggers, relationship_source_snapshot
from fair_platform.validation import safe_relative_archive_path, validate_research_object


def _relationship(global_id: str = "2qL6OSUnz6ZAzEOn1HxeD2", measurement_id: str = "M-001") -> GeometryMeasurementRelationship:
    return GeometryMeasurementRelationship(
        subject_component_id=f"ifc:{global_id}",
        subject_ifc_global_id=global_id,
        subject_ifc_file_id="model.ifc",
        object_measurement_id=measurement_id,
        relationship_type=RelationshipType.MEASURED_ON,
        rationale="Laboratory report identifies the tested specimen as the selected IFC wall assembly.",
        evidence=[
            EvidenceItem(
                evidence_type="IFC GlobalId",
                comparison_result=EvidenceStatus.SUPPORTS,
                observed_value=global_id,
                expected_value=global_id,
                source_asset="model.ifc",
                source_location="selected component",
                reliability="direct source evidence",
            ),
            EvidenceItem(
                evidence_type="test report component identifier",
                comparison_result=EvidenceStatus.SUPPORTS,
                observed_value="SPEC-01",
                expected_value="SPEC-01",
                source_asset="measurement.xml",
                source_location="/VaBDat/SpecimenId",
                reliability="direct source evidence",
            ),
        ],
        matching_attributes=["specimen identifier", "material layers", "total thickness"],
        source_component_version="model-v1",
        source_measurement_version="measurement-v1",
        status=LifecycleStewardshipState.UNASSESSED,
    )


def complete_package(*, external_status: str = "REACHABLE"):
    relationship = _relationship()
    access_context = {"access_rights": "open", "external_uri_status": external_status}
    if external_status not in {"NOT_TESTED", "UNKNOWN", "NOT_VERIFIED"}:
        access_context["external_uri_checked_at"] = "2026-09-09T12:00:00Z"
    return FairPackageBuilder().build(
        b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;",
        "model.ifc",
        b"<VaBDat><SpecimenId>SPEC-01</SpecimenId><Rw unit='dB'>52</Rw></VaBDat>",
        "measurement.xml",
        ifc_global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        creator="Researcher",
        version="1.0.0",
        identifier="https://doi.org/10.9999/example.acoustic-object",
        dataset_uri="https://example.org/datasets/M-001",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        provenance={
            "original_source": "Laboratory source record M-001",
            "creator": "Researcher",
            "institution": "Acoustic Laboratory",
            "generating_activity": "Laboratory measurement and research-object assembly",
            "responsible_agent": "Researcher",
        },
        measurement_context={
            "measurement_type": "Airborne sound insulation (Rw)",
            "origin_classification": MeasurementOrigin.RAW_MEASUREMENT.value,
            "measurement_version": "measurement-v1",
            "measurement_method": "ISO 10140 laboratory method",
            "instrument": "Two-channel acoustic analyzer",
            "measurement_date": "2026-01-15",
            "measured_quantity": "weighted sound reduction index",
            "unit": "dB",
        },
        quality_information={
            "uncertainty": "±1 dB",
            "quality_notes": "Calibration checked before test.",
            "limitations": "Prototype fixture; acoustic suitability for a different assembly is not assessed.",
        },
        research_context={
            "intended_reuse": "Component-level comparison and reproducible method evaluation.",
            "citation": "Researcher (2026), Acoustic component research object M-001.",
        },
        access_context=access_context,
        relationships=[relationship.to_dict()],
        metadata={
            "title": "Measured airborne sound insulation of test wall",
            "description": "IFC-linked acoustic measurement research object for a laboratory wall specimen.",
            "keywords": ["IFC", "acoustics", "sound insulation"],
            "measurement_identifier": "M-001",
            "geometry_ifc_schema": "IFC4",
            "geometry_name": "Test Wall",
            "geometry_ifc_class": "IfcWall",
            "geometry_component_type": "Masonry wall",
            "geometry_materials": ["Brick", "Plaster"],
            "geometry_total_thickness_m": 0.24,
            "model_version": "model-v1",
        },
        research_object_layout=True,
    )


def test_domain_model_and_qualified_evidence_round_trip():
    relationship = _relationship()
    restored = GeometryMeasurementRelationship.from_dict(relationship.to_dict())
    assert restored.relationship_type is RelationshipType.MEASURED_ON
    assert restored.evidence[0].comparison_result is EvidenceStatus.SUPPORTS
    assert restored.evidence_summary()["SUPPORTS"] == 2


def test_measurement_origin_is_explicit_not_inferred():
    unknown = inspect_measurement("measurement.xml", b"<VaBDat><Rw>52</Rw></VaBDat>")
    declared = inspect_measurement(
        "measurement.xml",
        b"<VaBDat><Rw>52</Rw></VaBDat>",
        declared_origin=MeasurementOrigin.PROCESSED_MEASUREMENT.value,
    )
    assert unknown["origin_classification"] == MeasurementOrigin.UNKNOWN.value
    assert declared["origin_classification"] == MeasurementOrigin.PROCESSED_MEASUREMENT.value
    assert declared["origin_basis"] == "user-declared"


def test_ro_crate_turtle_manifest_and_zip_are_consistent():
    package = complete_package()
    archive_bytes = export_research_object(package, strict=True)
    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        required = {
            "ro-crate-metadata.json",
            "metadata.ttl",
            "manifest.json",
            "geometry/model.ifc",
            "measurements/measurement.xml",
            "reports/fair-assessment.json",
            "reports/lifecycle-assessment.json",
            "reports/relationship-evidence.json",
            "reports/package-validation.json",
            "checksums/sha256sums.txt",
            "README.txt",
        }
        assert required <= names
        crate = json.loads(archive.read("ro-crate-metadata.json"))
        assert "@context" in crate and "@graph" in crate
        assert any(node.get("@type") == "fairac:GeometryMeasurementRelationship" for node in crate["@graph"])
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["package_id"] == package.package_id
        assert manifest["research_object"]["profile"] == package.research_object_profile
        Graph().parse(data=archive.read("metadata.ttl").decode("utf-8"), format="turtle")
        Graph().parse(data=archive.read("ro-crate-metadata.json").decode("utf-8"), format="json-ld")


def test_all_declared_checksums_match_bytes():
    package = complete_package()
    for path, expected in package.checksums.items():
        actual = "sha256:" + hashlib.sha256(package.assets[path]).hexdigest()
        assert actual == expected, path


def test_archive_path_safety():
    assert safe_relative_archive_path("geometry/model.ifc")
    assert safe_relative_archive_path("reports/fair-assessment.json")
    assert not safe_relative_archive_path("../secret.txt")
    assert not safe_relative_archive_path("geometry/../../secret.txt")
    assert not safe_relative_archive_path("/absolute/file")


def test_fair_support_pass_partial_not_verified_and_manual_review():
    package = complete_package()
    assert package.fair_support_status == "READY_FOR_PROTOTYPE_REUSE"
    statuses = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert statuses["F1"] == "PASS"
    assert statuses["I3"] == "PASS"
    assert statuses["R10"] == "PASS"

    package.quality_information = {}
    refresh_derived_assets(package)
    statuses = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert statuses["R8"] == "PARTIAL"
    assert package.fair_support_status == "PARTIALLY_READY"

    package = complete_package(external_status="NOT_TESTED")
    statuses = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert statuses["A3"] == "NOT_VERIFIED"

    package.metadata["ids_specification_reference"] = "local-prototype.ids"
    refresh_derived_assets(package)
    statuses = {item["criterion_id"]: item["status"] for item in package.fair_support_assessment["criteria"]}
    assert statuses["I8"] == "MANUAL_REVIEW"


def test_fair_support_and_lifecycle_are_independent():
    package = complete_package()
    package.lifecycle_status = "SEMANTICALLY_STALE"
    refresh_derived_assets(package)
    assert package.fair_support_status == "READY_FOR_PROTOTYPE_REUSE"
    assert package.lifecycle_display_status == "STALE"
    assert package.scientific_suitability_status == "NOT_ASSESSED"


def test_no_fabricated_descriptive_or_rights_metadata():
    package = FairPackageBuilder().build(
        b"IFC",
        "model.ifc",
        b"<m/>",
        "measurement.xml",
        ifc_global_id="gid-1",
        creator="",
        version="1.0.0",
        identifier=None,
        dataset_uri=None,
        license_uri=None,
        provenance={},
        measurement_context={"origin_classification": MeasurementOrigin.UNKNOWN.value},
        metadata={"measurement_identifier": "M-X", "geometry_ifc_schema": "IFC4"},
        relationships=[],
        research_object_layout=True,
    )
    assert package.identifier == ""
    assert package.creator is None
    assert package.license is None
    assert "title" not in package.metadata
    codes = {item["code"] for item in package.validation_report["issues"]}
    assert "PACKAGE_TITLE_MISSING" in codes
    assert "LICENCE_MISSING" in codes


def test_relationship_reassessment_triggers_are_typed_and_selective():
    package = complete_package()
    before = relationship_source_snapshot(package)
    after = dict(before)
    after["measurement_version"] = "measurement-v2"
    after["license"] = "https://creativecommons.org/licenses/by-sa/4.0/"
    triggers = detect_reassessment_triggers(before, after)
    by_type = {item.trigger_type: item for item in triggers}
    assert by_type["Measurement version changed"].resulting_state is LifecycleStewardshipState.MANUAL_REVIEW
    assert by_type["Licence/reuse terms changed"].resulting_state is LifecycleStewardshipState.ACCEPTABLE
    assert by_type["Licence/reuse terms changed"].category.value == "access_change"


def test_changed_ifc_evidence_requests_staleness():
    package = complete_package()
    before = relationship_source_snapshot(package)
    after = dict(before)
    after["thickness_m"] = 0.30
    triggers = detect_reassessment_triggers(before, after)
    assert len(triggers) == 1
    assert triggers[0].resulting_state is LifecycleStewardshipState.SEMANTICALLY_STALE
    assert triggers[0].category.value == "component_semantic_change"


def test_catalog_searches_profile_relationship_and_ifc_fields():
    package = complete_package()
    catalog = MetadataCatalog([package])
    assert catalog.search("Test Wall") == [package]
    assert catalog.search("measuredOn") == [package]
    assert catalog.search(ifc_type="IfcWall") == [package]
    assert catalog.search(relationship_type="measuredOn") == [package]
    assert catalog.search(fair_support_status="READY_FOR_PROTOTYPE_REUSE") == [package]


def test_validation_detects_wrong_relationship_target():
    package = complete_package()
    package.relationships[0]["object_measurement_id"] = "OTHER"
    refresh_derived_assets(package)
    codes = {item["code"] for item in package.validation_report["issues"]}
    assert "RELATIONSHIP_MEASUREMENT_UNKNOWN" in codes


def test_ifc_globalid_resolution_with_ifcopenshell(tmp_path):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    model = ifcopenshell.file(schema="IFC4")
    guid = ifcopenshell.guid.new()
    model.create_entity("IfcWall", GlobalId=guid, Name="Resolvable Test Wall")
    path = tmp_path / "component.ifc"
    model.write(str(path))
    extractor = IFCExtractor()
    resolved = extractor.resolve_global_id(path, guid)
    assert resolved["resolved"] is True
    assert resolved["global_id"] == guid
    assert resolved["ifc_class"] == "IfcWall"
    missing = extractor.resolve_global_id(path, "0000000000000000000000")
    assert missing["resolved"] is False
