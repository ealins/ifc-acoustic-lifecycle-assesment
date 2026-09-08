from fair_platform.package_builder import FairPackageBuilder
from fair_platform.stewardship import FairStewardshipService


def test_generic_stewardship_creates_revision_then_deduplicates():
    package = FairPackageBuilder().build(
        b"ISO-10303-21;", "wall.ifc", b"measurement", "measurement.csv",
        ifc_global_id="gid-1", creator="Researcher", version="1.0.0",
        dataset_uri="https://example.org/dataset/1",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        provenance={"creator": "Researcher", "institution": "Lab"},
        measurement_context={
            "measurement_type": "Vibration dataset",
            "stewardship_profile": "GENERIC_ACOUSTIC_MEASUREMENT",
            "measurement_method": "Modal test",
            "assembly": "Wall A",
            "construction_family": "Masonry Wall",
            "total_thickness_m": 0.2,
        },
        quality_information={"uncertainty": "documented"},
        metadata={
            "title": "Vibration wall package",
            "measurement_identifier": "V-1",
            "geometry_name": "Wall A",
            "geometry_construction_family": "Masonry Wall",
            "geometry_total_thickness_m": 0.2,
            "geometry_materials": ["Brick"],
            "model_version": "ifc-v1",
        },
    )
    service = FairStewardshipService()
    first = service.assess(package)
    assert first.created_revision is True
    assert package.mapping_series_uri
    assert package.latest_mapping_assertion_uri
    assert len(package.stewardship_history) == 1

    second = service.assess(package)
    assert second.created_revision is False
    assert len(package.stewardship_history) == 1
