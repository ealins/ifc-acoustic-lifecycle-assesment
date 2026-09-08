from fair_platform.assessment import assess_fair
from fair_platform.models import FairAcousticPackage, FairStatus


def test_complete_package_is_fair_ready():
    package = FairAcousticPackage(
        package_id="FAP-TEST",
        geometry_reference="geometry.ifc",
        measurement_reference="measurement.xml",
        metadata_reference="metadata.ttl",
        provenance={"creator": "Researcher"},
        version="1.0.0",
        identifier="https://example.org/package/FAP-TEST",
        creator="Researcher",
        license="https://creativecommons.org/licenses/by/4.0/",
        measurement_context={"method": "ISO 10140"},
        quality_information={"uncertainty": "1 dB"},
        ifc_global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        dataset_uri="https://example.org/dataset/1",
        metadata={"title": "Test"},
        assets={"geometry.ifc": b"IFC", "measurement.xml": b"<m/>", "metadata.ttl": b"@prefix x: <x:> ."},
    )
    result = assess_fair(package)
    assert result.fair_status == FairStatus.FAIR_READY
    assert result.score == 1.0


def test_missing_reuse_metadata_is_partial():
    package = FairAcousticPackage(
        package_id="FAP-TEST",
        geometry_reference="geometry.ifc",
        measurement_reference="measurement.xml",
        metadata_reference="metadata.ttl",
        provenance={},
        version="1.0.0",
        identifier="https://example.org/package/FAP-TEST",
        ifc_global_id="gid",
        dataset_uri="https://example.org/dataset/1",
        metadata={"title": "Test"},
        assets={"geometry.ifc": b"IFC", "measurement.xml": b"<m/>", "metadata.ttl": b"x"},
    )
    result = assess_fair(package)
    assert result.fair_status == FairStatus.PARTIALLY_FAIR
    assert "NOT_REUSABLE" in result.blocking_states
