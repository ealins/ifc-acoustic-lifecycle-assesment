from pathlib import Path

from fair_platform.vibrometry_sidecar import PROFILE_ID, PROFILE_VERSION, build_sidecar, sha256_uri, validate_shacl


def _lab_context():
    return {
        "method": "3D scanning laser Doppler vibrometry",
        "instrument": "unknown",
        "operator": "unknown",
        "measurementDate": "unknown",
        "calibrationStatus": "unknown",
        "scanSetup": "continuous scan; setup details not available",
        "measuredQuantity": "velocity",
        "unit": "m/s",
        "processingDescription": "unknown",
        "limitations": "Instrument, calibration and processing details require confirmation.",
    }


def _sidecar():
    payload = b"point,velocity\n1,0.03\n"
    ifc_bytes = b"fixture IFC bytes"
    return build_sidecar(
        "scan.csv",
        payload,
        _lab_context(),
        {
            "global_id": "0abc",
            "ifc_schema": "IFC4",
            "source_sha256": sha256_uri(ifc_bytes),
            "ifc_class": "IfcWall",
            "source_file": "wall.ifc",
        },
        record_id="evaluation-record-01",
    )


def test_complete_record_conforms_to_shacl_profile():
    result = validate_shacl(_sidecar())
    assert result["conforms"], result["report_text"]
    assert result["profile_id"] == PROFILE_ID
    assert result["profile_version"] == PROFILE_VERSION


def test_missing_lab_calibration_status_fails_shacl():
    sidecar = _sidecar()
    del sidecar["labContext"]["calibrationStatus"]
    result = validate_shacl(sidecar)
    assert not result["conforms"]
    assert "calibrationStatus" in result["report_text"]


def test_invalid_checksum_lexical_form_fails_shacl():
    sidecar = _sidecar()
    sidecar["measurementPayload"]["sha256"] = "sha256:not-a-real-digest"
    result = validate_shacl(sidecar)
    assert not result["conforms"]
    assert "sha256" in result["report_text"]
