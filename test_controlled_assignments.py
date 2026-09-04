"""Focused regression tests for controlled real-IFC sample assignments."""

from engine import assign_controlled_sample_records, evaluate_lifecycle


def sample_walls() -> list[dict]:
    return [
        {"GlobalId": "wall-a", "wall_name": "A"},
        {"GlobalId": "wall-b", "wall_name": "B"},
        {"GlobalId": "wall-c", "wall_name": "C"},
    ]


def record_catalog() -> list[dict]:
    return [
        {"record_label": "Record one", "record_id": "record-1", "record_uri": "https://example.org/record/1"},
        {"record_label": "Record two", "record_id": "record-2", "record_uri": "https://example.org/record/2"},
    ]


def test_assignments_are_deterministic_and_round_robin() -> None:
    first = assign_controlled_sample_records(sample_walls(), record_catalog())
    second = assign_controlled_sample_records(sample_walls(), record_catalog())

    assert first == second
    assert [first[wall].record_id for wall in ("wall-a", "wall-b", "wall-c")] == [
        "record-1", "record-2", "record-1"
    ]
    assert all("not produced by candidate discovery" in assignment.rationale for assignment in first.values())


def test_assignment_change_creates_assignment_event() -> None:
    ifc = {
        "GlobalId": "wall-a", "element_type": "IfcWall", "wall_name": "A",
        "construction_family": "metal_frame", "thickness_m": 0.1, "materials": "Metal Stud Layer",
        "native_record_uri": "https://example.org/hft-acoustic/record/record-1",
        "pset_record_uri": "https://example.org/hft-acoustic/record/record-1",
        "pset_mapping_series_uri": "https://example.org/hft-acoustic/mapping-series/wall-a-record-1",
        "mapping_series_uri": "https://example.org/hft-acoustic/mapping-series/wall-a-record-1",
        "association_type": "AcousticPerformanceReference", "semantic_profile": "HFT-Acoustic-Link-v1",
    }
    rdf = {
        "record_uri": ifc["native_record_uri"], "record_id": "record-1", "construction_family": "metal_frame",
        "thickness_m": 0.1, "Rw": 44.1, "unit": "dB", "assembly": "M75", "source_organisation": "Test",
        "report_reference": "R1", "provenance_note": "Controlled fixture", "record_available": True,
        "spectrum_adaptation_C": -2, "spectrum_adaptation_Ctr": -6, "measurement_method": "Test",
        "frequency_data": '[{"frequency_hz": 100, "R_db": 30}]', "layer_data": '[{"material_id": "M75"}]',
    }
    settings = {"thickness_tolerance_m": 0.02, "use_semantic_staleness": True, "require_mapping_series": True}
    assignment = {"assignment_id": "a1", "protocol_id": "p1", "wall_global_id": "wall-a", "record_id": "record-1",
                  "record_uri": rdf["record_uri"], "mapping_series_uri": ifc["mapping_series_uri"],
                  "assignment_method": "controlled"}

    assertion, result, _ = evaluate_lifecycle(ifc, rdf, settings, None, [], assignment)
    assert assertion is not None
    changed = {**assignment, "assignment_method": "tester override"}
    next_assertion, _, events = evaluate_lifecycle(ifc, rdf, settings, result["state"], [assertion], changed)
    assert next_assertion is not None
    assert any(event.side == "ASSIGNMENT" and event.category == "ASSIGNMENT_METHOD_CHANGE" for event in events)
