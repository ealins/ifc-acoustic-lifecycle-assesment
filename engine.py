from __future__ import annotations

import json
import random
import hashlib
from typing import Any
from pathlib import Path
import ifcopenshell
from ifcopenshell.util.element import get_material
from rdflib import Graph, Literal, Namespace, RDF, URIRef

from models import (
    AssignmentMetadata,
    ChangeEvent,
    EvidenceSnapshot,
    MappingAssertion,
    MappingSeries,
    ValidationActivity,
    utc_now,
)

BASE_URL = "https://example.org/hft-acoustic"
CONTROLLED_ASSIGNMENT_PROTOCOL = "real-ifc-sample-round-robin-v1"
CONTROLLED_ASSIGNMENT_METHOD = "deterministic controlled test allocation"
CONTROLLED_ASSIGNMENT_SEED = 42
BSDD_MAP = {
    "metal_frame": "bsDD:MetalFrameWall",
    "Metal Stud Layer": "bsDD:MetalStudLayer",
    "concrete": "bsDD:ConcreteWall",
    "Rw": "bsDD:WeightedSoundReductionIndex",
    "dB": "unit:Decibel",
    "AcousticPerformanceReference": "bsDD:AcousticPerformanceReference",
}

IFC_FIELDS = {
    "GlobalId": "IFC_GLOBALID_CHANGE",
    "element_type": "IFC_TYPE_CHANGE",
    "wall_name": "IFC_NAME_CHANGE",
    "construction_family": "IFC_FAMILY_CHANGE",
    "thickness_m": "IFC_THICKNESS_CHANGE",
    "materials": "IFC_MATERIAL_CHANGE",
    "native_record_uri": "IFC_NATIVE_URI_CHANGE",
    "pset_record_uri": "IFC_PSET_URI_CHANGE",
    "pset_mapping_series_uri": "IFC_PSET_MAPPING_SERIES_URI_CHANGE",
    "mapping_series_uri": "IFC_MAPPING_SERIES_URI_CHANGE",
    "association_type": "IFC_ASSOCIATION_TYPE_CHANGE",
    "semantic_profile": "IFC_SEMANTIC_PROFILE_CHANGE",
}
LINK_VALIDATION_QUERY = """SELECT ?wall ?nativeUri ?recordUri ?series WHERE {
    ?wall a ifcowl:IfcWall ; map:nativeRecordUri ?nativeUri ; map:recordUri ?recordUri ; map:mappingSeries ?series .
    FILTER(?nativeUri = ?recordUri)
}"""
LIFECYCLE_QUERY = """SELECT ?assertion ?revision ?status ?previous WHERE {
    ?assertion a map:MappingAssertion ; map:revisionNumber ?revision ; map:semanticStatus ?status .
    OPTIONAL { ?assertion prov:wasRevisionOf ?previous }
} ORDER BY ?revision"""
RDF_FIELDS = {
    "record_uri": "RDF_RECORD_URI_CHANGE",
    "record_id": "RDF_RECORD_ID_CHANGE",
    "construction_family": "RDF_FAMILY_CHANGE",
    "thickness_m": "RDF_THICKNESS_CHANGE",
    "Rw": "RDF_RW_CHANGE",
    "unit": "RDF_UNIT_CHANGE",
    "assembly": "RDF_ASSEMBLY_CHANGE",
    "source_organisation": "RDF_SOURCE_CHANGE",
    "report_reference": "RDF_REPORT_CHANGE",
    "provenance_note": "RDF_PROVENANCE_CHANGE",
    "record_available": "RDF_AVAILABILITY_CHANGE",
    "spectrum_adaptation_C": "RDF_C_CHANGE",
    "spectrum_adaptation_Ctr": "RDF_CTR_CHANGE",
    "measurement_method": "RDF_MEASUREMENT_METHOD_CHANGE",
    "frequency_data": "RDF_FREQUENCY_DATA_CHANGE",
    "layer_data": "RDF_LAYER_DATA_CHANGE",
}
SETTING_FIELDS = {
    "validation_profile": "VALIDATION_PROFILE_CHANGE",
    "thickness_tolerance_m": "THICKNESS_TOLERANCE_CHANGE",
    "use_semantic_staleness": "SEMANTIC_STALENESS_SETTING_CHANGE",
    "require_mapping_series": "REQUIRE_MAPPING_SERIES_SETTING_CHANGE",
    "semantic_override_status": "SEMANTIC_OVERRIDE_CHANGE",
    "semantic_override_note": "OVERRIDE_RATIONALE_CHANGE",
}


def expected_mapping_series_uri(ifc: dict[str, Any], rdf: dict[str, Any]) -> str:
    return f"{BASE_URL}/mapping-series/{ifc.get('GlobalId', '')}-{rdf.get('record_id', '')}"


def assign_controlled_sample_records(
    walls: list[dict[str, Any]],
    record_catalog: list[dict[str, Any]],
    *,
    protocol_id: str = CONTROLLED_ASSIGNMENT_PROTOCOL,
    sample_seed: int = CONTROLLED_ASSIGNMENT_SEED,
) -> dict[str, AssignmentMetadata]:
    """Assign external sample records reproducibly without claiming candidate discovery."""
    if not record_catalog:
        raise ValueError("At least one external sample record is required")

    assignments: dict[str, AssignmentMetadata] = {}
    for position, wall in enumerate(walls, start=1):
        global_id = str(wall.get("GlobalId", "")).strip()
        if not global_id:
            raise ValueError("Every sampled IFC wall must have a GlobalId")
        record = record_catalog[(position - 1) % len(record_catalog)]
        record_id = str(record["record_id"])
        record_uri = str(record.get("record_uri") or f"{BASE_URL}/record/{record_id}")
        assignment_id = f"assignment-{protocol_id}-{position:03d}-{global_id}-{record_id}"
        assignments[global_id] = AssignmentMetadata(
            assignment_id=assignment_id,
            protocol_id=protocol_id,
            wall_global_id=global_id,
            record_label=str(record.get("record_label", record_id)),
            record_id=record_id,
            record_uri=record_uri,
            mapping_series_uri=f"{BASE_URL}/mapping-series/{global_id}-{record_id}",
            assignment_method=CONTROLLED_ASSIGNMENT_METHOD,
            sample_seed=sample_seed,
            sample_position=position,
            rationale="Controlled test input; not extracted from IFC and not produced by candidate discovery.",
        )
    return assignments


def extract_ifc_walls(path: str, sample_size: int | None = None) -> tuple[list[dict[str, Any]], int]:
    model = ifcopenshell.open(path)
    walls_by_guid = {str(wall.GlobalId): wall for wall in model.by_type("IfcWall")}
    walls = [walls_by_guid[guid] for guid in sorted(walls_by_guid)]
    total_count = len(walls)
    if sample_size and 0 < sample_size < total_count:
        walls = random.Random(CONTROLLED_ASSIGNMENT_SEED).sample(walls, sample_size)

    # Record source provenance (filename and content hash) for the snapshots
    file_hash = _file_hash(path)

    extracted = []
    for wall in walls:
        materials = []
        thickness = None
        material = get_material(wall)
        if material and material.is_a("IfcMaterialLayerSetUsage"):
            layer_set = material.ForLayerSet
            materials = [layer.Material.Name for layer in layer_set.MaterialLayers if layer.Material and layer.Material.Name]
            thickness = sum(layer.LayerThickness for layer in layer_set.MaterialLayers) / 1000
        elif material and material.is_a("IfcMaterialLayerSet"):
            # Direct IfcMaterialLayerSet: layer thickness carries the IFC model unit
            # (typically meters in this model, no mm->m conversion needed)
            materials = [layer.Material.Name for layer in material.MaterialLayers if layer.Material and layer.Material.Name]
            thickness = sum(layer.LayerThickness for layer in material.MaterialLayers)
        elif material and material.is_a("IfcMaterial"):
            materials = [material.Name] if material.Name else []
        extracted.append({
            "GlobalId": wall.GlobalId,
            "element_type": wall.is_a(),
            "wall_name": wall.Name or "",
            "construction_family": "",
            "thickness_m": round(thickness, 4) if thickness is not None else 0.0,
            "materials": " / ".join(materials),
            "native_record_uri": "",
            "pset_record_uri": "",
            "pset_mapping_series_uri": "",
            "mapping_series_uri": "",
            "association_type": "",
            "semantic_profile": "",
            "source_file": str(Path(path).name),
            "source_hash": file_hash,
        })
    return extracted, total_count


def _file_hash(path: str) -> str:
    """Return a short SHA-256 content hash of the source IFC file for provenance."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()[:12]
    except OSError:
        return ""


def validate_mapping_series(ifc: dict[str, Any], rdf: dict[str, Any]) -> dict[str, Any]:
    actual = str(ifc.get("mapping_series_uri", "")).strip()
    expected = expected_mapping_series_uri(ifc, rdf)
    validity = "PASS" if actual == expected else "MISSING" if not actual else "MISMATCH"
    return {"status": validity, "actual": actual, "expected": expected}


def validate_native_link(ifc: dict[str, Any], rdf: dict[str, Any]) -> dict[str, Any]:
    if not rdf.get("record_available", False):
        state = "BROKEN"
    elif str(ifc.get("native_record_uri", "")).strip() != str(rdf.get("record_uri", "")).strip():
        state = "URI_MISMATCH"
    else:
        state = "RESOLVED"
    return {"state": state, "ifc_uri": ifc.get("native_record_uri", ""), "rdf_uri": rdf.get("record_uri", "")}


def validate_pset_link(ifc: dict[str, Any], rdf: dict[str, Any]) -> dict[str, Any]:
    pset_uri = str(ifc.get("pset_record_uri", "")).strip()
    native_uri = str(ifc.get("native_record_uri", "")).strip()
    rdf_uri = str(rdf.get("record_uri", "")).strip()
    if not pset_uri:
        state = "MISSING"
    elif pset_uri == rdf_uri and pset_uri == native_uri:
        state = "MATCHES_NATIVE"
    else:
        state = "MISMATCH"
    return {"state": state, "pset_uri": pset_uri, "native_uri": native_uri, "rdf_uri": rdf_uri}


def validate_record_data(ifc: dict[str, Any], rdf: dict[str, Any], tolerance_m: float) -> dict[str, Any]:
    """Validate the record's identity, core acoustic value, and compatibility fields."""
    family_match = str(ifc.get("construction_family", "")).strip().lower() == str(rdf.get("construction_family", "")).strip().lower()
    try:
        thickness_difference = abs(float(ifc.get("thickness_m")) - float(rdf.get("thickness_m")))
    except (TypeError, ValueError):
        thickness_difference = float("inf")
    try:
        rw_valid = 0 < float(rdf.get("Rw")) < 100
    except (TypeError, ValueError):
        rw_valid = False
    checks = [
        ("record_id", "record identity is present", _present(rdf.get("record_id"))),
        ("construction_family", "IFC and record families match", family_match),
        ("thickness_m", f"difference <= {tolerance_m:.3f} m", thickness_difference <= tolerance_m),
        ("Rw", "numeric acoustic value between 0 and 100", rw_valid),
        ("unit", "unit is dB", str(rdf.get("unit", "")).strip().lower() == "db"),
        ("assembly", "assembly identifier is present", _present(rdf.get("assembly"))),
        ("source_organisation", "source is present", _present(rdf.get("source_organisation"))),
        ("report_reference", "report reference is present", _present(rdf.get("report_reference"))),
        ("provenance_note", "provenance is present", _present(rdf.get("provenance_note"))),
        ("record_available", "record is available", bool(rdf.get("record_available"))),
    ]
    rows = [{"field": field, "value": rdf.get(field, ""), "rule": rule, "status": "PASS" if passed else "FAIL"} for field, rule, passed in checks]
    status = "PASS" if all(passed for _, _, passed in checks) else "FAIL"
    return {"status": status, "rows": rows, "thickness_difference_m": thickness_difference, "family_match": family_match}


def validate_simulation_readiness(rdf: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for field, rule in (("spectrum_adaptation_C", "C value is numeric"), ("spectrum_adaptation_Ctr", "Ctr value is numeric")):
        try:
            float(rdf.get(field))
            passed = True
        except (TypeError, ValueError):
            passed = False
        checks.append((field, rdf.get(field, ""), rule, passed))
    method = _present(rdf.get("measurement_method"))
    checks.append(("measurement_method", rdf.get("measurement_method", ""), "measurement or calculation method is documented", method))
    parsed = {}
    for field, rule in (("frequency_data", "frequency-band R(f) data is a JSON array with observations"), ("layer_data", "layer/build-up data is a JSON array with layers")):
        try:
            parsed[field] = json.loads(rdf.get(field, ""))
            passed = isinstance(parsed[field], list) and bool(parsed[field]) and all(isinstance(item, dict) for item in parsed[field])
        except (TypeError, json.JSONDecodeError):
            passed = False
        checks.append((field, rdf.get(field, ""), rule, passed))
    rows = [{"field": field, "value": value, "rule": rule, "status": "PASS" if passed else "MISSING/INVALID"} for field, value, rule, passed in checks]
    return {"status": "PASS" if all(passed for _, _, _, passed in checks) else "PARTIAL", "rows": rows, "parsed": parsed}

def validate_link_state(technical: dict[str, Any], mapping: dict[str, Any], pset: dict[str, Any], require_mapping_series: bool) -> str:
    if technical["state"] == "BROKEN":
        return "BROKEN"
    if technical["state"] == "URI_MISMATCH" or pset["state"] == "MISMATCH" or (require_mapping_series and mapping["status"] != "PASS"):
        return "INVALID"
    return "RESOLVED"


def record_target_changed(previous: dict[str, Any] | None, ifc: dict[str, Any], rdf: dict[str, Any]) -> bool:
    if not previous:
        return False
    previous_ifc = previous.get("ifc", {})
    previous_rdf = previous.get("rdf", {})
    return any(
        previous_value != current_value
        for previous_value, current_value in (
            (previous_ifc.get("native_record_uri"), ifc.get("native_record_uri")),
            (previous_ifc.get("mapping_series_uri"), ifc.get("mapping_series_uri")),
            (previous_rdf.get("record_uri"), rdf.get("record_uri")),
            (previous_rdf.get("record_id"), rdf.get("record_id")),
        )
    )


def build_discrepancies(ifc: dict[str, Any], rdf: dict[str, Any], mapping: dict[str, Any], technical: dict[str, Any], pset: dict[str, Any], data: dict[str, Any], ids: dict[str, Any], bsdd: dict[str, Any], link_status: str, semantic_status: str, target_changed: bool) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []

    def add(category: str, severity: str, field: str, ifc_value: Any, rdf_value: Any, rule: str, action: str) -> None:
        discrepancies.append({"category": category, "severity": severity, "field": field, "IFC value": ifc_value, "RDF value": rdf_value, "rule": rule, "required action": action})

    if technical["state"] != "RESOLVED":
        add("Native link", "ERROR", "native_record_uri / record_uri", technical["ifc_uri"], technical["rdf_uri"], "URIs must match and the record must be available", "Repair the URI or restore record availability")
    if mapping["status"] != "PASS":
        add("MappingSeries", "ERROR", "mapping_series_uri", mapping["actual"], mapping["expected"], "Actual URI must equal the expected GlobalId + record_id URI", "Update the MappingSeries URI")
    if pset["state"] != "MATCHES_NATIVE":
        add("Pset link", "ERROR" if pset["state"] == "MISMATCH" else "WARNING", "pset_record_uri", pset["pset_uri"], pset["rdf_uri"], "Pset semantic link must agree with native IFC and RDF URIs", "Repair or explicitly document the Pset link")
    for row in data["rows"]:
        if row["status"] != "PASS":
            add("RDF data", "ERROR", row["field"], ifc.get(row["field"], ""), row["value"], row["rule"], "Correct the RDF registry value or review the association")
    for field in ids["missing_required"]:
        add("IDS", "ERROR", field, ifc.get(field, ""), "not applicable", "Required IFC evidence must be present", "Provide the required IFC value")
    for field in ids["missing_optional"]:
        add("IDS", "WARNING", field, ifc.get(field, ""), "not applicable", "Optional semantic-routing evidence is recommended", "Add the optional IFC value or accept partial readiness")
    for row in bsdd["rows"]:
        if row["status"] != "ALIGNED":
            add("bSDD", "WARNING", row["field"], row["original value"] if row["side"] == "IFC" else "not applicable", row["original value"] if row["side"] == "RDF" else "not applicable", "Term should map to a controlled concept", "Map the term or document the exception")
    if target_changed:
        add("Lifecycle", "WARNING", "record target", "changed from previous revision", rdf.get("record_id", ""), "A retargeted association requires explicit approval", "Review and override only after approving the new record")
    if semantic_status != "ACCEPTABLE" and not target_changed:
        add("Semantic", "ERROR", "semantic_status", semantic_status, "association decision", "Overall association must be acceptable", "Resolve the listed discrepancies before accepting")
    if link_status == "RESOLVED" and data["status"] == "PASS" and semantic_status == "ACCEPTABLE":
        return []
    return discrepancies


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def validate_ids(ifc: dict[str, Any]) -> dict[str, Any]:
    required = ["GlobalId", "element_type", "construction_family", "thickness_m", "materials", "native_record_uri"]
    optional = ["mapping_series_uri", "pset_record_uri", "pset_mapping_series_uri", "association_type", "semantic_profile"]
    missing_required = [field for field in required if not _present(ifc.get(field))]
    missing_optional = [field for field in optional if not _present(ifc.get(field))]
    status = "FAIL" if missing_required else "PARTIAL" if missing_optional else "PASS"
    rows = [
        {"field": field, "requirement": "required", "value": ifc.get(field, ""), "status": "PASS" if _present(ifc.get(field)) else "MISSING"}
        for field in required
    ]
    rows.extend(
        {"field": field, "requirement": "optional", "value": ifc.get(field, ""), "status": "PASS" if _present(ifc.get(field)) else "MISSING"}
        for field in optional
    )
    return {"status": status, "missing_required": missing_required, "missing_optional": missing_optional, "rows": rows}


def validate_bsdd(ifc: dict[str, Any], rdf: dict[str, Any]) -> dict[str, Any]:
    terms = [
        ("IFC", "construction_family", ifc.get("construction_family")),
        ("IFC", "materials", ifc.get("materials")),
        ("IFC", "association_type", ifc.get("association_type")),
        ("RDF", "construction_family", rdf.get("construction_family")),
        ("RDF", "unit", rdf.get("unit")),
        ("RDF", "Rw", "Rw" if _present(rdf.get("Rw")) else ""),
    ]
    rows = []
    mapped_count = 0
    for side, field, value in terms:
        concept = BSDD_MAP.get(str(value), "")
        mapped = bool(concept)
        mapped_count += int(mapped)
        rows.append({"side": side, "field": field, "original value": value, "mapped concept": concept or "No local concept", "status": "ALIGNED" if mapped else "UNMAPPED"})
    status = "ALIGNED" if mapped_count == len(terms) else "PARTIAL" if mapped_count else "UNALIGNED"
    return {"status": status, "rows": rows}


def assess_semantic_status(ifc: dict[str, Any], rdf: dict[str, Any], technical: dict[str, Any], previous: dict[str, Any] | None, settings: dict[str, Any]) -> dict[str, Any]:
    if technical["state"] == "BROKEN":
        status, rationale = "BROKEN", "The external RDF record is unavailable. Last known evidence is retained for review."
    elif technical["state"] == "URI_MISMATCH":
        status, rationale = "INVALID", "The native IFC record URI does not identify the RDF record being assessed."
    elif str(ifc.get("construction_family", "")).strip().lower() != str(rdf.get("construction_family", "")).strip().lower():
        status, rationale = "INVALID", "IFC and RDF construction families contradict each other."
    else:
        try:
            difference = abs(float(ifc.get("thickness_m", 0)) - float(rdf.get("thickness_m", 0)))
        except (TypeError, ValueError):
            difference = float("inf")
        if difference <= float(settings.get("thickness_tolerance_m", 0.02)):
            status, rationale = "ACCEPTABLE", f"Family matches and thickness difference ({difference:.3f} m) is within tolerance."
        else:
            status, rationale = "AMBIGUOUS", f"Family matches, but thickness difference ({difference:.3f} m) exceeds tolerance."
        if (
            settings.get("use_semantic_staleness", True)
            and previous
            and previous.get("results", {}).get("semantic_status") == "ACCEPTABLE"
            and status == "AMBIGUOUS"
        ):
            status, rationale = "SEMANTICALLY_STALE", "The resolved link remains reachable, but evidence that justified the previous acceptable association no longer holds."
    override_status = settings.get("semantic_override_status", "")
    if override_status:
        override_note = str(settings.get("semantic_override_note", "")).strip() or "Manually promoted by reviewer."
        status = override_status
        rationale = f"Override applied: {override_note}"
    return {"semantic_status": status, "requires_review": status != "ACCEPTABLE", "rationale": rationale, "decision_factors": [technical["state"], status]}


def _change_events(previous: dict[str, Any] | None, current_ifc: dict[str, Any], current_rdf: dict[str, Any], current_assignment: dict[str, Any], current_results: dict[str, Any]) -> list[ChangeEvent]:
    if not previous:
        return []
    events: list[ChangeEvent] = []
    for side, fields, current in [("IFC", IFC_FIELDS, current_ifc), ("RDF", RDF_FIELDS, current_rdf)]:
        old_values = previous.get("ifc" if side == "IFC" else "rdf", {})
        for field, category in fields.items():
            old, new = old_values.get(field), current.get(field)
            if old != new:
                events.append(ChangeEvent(category, side, field, old, new))
    assignment_fields = {
        "record_id": "ASSIGNMENT_RECORD_CHANGE",
        "record_uri": "ASSIGNMENT_RECORD_CHANGE",
        "mapping_series_uri": "ASSIGNMENT_MAPPING_SERIES_CHANGE",
        "assignment_method": "ASSIGNMENT_METHOD_CHANGE",
        "protocol_id": "ASSIGNMENT_PROTOCOL_CHANGE",
    }
    old_assignment = previous.get("assignment", {})
    for field, category in assignment_fields.items():
        old, new = old_assignment.get(field), current_assignment.get(field)
        if old != new:
            events.append(ChangeEvent(category, "ASSIGNMENT", field, old, new))
    old_settings = previous.get("settings", {})
    current_settings = current_results.get("settings", {})
    for field, category in SETTING_FIELDS.items():
        old, new = old_settings.get(field), current_settings.get(field)
        if old != new:
            events.append(ChangeEvent(category, "VALIDATION", field, old, new))
    old_results = previous.get("results", {})
    result_fields = {
        "technical_state": "TECHNICAL_STATE_CHANGE",
        "semantic_status": "SEMANTIC_STATUS_CHANGE",
        "ids_status": "IDS_STATUS_CHANGE",
        "bsdd_status": "BSDD_STATUS_CHANGE",
        "mapping_series_validity": "MAPPING_SERIES_VALIDITY_CHANGE",
        "link_status": "LINK_STATUS_CHANGE",
        "data_status": "RDF_DATA_VALIDITY_CHANGE",
        "record_target_changed": "RECORD_TARGET_CHANGE",
        "rationale": "RATIONAL_CHANGE",
        "requires_review": "REVIEW_STATE_CHANGE",
        "mapping_expected_uri": "MAPPING_SERIES_EXPECTED_URI_CHANGE",
    }
    for field, category in result_fields.items():
        old, new = old_results.get(field), current_results.get(field)
        if old != new:
            events.append(ChangeEvent(category, "VALIDATION", field, old, new))
    return events


def evaluate_lifecycle(ifc: dict[str, Any], rdf: dict[str, Any], settings: dict[str, Any], previous: dict[str, Any] | None, assertions: list[MappingAssertion], assignment: dict[str, Any] | None = None) -> tuple[MappingAssertion | None, dict[str, Any], list[ChangeEvent]]:
    assignment = dict(assignment or {})
    mapping = validate_mapping_series(ifc, rdf)
    technical = validate_native_link(ifc, rdf)
    ids = validate_ids(ifc)
    bsdd = validate_bsdd(ifc, rdf)
    pset = validate_pset_link(ifc, rdf)
    data = validate_record_data(ifc, rdf, float(settings.get("thickness_tolerance_m", 0.02)))
    simulation = validate_simulation_readiness(rdf)
    link_status = validate_link_state(technical, mapping, pset, bool(settings.get("require_mapping_series", True)))
    semantic = assess_semantic_status(ifc, rdf, technical, previous, settings)
    target_changed = record_target_changed(previous, ifc, rdf)
    if target_changed and not settings.get("semantic_override_status"):
        semantic = {
            "semantic_status": "UNMATCHED",
            "requires_review": True,
            "rationale": "The IFC wall has been retargeted to a different RDF record. Validate and explicitly approve the new association before accepting it.",
            "decision_factors": [link_status, data["status"], "NEW_RECORD_TARGET"],
        }
    if (
        settings.get("require_mapping_series", True)
        and mapping["status"] != "PASS"
        and semantic["semantic_status"] not in {"BROKEN", "INVALID"}
    ):
        semantic = {
            "semantic_status": "INVALID",
            "requires_review": True,
            "rationale": "The required MappingSeries anchor is missing or does not match the expected wall-record pair.",
            "decision_factors": [technical["state"], mapping["status"], "INVALID"],
        }
    if link_status != "RESOLVED" or data["status"] != "PASS":
        semantic = {
            "semantic_status": "BROKEN" if link_status == "BROKEN" else "INVALID" if link_status == "INVALID" or not data["family_match"] else "AMBIGUOUS",
            "requires_review": True,
            "rationale": "The association is not acceptable because the link and complete RDF record-data checks must both pass.",
            "decision_factors": [link_status, data["status"]],
        }
    discrepancies = build_discrepancies(ifc, rdf, mapping, technical, pset, data, ids, bsdd, link_status, semantic["semantic_status"], target_changed)
    results = {
        "technical_state": technical["state"],
        "link_status": link_status,
        "data_status": data["status"],
        "simulation_status": simulation["status"],
        "pset_status": pset["state"],
        "record_target_changed": target_changed,
        "discrepancies": discrepancies,
        "semantic_status": semantic["semantic_status"],
        "ids_status": ids["status"],
        "bsdd_status": bsdd["status"],
        "mapping_series_validity": mapping["status"],
        "rationale": semantic["rationale"],
        "requires_review": semantic["requires_review"],
        "mapping_expected_uri": mapping["expected"],
        "assignment_id": assignment.get("assignment_id", ""),
        "assignment_method": assignment.get("assignment_method", ""),
        "settings": dict(settings),
    }
    events = _change_events(previous, ifc, rdf, assignment, results)
    state = {"ifc": dict(ifc), "rdf": dict(rdf), "assignment": assignment, "results": results, "settings": dict(settings)}
    if previous is not None and not events:
        return None, {"mapping": mapping, "technical": technical, "pset": pset, "data": data, "simulation": simulation, "link_status": link_status, "ids": ids, "bsdd": bsdd, "semantic": semantic, "discrepancies": discrepancies, "state": state}, events
    revision = len(assertions) + 1
    series = MappingSeries(mapping["expected"], str(ifc.get("GlobalId", "")), str(rdf.get("record_id", "")))
    assertion = MappingAssertion(
        revision_number=revision,
        timestamp=utc_now(),
        mapping_series_uri=series.uri,
        ifc_snapshot=EvidenceSnapshot("IFC", dict(ifc)),
        rdf_snapshot=EvidenceSnapshot("RDF", dict(rdf)),
        technical_link_state=technical["state"],
        link_status=link_status,
        data_status=data["status"],
        mapping_series_validity=mapping["status"],
        ids_status=ids["status"],
        bsdd_status=bsdd["status"],
        semantic_status=semantic["semantic_status"],
        requires_review=semantic["requires_review"],
        rationale=semantic["rationale"],
        assignment_snapshot=EvidenceSnapshot("ASSIGNMENT", assignment) if assignment else None,
        change_events=events,
        previous_revision=assertions[-1].revision_number if assertions else None,
        validation_activity=ValidationActivity(revision, utc_now(), f"validation-r{revision}", ["controlled assignment", "native link", "MappingSeries", "IDS", "bSDD", "semantic assessment"]),
    )
    return assertion, {"mapping": mapping, "technical": technical, "pset": pset, "data": data, "simulation": simulation, "link_status": link_status, "ids": ids, "bsdd": bsdd, "semantic": semantic, "discrepancies": discrepancies, "state": state}, events


def build_rdf_turtle(assertions: list[MappingAssertion]) -> str:
    graph = Graph()
    map_ns = Namespace("https://example.org/hft-acoustic/vocab#")
    prov_ns = Namespace("http://www.w3.org/ns/prov#")
    graph.bind("map", map_ns)
    graph.bind("prov", prov_ns)
    for assertion in assertions:
        aid = map_ns[f"MappingAssertion_r{assertion.revision_number}"]
        series = URIRef(assertion.mapping_series_uri)
        activity = map_ns[f"ValidationActivity_r{assertion.revision_number}"]
        ifc_snapshot = map_ns[f"IFCSnapshot_r{assertion.revision_number}"]
        rdf_snapshot = map_ns[f"RDFSnapshot_r{assertion.revision_number}"]
        graph.add((series, RDF.type, map_ns.MappingSeries))
        graph.add((aid, RDF.type, map_ns.MappingAssertion))
        graph.add((aid, map_ns.revisionNumber, Literal(assertion.revision_number)))
        graph.add((aid, map_ns.semanticStatus, Literal(assertion.semantic_status)))
        graph.add((aid, map_ns.linkStatus, Literal(getattr(assertion, "link_status", assertion.technical_link_state))))
        graph.add((aid, map_ns.dataStatus, Literal(getattr(assertion, "data_status", "PASS"))))
        graph.add((aid, prov_ns.wasGeneratedBy, activity))
        graph.add((activity, RDF.type, prov_ns.Activity))
        graph.add((activity, prov_ns.used, ifc_snapshot))
        graph.add((activity, prov_ns.used, rdf_snapshot))
        graph.add((ifc_snapshot, RDF.type, map_ns.IFCElementSnapshot))
        graph.add((rdf_snapshot, RDF.type, map_ns.RDFRecordSnapshot))
        if assertion.assignment_snapshot:
            assignment = map_ns[f"ControlledAssignment_r{assertion.revision_number}"]
            values = assertion.assignment_snapshot.values
            graph.add((assignment, RDF.type, map_ns.ControlledSampleAssignment))
            graph.add((assignment, map_ns.assignmentId, Literal(values.get("assignment_id", ""))))
            graph.add((assignment, map_ns.assignmentProtocol, Literal(values.get("protocol_id", ""))))
            graph.add((assignment, map_ns.assignmentMethod, Literal(values.get("assignment_method", ""))))
            graph.add((assignment, map_ns.assignedWallGlobalId, Literal(values.get("wall_global_id", ""))))
            graph.add((assignment, map_ns.assignedRecord, URIRef(values.get("record_uri", ""))))
            graph.add((activity, prov_ns.used, assignment))
        if assertion.previous_revision:
            graph.add((aid, prov_ns.wasRevisionOf, map_ns[f"MappingAssertion_r{assertion.previous_revision}"]))
        else:
            graph.add((aid, map_ns.belongsTo, series))
        # Persist change events so the RDF export retains full change awareness
        for index, event in enumerate(getattr(assertion, "change_events", []) or []):
            change = map_ns[f"ChangeEvent_r{assertion.revision_number}_{index}"]
            graph.add((change, RDF.type, map_ns.ChangeEvent))
            graph.add((change, map_ns.changeCategory, Literal(event.category)))
            graph.add((change, map_ns.changeSide, Literal(event.side)))
            graph.add((change, map_ns.changeField, Literal(event.field)))
            graph.add((change, map_ns.oldValue, Literal(str(event.old_value))))
            graph.add((change, map_ns.newValue, Literal(str(event.new_value))))
            graph.add((aid, map_ns.hasChangeEvent, change))
    return graph.serialize(format="turtle")
