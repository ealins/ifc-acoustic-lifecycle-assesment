"""Tests for the v0.6 sidecar engine (fair_platform/sidecar_v06.py)."""
from pathlib import Path

import pytest

from vibro_ifc import engine as sv


@pytest.fixture(scope="module")
def graph():
    records = sv.list_records()
    assert len(records) == 20
    return sv.load_record(records[0])


def test_validation_reports_known_gaps(graph):
    report = sv.validate_record(graph)
    paths = {r["path"] for r in report["results"] if r["severity"] == "Violation"}
    assert {"identifier", "license"} <= paths          # persistent identifier and licence are known gaps
    assert report["shape_triples"] > 0 and report["data_triples"] == 321


def test_gap_report_lists_declared_fields(graph):
    gaps = sv.gap_report(graph)
    assert "licence" in gaps["absent"] and "excitationType" in gaps["unresolved"]
    assert gaps["units_pending"] > 0


def test_summary_links_data_record_and_ifc(graph):
    info = sv.summary(graph)
    assert info["global_id"] == "0c1zZ8Xcf2Hf51V7zFkw2R"
    assert info["measurement_file"].endswith(".txt") and info["ifc_file"].endswith(".ifc")
    assert info["association_level"] == "component" and info["registration"] == "not established"
    assert "not confirmed" in info["hypothesis_status"]


def test_class_graph_hides_quality_and_flags_own_terms(graph):
    core, full = sv.class_graph(graph), sv.class_graph(graph, include_quality=True)
    assert all(n["prefix"] != "dqv" for n in core["nodes"])
    assert any(n["prefix"] == "dqv" for n in full["nodes"])
    own = [n for n in core["nodes"] if n["own"]]
    assert [n["label"] for n in own] == ["ldv:RegistrationHypothesis"]


def test_data_checks_without_folder_report_not_found(graph):
    rows = sv.data_checks(graph, None)
    assert {r["status"] for r in rows} == {"file not found"} and len(rows) == 2


def test_data_checks_detect_a_changed_file(graph, tmp_path):
    for row in sv.data_checks(graph, None):
        (tmp_path / row["file"]).write_bytes(b"not the recorded content")
    assert {r["status"] for r in sv.data_checks(graph, tmp_path)} == {"MISMATCH"}
