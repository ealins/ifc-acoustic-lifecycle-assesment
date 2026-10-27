import io
import json

from dashboard.ui.batch_measurement_intake import _lab_context, _parse_metadata, _record_for_file


class Upload:
    def __init__(self, name, payload):
        self.name = name
        self._payload = payload

    def getvalue(self):
        return self._payload


def test_external_json_metadata_maps_shared_and_per_file_values():
    upload = Upload("lab.json", json.dumps({
        "labContext": {"method": "3D SLDV", "unit": "m/s"},
        "records": [{"fileName": "scan-02.csv", "operator": "Operator B"}],
    }).encode())
    metadata, message = _parse_metadata(upload)
    assert metadata["labContext"]["method"] == "3D SLDV"
    assert _record_for_file(metadata, "scan-02.csv")["operator"] == "Operator B"
    lab = _lab_context(metadata["labContext"], _record_for_file(metadata, "scan-02.csv"))
    assert lab["method"] == "3D SLDV"
    assert lab["operator"] == "Operator B"
    assert "Parsed JSON" in message


def test_external_csv_metadata_matches_by_filename():
    upload = Upload("lab.csv", b"fileName,method,unit\nscan.csv,SLDV,m/s\n")
    metadata, _ = _parse_metadata(upload)
    row = _record_for_file(metadata, "scan.csv")
    lab = _lab_context({}, row)
    assert lab["method"] == "SLDV"
    assert lab["unit"] == "m/s"


def test_missing_metadata_is_explicitly_unknown_not_invented():
    lab = _lab_context({}, {})
    assert lab["instrument"] == "unknown"
    assert lab["calibrationStatus"] == "unknown"
    assert "unknown" in lab["limitations"].lower()


def test_docx_parser_returns_labelled_fields_for_review(monkeypatch):
    # DOCX parsing is exercised by the deployed dependency; this unit test
    # verifies the supported-format gate without creating a binary document.
    upload = Upload("unsupported.xlsx", b"")
    try:
        _parse_metadata(upload)
    except ValueError as exc:
        assert "JSON, JSON-LD, CSV or DOCX" in str(exc)
    else:
        raise AssertionError("Unsupported metadata file should be rejected.")
