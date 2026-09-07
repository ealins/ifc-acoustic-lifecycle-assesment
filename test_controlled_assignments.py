"""Focused regression tests for controlled assignments and MappingSeries transitions."""

from rdflib import Graph, Namespace, RDF, URIRef

from engine import assign_controlled_sample_records, build_rdf_turtle, evaluate_lifecycle


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
    assert next_assertion.revision_number == 2
    assert next_assertion.previous_assertion_uri == assertion.assertion_uri
    assert next_assertion.series_transition == "SAME_SERIES_REVISION"
    assert any(event.side == "ASSIGNMENT" and event.category == "ASSIGNMENT_METHOD_CHANGE" for event in events)


def _valid_evidence(record_id: str = "record-1") -> tuple[dict, dict, dict, dict]:
    record_uri = f"https://example.org/hft-acoustic/record/{record_id}"
    series_uri = f"https://example.org/hft-acoustic/mapping-series/wall-a-{record_id}"
    ifc = {
        "GlobalId": "wall-a", "element_type": "IfcWall", "wall_name": "A",
        "construction_family": "metal_frame", "thickness_m": 0.1, "materials": "Metal Stud Layer",
        "native_record_uri": record_uri, "pset_record_uri": record_uri,
        "pset_mapping_series_uri": series_uri, "mapping_series_uri": series_uri,
        "association_type": "AcousticPerformanceReference", "semantic_profile": "HFT-Acoustic-Link-v1",
    }
    rdf = {
        "record_uri": record_uri, "record_id": record_id, "construction_family": "metal_frame",
        "thickness_m": 0.1, "Rw": 44.1, "unit": "dB", "assembly": "M75",
        "source_organisation": "Test", "report_reference": "R1", "provenance_note": "Controlled fixture",
        "record_available": True, "spectrum_adaptation_C": -2, "spectrum_adaptation_Ctr": -6,
        "measurement_method": "Test", "frequency_data": '[{"frequency_hz": 100, "R_db": 30}]',
        "layer_data": '[{"material_id": "M75"}]',
    }
    settings = {
        "validation_profile": "Balanced default", "thickness_tolerance_m": 0.02,
        "use_semantic_staleness": True, "require_mapping_series": True,
    }
    assignment = {
        "assignment_id": f"assignment-{record_id}", "protocol_id": "p1", "wall_global_id": "wall-a",
        "record_id": record_id, "record_uri": record_uri, "mapping_series_uri": series_uri,
        "assignment_method": "controlled",
    }
    return ifc, rdf, settings, assignment


def test_acoustic_content_change_stays_in_same_series() -> None:
    ifc, rdf, settings, assignment = _valid_evidence()
    first, result, _ = evaluate_lifecycle(ifc, rdf, settings, None, [], assignment)
    assert first is not None

    changed_rdf = {**rdf, "Rw": 46.0, "provenance_note": "Updated laboratory result"}
    second, next_result, events = evaluate_lifecycle(ifc, changed_rdf, settings, result["state"], [first], assignment)

    assert second is not None
    assert second.mapping_series_uri == first.mapping_series_uri
    assert second.revision_number == 2
    assert second.previous_assertion_uri == first.assertion_uri
    assert second.supersedes_series_uri is None
    assert next_result["transition"]["kind"] == "SAME_SERIES_REVISION"
    assert any(event.category == "RDF_RW_CHANGE" for event in events)


def test_record_target_change_creates_new_series_at_revision_one() -> None:
    ifc, rdf, settings, assignment = _valid_evidence()
    first, result, _ = evaluate_lifecycle(ifc, rdf, settings, None, [], assignment)
    assert first is not None

    next_ifc, next_rdf, next_settings, next_assignment = _valid_evidence("record-2")
    second, next_result, events = evaluate_lifecycle(
        next_ifc, next_rdf, next_settings, result["state"], [first], next_assignment
    )

    assert second is not None
    assert second.mapping_series_uri != first.mapping_series_uri
    assert second.revision_number == 1
    assert second.previous_revision is None
    assert second.previous_assertion_uri is None
    assert second.supersedes_series_uri == first.mapping_series_uri
    assert second.series_transition == "NEW_SERIES"
    assert next_result["transition"]["kind"] == "NEW_SERIES"
    assert next_result["semantic"]["semantic_status"] == "UNMATCHED"
    assert any(event.category == "RECORD_TARGET_CHANGE" for event in events)


def test_rdf_export_scopes_assertions_to_series_and_supersession() -> None:
    ifc, rdf, settings, assignment = _valid_evidence()
    first, result, _ = evaluate_lifecycle(ifc, rdf, settings, None, [], assignment)
    assert first is not None
    next_ifc, next_rdf, next_settings, next_assignment = _valid_evidence("record-2")
    second, _, _ = evaluate_lifecycle(next_ifc, next_rdf, next_settings, result["state"], [first], next_assignment)
    assert second is not None

    graph = Graph().parse(data=build_rdf_turtle([first, second]), format="turtle")
    map_ns = Namespace("https://example.org/hft-acoustic/mapping/vocab/")
    prov_ns = Namespace("http://www.w3.org/ns/prov#")
    first_uri = URIRef(first.assertion_uri)
    second_uri = URIRef(second.assertion_uri)

    assert (first_uri, RDF.type, map_ns.MappingAssertion) in graph
    assert (second_uri, RDF.type, map_ns.MappingAssertion) in graph
    assert (second_uri, prov_ns.wasRevisionOf, first_uri) not in graph
    assert (URIRef(second.mapping_series_uri), map_ns.supersedes, URIRef(first.mapping_series_uri)) in graph
    assert len(list(graph.objects(URIRef(first.mapping_series_uri), map_ns.currentAssertion))) == 1
    assert len(list(graph.objects(URIRef(second.mapping_series_uri), map_ns.currentAssertion))) == 1


def test_discrepancy_audit_keeps_non_gating_warnings() -> None:
    ifc, rdf, settings, assignment = _valid_evidence()
    ifc["semantic_profile"] = ""
    assertion, result, _ = evaluate_lifecycle(ifc, rdf, settings, None, [], assignment)

    assert assertion is not None
    assert result["semantic"]["semantic_status"] == "ACCEPTABLE"
    assert any(item["category"] == "IDS" and item["field"] == "semantic_profile" for item in result["discrepancies"])
