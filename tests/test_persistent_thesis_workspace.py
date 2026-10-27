import io
import json
import zipfile

from dashboard.ui.persistent_thesis_workspace import CachedUpload, _make_bundle


def test_cached_upload_returns_original_bytes():
    payload = b"frequency;real;imag\r\n20;0.12;0.03\r\n"
    upload = CachedUpload("scan.csv", payload)
    assert upload.name == "scan.csv"
    assert upload.getvalue() == payload


def test_bundle_contains_source_bytes_sidecar_validation_and_viewer():
    original = b"frequency;real;imag\r\n20;0.12;0.03\r\n"
    sidecar = {"@context": {}, "@id": "urn:test", "sourceProvenance": {"measurement": {"sha256": "sha256:abc"}}}
    report = {
        "index": {"indexVersion": "1.1", "records": []},
        "validation_report": [{"recordIdentifier": "SLDV-001", "status": "PASS", "findings": []}],
        "metadata_report": {"status": "parsed"},
        "metadata": {"extractedFields": {"method": "3D SLDV"}},
        "ifc_name": "specimen.ifc",
        "ifc_bytes": b"ISO-10303-21;\nEND-ISO-10303-21;",
        "viewer_json": b'{"viewer":"blender","points":[]}',
        "records": [{
            "record_id": "SLDV-001", "filename": "scan.csv", "payload": original,
            "sidecar": sidecar, "validation": {"status": "PASS"},
        }],
    }
    bundle = _make_bundle(report)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        assert "measurements/scan.csv" in names
        assert "metadata/SLDV-001.jsonld" in names
        assert "reports/validation-report.json" in names
        assert "viewer/blender-viewer.json" in names
        assert "geometry/specimen.ifc" in names
        assert archive.read("measurements/scan.csv") == original
        assert json.loads(archive.read("metadata/SLDV-001.jsonld"))["sourceProvenance"]["measurement"]["sha256"] == "sha256:abc"
        assert json.loads(archive.read("manifest/index.json"))["indexVersion"] == "1.1"
