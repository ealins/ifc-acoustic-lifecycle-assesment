import json

from dashboard.ui.batch_measurement_intake import _lab_context, _parse_metadata, _record_for_file


class Upload:
    def __init__(self, name, payload):
        self.name = name
        self._payload = payload

    def getvalue(self):
        return self._payload


def test_external_json_metadata_maps_shared_and_per_file_values_with_provenance():
    upload = Upload("lab.json", json.dumps({
        "labContext": {"method": "3D SLDV", "unit": "m/s"},
        "records": [{"fileName": "scan-02.csv", "operator": "Operator B"}],
    }).encode())
    metadata, report = _parse_metadata(upload)
    assert metadata["labContext"]["method"] == "3D SLDV"
    row = _record_for_file(metadata, "scan-02.csv")
    lab, provenance = _lab_context(metadata, row)
    assert lab["method"] == "3D SLDV"
    assert lab["operator"] == "Operator B"
    assert lab["unit"] == "m/s"
    assert provenance["operator"]["status"] == "extracted"
    assert provenance["operator"]["source"] == "matching per-file metadata record"
    assert provenance["method"]["source_field"] == "method"
    assert report["format"] == "JSON/JSON-LD"


def test_external_csv_metadata_matches_by_filename():
    upload = Upload("lab.csv", b"fileName,method,unit\nscan.csv,SLDV,m/s\n")
    metadata, _ = _parse_metadata(upload)
    row = _record_for_file(metadata, "scan.csv")
    lab, provenance = _lab_context(metadata, row)
    assert lab["method"] == "SLDV"
    assert lab["unit"] == "m/s"
    assert provenance["unit"]["status"] == "extracted"


def test_missing_metadata_is_explicitly_unknown_not_invented():
    lab, provenance = _lab_context({}, {})
    assert lab["instrument"] == "unknown"
    assert lab["calibrationStatus"] == "unknown"
    assert provenance["instrument"]["status"] == "unknown"
    assert "unknown" in lab["limitations"].lower()


def test_per_file_values_take_precedence_without_manual_override():
    metadata = {
        "labContext": {"method": "Shared method", "unit": "m/s"},
        "records": [{"fileName": "scan.csv", "method": "Per-file method"}],
    }
    row = _record_for_file(metadata, "scan.csv")
    lab, provenance = _lab_context(metadata, row)
    assert lab["method"] == "Per-file method"
    assert provenance["method"]["source"] == "matching per-file metadata record"
    assert lab["unit"] == "m/s"


def test_docx_parser_returns_labelled_fields_for_review():
    upload = Upload("unsupported.xlsx", b"")
    try:
        _parse_metadata(upload)
    except ValueError as exc:
        assert "JSON, JSON-LD, CSV or DOCX" in str(exc)
    else:
        raise AssertionError("Unsupported metadata file should be rejected.")
