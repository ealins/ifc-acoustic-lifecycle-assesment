from fair_platform.assessment import assess_fair
from fair_platform.models import FairAcousticPackage, FairStatus


def complete_package():
    return FairAcousticPackage(
        package_id="FAP-TEST",
        geometry_reference="geometry.ifc",
        measurement_reference="measurement.xml",
        metadata_reference="metadata.ttl",
        provenance={"creator": "Researcher", "institution": "Lab"},
        version="1.0.0",
        identifier="https://example.org/package/FAP-TEST",
        creator="Researcher",
        license="https://creativecommons.org/licenses/by/4.0/",
        measurement_context={"measurement_type": "Airborne sound insulation", "measurement_method": "ISO 10140"},
        quality_information={"uncertainty": "1 dB"},
        ifc_global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        dataset_uri="https://example.org/dataset/1",
        metadata={"title": "Test component", "measurement_identifier": "M-1"},
        assets={
            "geometry.ifc": b"IFC",
            "measurement.xml": b"<m/>",
            "metadata.ttl": b"@prefix dct: <http://purl.org/dc/terms/> . <urn:x> dct:title \"x\" .",
        },
    )


def test_complete_package_is_fair_ready():
    result = assess_fair(complete_package())
    assert result.fair_status == FairStatus.FAIR_READY
    assert result.score == 1.0


def test_missing_reuse_metadata_is_partial():
    package = complete_package()
    package.provenance = {}
    package.quality_information = {}
    package.license = None
    result = assess_fair(package)
    assert result.fair_status == FairStatus.PARTIALLY_FAIR
    assert "NOT_REUSABLE" in result.blocking_states
    assert result.reusable.score < 1.0
