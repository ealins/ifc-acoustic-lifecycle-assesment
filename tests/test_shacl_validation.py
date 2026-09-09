from fair_platform.export import finalize_package
from fair_platform.package_builder import FairPackageBuilder


def _package():
    return FairPackageBuilder().build(
        b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;",
        "geometry.ifc",
        b"<VaBDat><Rw>52</Rw></VaBDat>",
        "measurement.xml",
        ifc_global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        creator="Researcher",
        version="1.0.0",
        dataset_uri="https://example.org/dataset/1",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        provenance={"creator": "Researcher", "institution": "HFT Stuttgart"},
        measurement_context={
            "measurement_type": "Airborne sound insulation (Rw)",
            "measurement_method": "ISO 10140",
        },
        quality_information={"uncertainty": "1 dB"},
        metadata={"title": "Test acoustic package", "measurement_identifier": "LAB-001"},
    )


def test_generated_metadata_passes_shacl_profile():
    package = _package()
    report = package.metadata["shacl_validation"]
    assert report["available"] is True
    assert report["conforms"] is True
    assert report["violation_count"] == 0


def test_missing_globalid_is_reported_by_shacl():
    package = _package()
    package.ifc_global_id = None
    finalize_package(package)
    report = package.metadata["shacl_validation"]
    assert report["available"] is True
    assert report["conforms"] is False
    assert report["violation_count"] >= 1
    assert any("ifcGlobalId" in item.get("path", "") for item in report["results"])
