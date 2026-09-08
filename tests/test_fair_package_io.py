import json
from io import BytesIO
from zipfile import ZipFile

from fair_platform.export import export_fair_package
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.repository import PackageRepository


def build_package():
    return FairPackageBuilder().build(
        b"ISO-10303-21;",
        "source.ifc",
        b"<measurement />",
        "source.xml",
        ifc_global_id="gid-1",
        creator="Researcher",
        version="1.0.0",
        dataset_uri="https://example.org/dataset/1",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        provenance={"creator": "Researcher", "institution": "Lab"},
        measurement_context={"measurement_type": "Acoustic", "measurement_method": "Laboratory method"},
        quality_information={"uncertainty": "1 dB"},
        metadata={"title": "Wall dataset", "measurement_identifier": "M-1"},
    )


def test_zip_contains_canonical_resources():
    package = build_package()
    with ZipFile(BytesIO(export_fair_package(package))) as archive:
        names = set(archive.namelist())
        assert {"geometry.ifc", "measurement.xml", "metadata.ttl", "manifest.json"} <= names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["resources"]["geometry"]["ifc_global_id"] == "gid-1"
        assert manifest["checksums"]["geometry.ifc"].startswith("sha256:")


def test_repository_round_trip(tmp_path):
    repository = PackageRepository(tmp_path)
    package = build_package()
    repository.save(package)
    restored = repository.load(package.package_id)
    assert restored.package_id == package.package_id
    assert restored.assets["geometry.ifc"] == package.assets["geometry.ifc"]
    assert restored.metadata["measurement_identifier"] == "M-1"
