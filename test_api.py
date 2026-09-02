"""
Comprehensive integration tests for the Flask API server.

Covers:
  1. Health check
  2. Single analysis — matching (acceptable)
  3. Single analysis — mismatch (invalid)
  4. Single analysis — broken record (unavailable)
  5. Batch analysis
  6. Missing fields -> 400
  7. Empty body -> 400
  8. Unknown route -> 404

Usage:
    python test_api.py          # starts its own server on port 5050
"""

import sys
import json
import time
import threading
import urllib.request
import urllib.error

from flask_app import app

BASE = "http://127.0.0.1:5050"

# ── helpers ──────────────────────────────────────────────────────────────────

def _run_server():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


def _start_server():
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    time.sleep(1.5)


def _get_raw(path):
    """GET that does *not* raise on 4xx/5xx -- returns (status, body_dict)."""
    try:
        resp = urllib.request.urlopen(urllib.request.Request(f"{BASE}{path}", method="GET"))
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _post_raw(path, payload):
    """POST that does *not* raise on 4xx/5xx -- returns (status, body_dict)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# ── fixtures ─────────────────────────────────────────────────────────────────

def _good_ifc(**overrides):
    d = {
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
    d.update(overrides)
    return d


def _good_record(**overrides):
    d = {
        "uri": "https://example.com/records/acoustic/wall-001",
        "identifier": "VABDAT-WALL-001",
        "assembly": "Load-bearing brick+block wall",
        "construction_family": "loadbearing",
        "total_thickness_m": 0.3,
        "record_version": "2.1",
        "available": True,
    }
    d.update(overrides)
    return d

# ── tests ────────────────────────────────────────────────────────────────────

def test_01_health():
    """GET /api/health -> 200, status ok."""
    status, data = _get_raw("/api/health")
    assert status == 200, f"Expected 200, got {status}"
    assert data["status"] == "ok"
    assert data["service"] == "lifecycle-assessment-api"
    print("[PASS] 01  GET /api/health")


def test_02_single_match():
    """POST /api/analyze -- matching family & thickness -> acceptable."""
    payload = {
        "ifc_evidence": _good_ifc(),
        "record_evidence": _good_record(),
    }
    status, data = _post_raw("/api/analyze", payload)
    assert status == 200, f"Expected 200, got {status}"
    assert data["status"] == "ok"
    r = data["result"]
    assert r["semantic_status"] == "acceptable"
    assert r["confidence"] == 0.95
    assert r["family_match"] is True
    assert r["thickness_match"] is True
    print("[PASS] 02  POST /api/analyze (single - matching)")


def test_03_single_mismatch():
    """POST /api/analyze -- different family AND thickness -> invalid."""
    payload = {
        "ifc_evidence": _good_ifc(construction_family="curtain", total_thickness_m=0.15),
        "record_evidence": _good_record(construction_family="loadbearing", total_thickness_m=0.3),
    }
    status, data = _post_raw("/api/analyze", payload)
    assert status == 200, f"Expected 200, got {status}"
    assert data["status"] == "ok"
    r = data["result"]
    assert r["semantic_status"] == "invalid"
    assert r["confidence"] == 0.20
    assert r["family_match"] is False
    assert r["thickness_match"] is False
    print("[PASS] 03  POST /api/analyze (single - mismatch)")


def test_04_single_broken():
    """POST /api/analyze -- record unavailable -> broken."""
    payload = {
        "ifc_evidence": _good_ifc(),
        "record_evidence": _good_record(available=False),
    }
    status, data = _post_raw("/api/analyze", payload)
    assert status == 200, f"Expected 200, got {status}"
    assert data["status"] == "ok"
    r = data["result"]
    assert r["semantic_status"] == "broken"
    assert r["confidence"] == 0.0
    assert r["thickness_match"] is None
    assert r["family_match"] is None
    print("[PASS] 04  POST /api/analyze (single - broken record)")


def test_05_batch():
    """POST /api/analyze with batch=true -- cross-product of IFCs x records."""
    payload = {
        "batch": True,
        "ifc": [
            _good_ifc(global_id="IFC-A"),
            _good_ifc(global_id="IFC-B", construction_family="curtain"),
        ],
        "records": [
            _good_record(identifier="REC-1"),
            _good_record(identifier="REC-2", construction_family="curtain"),
        ],
    }
    status, data = _post_raw("/api/analyze", payload)
    assert status == 200, f"Expected 200, got {status}"
    assert data["status"] == "ok"
    assert data["count"] == 4, f"Expected 4 results, got {data['count']}"
    ids = {(r["ifc_global_id"], r["record_id"]) for r in data["results"]}
    assert ("IFC-A", "REC-1") in ids
    assert ("IFC-A", "REC-2") in ids
    assert ("IFC-B", "REC-1") in ids
    assert ("IFC-B", "REC-2") in ids
    print("[PASS] 05  POST /api/analyze (batch)")


def test_06_missing_fields():
    """POST /api/analyze -- missing required fields -> 400."""
    payload = {"ifc_evidence": _good_ifc()}  # missing record_evidence
    status, data = _post_raw("/api/analyze", payload)
    assert status == 400, f"Expected 400, got {status}"
    assert "error" in data
    print("[PASS] 06  POST /api/analyze (missing fields -> 400)")


def test_07_empty_body():
    """POST /api/analyze -- empty JSON body -> 400."""
    status, data = _post_raw("/api/analyze", {})
    assert status == 400, f"Expected 400, got {status}"
    assert "error" in data
    print("[PASS] 07  POST /api/analyze (empty body -> 400)")


def test_08_not_found():
    """GET /api/nonexistent -> 404."""
    status, data = _get_raw("/api/nonexistent")
    assert status == 404, f"Expected 404, got {status}"
    assert "error" in data
    print("[PASS] 08  GET /api/nonexistent (-> 404)")


# ── runner ───────────────────────────────────────────────────────────────────

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
    print("=" * 60)
    print("Flask API Integration Tests")
    print("=" * 60)

    _start_server()

    passed = failed = 0
    for fn in ALL_TESTS:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {e}")

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(ALL_TESTS)}")
    print("=" * 60)
    sys.exit(1 if failed else 0)
