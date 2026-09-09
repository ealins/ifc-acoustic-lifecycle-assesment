"""Integration tests for the Flask lifecycle API.

The original harness expected an already-running server when collected by pytest,
which made `pytest` fail with connection-refused errors. These tests now exercise
the same HTTP routes through Flask's in-process test client, so they are deterministic
both in CI and on a developer machine.
"""

import json
import sys

from flask_app import app


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get_raw(path):
    """GET through Flask's test client and return (status, body_dict)."""
    with app.test_client() as client:
        response = client.get(path)
        return response.status_code, response.get_json()


def _post_raw(path, payload):
    """POST JSON through Flask's test client and return (status, body_dict)."""
    with app.test_client() as client:
        response = client.post(path, json=payload)
        return response.status_code, response.get_json()


# ── fixtures ──────────────────────────────────────────────────────────────────

def _good_ifc(**overrides):
    data = {
        "global_id": "2O2Fr$t4X7ZPjKNAi5dMVr",
        "name": "Basic Wall:Exterior - Brick on Block",
        "construction_family": "loadbearing",
        "total_thickness_m": 0.3,
        "material_evidence": [
            {"layer": "brick", "thickness_m": 0.1},
            {"layer": "block", "thickness_m": 0.2},
        ],
        "model_version": "IFC4",
    }
    data.update(overrides)
    return data


def _good_record(**overrides):
    data = {
        "uri": "https://example.com/records/acoustic/wall-001",
        "identifier": "VABDAT-WALL-001",
        "assembly": "Load-bearing brick+block wall",
        "construction_family": "loadbearing",
        "total_thickness_m": 0.3,
        "record_version": "2.1",
        "available": True,
    }
    data.update(overrides)
    return data


# ── tests ─────────────────────────────────────────────────────────────────────

def test_01_health():
    status, data = _get_raw("/api/health")
    assert status == 200
    assert data["status"] == "ok"
    assert data["service"] == "lifecycle-assessment-api"


def test_02_single_match():
    status, data = _post_raw(
        "/api/analyze",
        {"ifc_evidence": _good_ifc(), "record_evidence": _good_record()},
    )
    assert status == 200
    result = data["result"]
    assert result["semantic_status"] == "acceptable"
    assert result["confidence"] == 0.95
    assert result["family_match"] is True
    assert result["thickness_match"] is True


def test_03_single_mismatch():
    status, data = _post_raw(
        "/api/analyze",
        {
            "ifc_evidence": _good_ifc(construction_family="curtain", total_thickness_m=0.15),
            "record_evidence": _good_record(construction_family="loadbearing", total_thickness_m=0.3),
        },
    )
    assert status == 200
    result = data["result"]
    assert result["semantic_status"] == "invalid"
    assert result["confidence"] == 0.20
    assert result["family_match"] is False
    assert result["thickness_match"] is False


def test_04_single_broken():
    status, data = _post_raw(
        "/api/analyze",
        {"ifc_evidence": _good_ifc(), "record_evidence": _good_record(available=False)},
    )
    assert status == 200
    result = data["result"]
    assert result["semantic_status"] == "broken"
    assert result["confidence"] == 0.0
    assert result["thickness_match"] is None
    assert result["family_match"] is None


def test_05_batch():
    status, data = _post_raw(
        "/api/analyze",
        {
            "batch": True,
            "ifc": [
                _good_ifc(global_id="IFC-A"),
                _good_ifc(global_id="IFC-B", construction_family="curtain"),
            ],
            "records": [
                _good_record(identifier="REC-1"),
                _good_record(identifier="REC-2", construction_family="curtain"),
            ],
        },
    )
    assert status == 200
    assert data["count"] == 4
    ids = {(row["ifc_global_id"], row["record_id"]) for row in data["results"]}
    assert ids == {
        ("IFC-A", "REC-1"),
        ("IFC-A", "REC-2"),
        ("IFC-B", "REC-1"),
        ("IFC-B", "REC-2"),
    }


def test_06_missing_fields():
    status, data = _post_raw("/api/analyze", {"ifc_evidence": _good_ifc()})
    assert status == 400
    assert "error" in data


def test_07_empty_body():
    status, data = _post_raw("/api/analyze", {})
    assert status == 400
    assert "error" in data


def test_08_not_found():
    status, data = _get_raw("/api/nonexistent")
    assert status == 404
    assert "error" in data


ALL_TESTS = [
    test_01_health,
    test_02_single_match,
    test_03_single_mismatch,
    test_04_single_broken,
    test_05_batch,
    test_06_missing_fields,
    test_07_empty_body,
    test_08_not_found,
]


if __name__ == "__main__":
    passed = 0
    for test in ALL_TESTS:
        try:
            test()
            passed += 1
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")
    print(f"Results: {passed}/{len(ALL_TESTS)} passed")
    sys.exit(0 if passed == len(ALL_TESTS) else 1)
