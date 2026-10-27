from dashboard.ui.live_validation_workbench import _fixture
from fair_platform.vibrometry_sidecar import build_sidecar, sha256_uri, validate_shacl, validate_sidecar


def _record():
    measurement, ifc, lab, context = _fixture()
    return measurement, ifc, lab, context, build_sidecar(
        "scan.csv", measurement, lab, context, record_id="interactive-fixture"
    )


def test_interactive_fixture_baseline_passes_profile_and_cross_layer_checks():
    measurement, ifc, _, context, sidecar = _record()
    assert validate_shacl(sidecar)["conforms"]
    assert validate_sidecar(
        sidecar, measurement, ifc,
        {"resolved": True, "global_id": context["global_id"], "ifc_class": context["ifc_class"]},
    ) == []


def test_interactive_fixture_detects_changed_measurement_bytes():
    measurement, ifc, _, context, sidecar = _record()
    issues = validate_sidecar(
        sidecar, measurement + b" ",
        ifc, {"resolved": True, "global_id": context["global_id"], "ifc_class": context["ifc_class"]},
    )
    assert "MEASUREMENT_HASH_MISMATCH" in {item["code"] for item in issues}
    assert "MEASUREMENT_SIZE_MISMATCH" in {item["code"] for item in issues}


def test_interactive_fixture_detects_unresolved_ifc_identifier():
    measurement, ifc, _, _, sidecar = _record()
    issues = validate_sidecar(sidecar, measurement, ifc, {"resolved": False})
    assert "IFC_GLOBALID_UNRESOLVED" in {item["code"] for item in issues}


def test_interactive_fixture_detects_missing_shacl_property():
    _, _, _, _, sidecar = _record()
    del sidecar["labContext"]["calibrationStatus"]
    result = validate_shacl(sidecar)
    assert not result["conforms"]
    assert "calibrationStatus" in result["report_text"]
