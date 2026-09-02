"""Lightweight test runner."""
import sys, json, time, threading, urllib.request, urllib.error, traceback
from flask_app import app

BASE = "http://127.0.0.1:5050"

def _run_server():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)

def _start_server():
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    time.sleep(2)

def _get_raw(path):
    try:
        resp = urllib.request.urlopen(urllib.request.Request(f"{BASE}{path}", method="GET"))
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def _post_raw(path, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST",
                                headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def _ifc(**o):
    d = {"global_id": "2O2Fr$t4X7ZPjKNAi5dMVr", "name": "Basic Wall",
         "construction_family": "loadbearing", "total_thickness_m": 0.3,
         "material_evidence": [{"layer": "brick", "thickness_m": 0.1}],
         "model_version": "IFC4"}
    d.update(o); return d

def _rec(**o):
    d = {"uri": "https://example.com/records/001", "identifier": "REC-001",
         "assembly": "Load-bearing wall", "construction_family": "loadbearing",
         "total_thickness_m": 0.3, "record_version": "2.1", "available": True}
    d.update(o); return d

# -- tests --
def t01_health():
    s, d = _get_raw("/api/health")
    assert s == 200 and d["status"] == "ok" and d["service"] == "lifecycle-assessment-api"

def t02_match():
    s, d = _post_raw("/api/analyze", {"ifc_evidence": _ifc(), "record_evidence": _rec()})
    assert s == 200 and d["result"]["semantic_status"] == "acceptable"
    assert d["result"]["confidence"] == 0.95

def t03_mismatch():
    p = {"ifc_evidence": _ifc(construction_family="curtain", total_thickness_m=0.15),
         "record_evidence": _rec(construction_family="loadbearing", total_thickness_m=0.3)}
    s, d = _post_raw("/api/analyze", p)
    assert s == 200 and d["result"]["semantic_status"] == "invalid"
    assert d["result"]["confidence"] == 0.20

def t04_broken():
    p = {"ifc_evidence": _ifc(), "record_evidence": _rec(available=False)}
    s, d = _post_raw("/api/analyze", p)
    assert s == 200 and d["result"]["semantic_status"] == "broken"
    assert d["result"]["confidence"] == 0.0

def t05_batch():
    p = {"batch": True,
         "ifc": [_ifc(global_id="A"), _ifc(global_id="B", construction_family="curtain")],
         "records": [_rec(identifier="R1"), _rec(identifier="R2", construction_family="curtain")]}
    s, d = _post_raw("/api/analyze", p)
    assert s == 200 and d["count"] == 4

def t06_missing():
    s, d = _post_raw("/api/analyze", {"ifc_evidence": _ifc()})
    assert s == 400 and "error" in d

def t07_empty():
    s, d = _post_raw("/api/analyze", {})
    assert s == 400 and "error" in d

def t08_404():
    s, d = _get_raw("/api/nonexistent")
    assert s == 404 and "error" in d

TESTS = [("health", t01_health), ("match", t02_match), ("mismatch", t03_mismatch),
         ("broken", t04_broken), ("batch", t05_batch), ("missing", t06_missing),
         ("empty", t07_empty), ("404", t08_404)]

if __name__ == "__main__":
    print("="*50, flush=True)
    print("Flask API Integration Tests", flush=True)
    print("="*50, flush=True)
    _start_server()
    ok = fail = 0
    for name, fn in TESTS:
        try: fn(); ok += 1; print(f"  [PASS] {name}", flush=True)
        except Exception as e:
            fail += 1; print(f"  [FAIL] {name}: {e}", flush=True)
            traceback.print_exc()
    print("="*50, flush=True)
    print(f"Results: {ok} passed, {fail} failed / {len(TESTS)}", flush=True)
    sys.exit(1 if fail else 0)