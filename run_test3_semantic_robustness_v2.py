from __future__ import annotations

import argparse
import csv
import json
import re
from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import ifcopenshell
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

AC = Namespace("https://example.org/hft-acoustic/vocab/")
REAL_RECORD_URI = "https://example.org/hft-acoustic/record/vabdat-310"
SYNTHETIC_DUP_RECORD_URI = "https://example.org/hft-acoustic/record/control-vabdat-310-near-duplicate"

# These thicknesses are documented IFC-side evidence established during the
# earlier Bau 1 inspection. They are inputs to the correspondence assessment;
# they are NOT expected classifications.
ACTUAL_WALLS = {
    "pilot_metal_stud": {
        "global_id": "2qL6OSUnz6ZAzEOn1HxeD2",
        "documented_total_thickness_m": 0.285,
    },
    "concrete_150": {
        "global_id": "0wnAJp1nDEywwo7Vo$xbfn",
        "documented_total_thickness_m": 0.150,
    },
    "concrete_300": {
        "global_id": "1You9r7r15Ax77pHYWcjAi",
        "documented_total_thickness_m": 0.300,
    },
    "wood_100": {
        "global_id": "3jVfQlWajACA3M083XXgEN",
        "documented_total_thickness_m": 0.100,
    },
}


@dataclass
class WallSignature:
    source: str
    global_id: str
    name: str
    type_name: str
    construction_family: str
    total_thickness_m: float | None
    material_names: list[str]
    evidence_text: str


@dataclass
class RecordSignature:
    uri: str
    identifier: str
    assembly: str
    construction: str
    construction_family: str
    total_thickness_m: float | None
    layer_names: list[str]
    layer_categories: list[str]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def family_from_text(text: str) -> str:
    s = text.lower()
    metal_terms = ["metal stud", "metal frame", "metallständ", "metalständ", "cw75", "steel stud"]
    concrete_terms = ["concrete", "beton"]
    wood_terms = ["wood", "timber", "holz", "cerezo", "clt", "cross laminated"]
    if any(t in s for t in metal_terms):
        return "metal_frame"
    if any(t in s for t in concrete_terms):
        return "concrete"
    if any(t in s for t in wood_terms):
        return "wood"
    return "unknown"


def normalise_tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "with", "layer", "construction", "wall", "generic", "basic",
        "of", "a", "an", "m", "mm", "mit", "und", "bauplatte",
    }
    tokens = set(re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text.lower()))
    return {t for t in tokens if len(t) >= 3 and t not in stop}


def material_names_from_select(mat: Any) -> list[str]:
    if mat is None:
        return []
    out: list[str] = []
    seen_ids: set[int] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        try:
            oid = obj.id()
        except Exception:
            oid = id(obj)
        if oid in seen_ids:
            return
        seen_ids.add(oid)

        try:
            typ = obj.is_a()
        except Exception:
            typ = type(obj).__name__

        if typ == "IfcMaterial":
            name = getattr(obj, "Name", None)
            if name:
                out.append(str(name))
            return

        # Traverse the common IFC material-select containers.
        attrs = [
            "Material", "ForLayerSet", "MaterialLayers", "Materials",
            "MaterialConstituents", "MaterialProfiles", "ForProfileSet",
        ]
        for attr in attrs:
            val = getattr(obj, attr, None)
            if val is None:
                continue
            if isinstance(val, (tuple, list)):
                for item in val:
                    visit(item)
            else:
                visit(val)

        # Layer/profile names themselves can contain useful semantic evidence.
        for attr in ("Name", "Category"):
            val = getattr(obj, attr, None)
            if val and typ != "IfcMaterial":
                out.append(str(val))

    visit(mat)
    # preserve order, remove blanks/duplicates
    unique = []
    seen = set()
    for x in out:
        x = x.strip()
        if x and x not in seen:
            unique.append(x)
            seen.add(x)
    return unique


def extract_wall_signature(model: Any, key: str) -> WallSignature:
    cfg = ACTUAL_WALLS[key]
    wall = model.by_guid(cfg["global_id"])
    if wall is None:
        raise RuntimeError(f"Wall {cfg['global_id']} not found")

    type_name = ""
    material_names: list[str] = []

    # Inverse relationships are robust across IFC4/IFC4x3 exports.
    for rel in model.get_inverse(wall):
        try:
            rtype = rel.is_a()
        except Exception:
            continue
        if rtype == "IfcRelDefinesByType":
            typ = getattr(rel, "RelatingType", None)
            if typ is not None:
                type_name = str(getattr(typ, "Name", "") or "")
                for inv in model.get_inverse(typ):
                    try:
                        if inv.is_a() == "IfcRelAssociatesMaterial":
                            material_names.extend(material_names_from_select(getattr(inv, "RelatingMaterial", None)))
                    except Exception:
                        pass
        elif rtype == "IfcRelAssociatesMaterial":
            material_names.extend(material_names_from_select(getattr(rel, "RelatingMaterial", None)))

    # Deduplicate material evidence.
    material_names = list(dict.fromkeys([m for m in material_names if m]))

    text_parts = [
        str(getattr(wall, "Name", "") or ""),
        str(getattr(wall, "ObjectType", "") or ""),
        type_name,
        *material_names,
    ]
    evidence_text = " | ".join(x for x in text_parts if x)
    family = family_from_text(evidence_text)

    return WallSignature(
        source="ACTUAL_IFC",
        global_id=str(wall.GlobalId),
        name=str(getattr(wall, "Name", "") or ""),
        type_name=type_name,
        construction_family=family,
        total_thickness_m=cfg["documented_total_thickness_m"],
        material_names=material_names,
        evidence_text=evidence_text,
    )


def parse_records(graph: Graph) -> dict[str, RecordSignature]:
    records: dict[str, RecordSignature] = {}
    for rec in graph.subjects(RDF.type, AC.AcousticPerformanceRecord):
        component = next(graph.objects(rec, AC.describesComponent), None)
        if component is None:
            continue
        title = next(graph.objects(component, DCTERMS.title), Literal(""))
        construction = next(graph.objects(component, AC.constructionType), Literal(""))
        thickness = next(graph.objects(component, AC.totalThickness_m), None)
        identifier = next(graph.objects(rec, DCTERMS.identifier), Literal(str(rec)))

        layers: list[tuple[int, str, str]] = []
        for layer in graph.objects(component, AC.hasLayer):
            pos = next(graph.objects(layer, AC.layerPosition), Literal(999))
            name = next(graph.objects(layer, AC.layerName), Literal(""))
            cat = next(graph.objects(layer, AC.materialCategory), Literal(""))
            try:
                pos_i = int(pos)
            except Exception:
                pos_i = 999
            layers.append((pos_i, str(name), str(cat)))
        layers.sort(key=lambda x: x[0])

        records[str(rec)] = RecordSignature(
            uri=str(rec),
            identifier=str(identifier),
            assembly=str(title),
            construction=str(construction),
            construction_family=family_from_text(str(construction)),
            total_thickness_m=float(thickness) if thickness is not None else None,
            layer_names=[x[1] for x in layers],
            layer_categories=[x[2] for x in layers],
        )
    return records


def layer_overlap(wall: WallSignature, record: RecordSignature) -> float:
    if not wall.material_names or not record.layer_names:
        return 0.0
    wall_tokens = normalise_tokens(" ".join(wall.material_names))
    record_tokens = normalise_tokens(" ".join(record.layer_names + record.layer_categories))
    if not wall_tokens or not record_tokens:
        return 0.0
    return len(wall_tokens & record_tokens) / max(1, len(record_tokens))


def assess_pair(wall: WallSignature, record: RecordSignature, thickness_tol_m: float = 0.02) -> tuple[str, str, dict[str, Any]]:
    metrics: dict[str, Any] = {
        "wall_family": wall.construction_family,
        "record_family": record.construction_family,
        "wall_thickness_m": wall.total_thickness_m,
        "record_thickness_m": record.total_thickness_m,
        "thickness_delta_m": None,
        "layer_token_overlap": layer_overlap(wall, record),
    }

    if wall.construction_family == "unknown":
        return "AMBIGUOUS", "IFC evidence is insufficient to determine the wall construction family.", metrics
    if record.construction_family == "unknown":
        return "AMBIGUOUS", "The external record does not expose a recognizable construction family.", metrics
    if wall.construction_family != record.construction_family:
        return (
            "INVALID",
            f"Construction-family mismatch: IFC wall={wall.construction_family}, external record={record.construction_family}.",
            metrics,
        )

    if wall.total_thickness_m is not None and record.total_thickness_m is not None:
        delta = abs(wall.total_thickness_m - record.total_thickness_m)
        metrics["thickness_delta_m"] = delta
    else:
        delta = None

    thickness_ok = delta is not None and delta <= thickness_tol_m
    layers_ok = metrics["layer_token_overlap"] >= 0.35

    if thickness_ok and layers_ok:
        return (
            "ACCEPTABLE",
            "Construction family agrees and both thickness and material/layer evidence are compatible within the controlled criteria.",
            metrics,
        )

    reasons = []
    if delta is None:
        reasons.append("comparable total thickness is unavailable")
    elif not thickness_ok:
        reasons.append(f"total-thickness difference is {delta:.3f} m (> {thickness_tol_m:.3f} m tolerance)")
    if not layers_ok:
        reasons.append("IFC material/layer evidence is insufficient to reproduce the tested assembly")
    return "AMBIGUOUS", "; ".join(reasons) + ".", metrics


def discover_candidates(wall: WallSignature, records: dict[str, RecordSignature]) -> list[RecordSignature]:
    """Coarse candidate discovery only. Final correspondence is assessed separately."""
    if wall.construction_family == "unknown":
        return []
    return [r for r in records.values() if r.construction_family == wall.construction_family]


def evaluate_link(
    wall: WallSignature,
    records: dict[str, RecordSignature],
    linked_uri: str | None,
    prior_wall: WallSignature | None = None,
) -> tuple[str, str, dict[str, Any]]:
    # Explicit reference path: first test technical resolution, then semantics.
    if linked_uri:
        record = records.get(linked_uri)
        if record is None:
            return (
                "BROKEN",
                "The IFC/reference identifier is retained, but the referenced external record is unavailable in the registry.",
                {"linked_uri": linked_uri, "technical_resolution": False},
            )

        current_status, current_reason, metrics = assess_pair(wall, record)
        metrics = {"linked_uri": linked_uri, "technical_resolution": True, **metrics}

        if prior_wall is not None:
            prior_status, prior_reason, prior_metrics = assess_pair(prior_wall, record)
            metrics["prior_correspondence_status"] = prior_status
            metrics["prior_correspondence_reason"] = prior_reason
            metrics["prior_wall_family"] = prior_wall.construction_family
            metrics["prior_wall_thickness_m"] = prior_wall.total_thickness_m
            if prior_status == "ACCEPTABLE" and current_status == "INVALID":
                return (
                    "SEMANTICALLY_STALE",
                    "The same identifier still resolves, but an association that was acceptable in the prior model state is incompatible with the current wall state.",
                    metrics,
                )

        return current_status, current_reason, metrics

    # No explicit link: test candidate discovery behaviour.
    candidates = discover_candidates(wall, records)
    if len(candidates) == 0:
        return (
            "UNMATCHED",
            "No external record with the same detectable construction family is available as a candidate.",
            {"candidate_count": 0, "candidate_uris": []},
        )
    if len(candidates) > 1:
        return (
            "MULTIPLE_CANDIDATES",
            "More than one external record passes the coarse construction-family candidate filter; additional evidence is required for unique selection.",
            {"candidate_count": len(candidates), "candidate_uris": [r.uri for r in candidates]},
        )

    status, reason, metrics = assess_pair(wall, candidates[0])
    return status, "One candidate was discovered. " + reason, {"candidate_count": 1, "candidate_uris": [candidates[0].uri], **metrics}


def controlled_exact_wall(record: RecordSignature, global_id: str, name: str) -> WallSignature:
    return WallSignature(
        source="CONTROLLED_FIXTURE",
        global_id=global_id,
        name=name,
        type_name="Controlled fixture",
        construction_family=record.construction_family,
        total_thickness_m=record.total_thickness_m,
        material_names=list(record.layer_names),
        evidence_text=" | ".join(record.layer_names),
    )


def add_synthetic_near_duplicate(graph: Graph, source_record: RecordSignature) -> None:
    """Add an explicitly synthetic second candidate to test non-unique candidate handling."""
    rec = URIRef(SYNTHETIC_DUP_RECORD_URI)
    comp = URIRef("https://example.org/hft-acoustic/component/control-vabdat-346-near-duplicate")
    graph.add((rec, RDF.type, AC.AcousticPerformanceRecord))
    graph.add((rec, DCTERMS.identifier, Literal("CONTROLLED-near-duplicate")))
    graph.add((rec, AC.describesComponent, comp))
    graph.add((comp, RDF.type, AC.WallAssembly))
    graph.add((comp, DCTERMS.title, Literal("CONTROLLED near-duplicate metal-frame assembly")))
    graph.add((comp, AC.constructionType, Literal(source_record.construction)))
    if source_record.total_thickness_m is not None:
        graph.add((comp, AC.totalThickness_m, Literal(source_record.total_thickness_m, datatype=XSD.decimal)))
    for idx, layer_name in enumerate(source_record.layer_names, start=1):
        layer = URIRef(f"https://example.org/hft-acoustic/layer/control-near-duplicate-{idx}")
        graph.add((comp, AC.hasLayer, layer))
        graph.add((layer, RDF.type, AC.MaterialLayer))
        graph.add((layer, AC.layerPosition, Literal(idx, datatype=XSD.integer)))
        graph.add((layer, AC.layerName, Literal(layer_name)))
        if idx - 1 < len(source_record.layer_categories):
            graph.add((layer, AC.materialCategory, Literal(source_record.layer_categories[idx - 1])))


def graph_without_record(original: Graph, record_uri: str) -> Graph:
    """Create a registry state in which the referenced record cannot be resolved."""
    g = Graph()
    for prefix, ns in original.namespaces():
        g.bind(prefix, ns)
    rec = URIRef(record_uri)
    # Remove all triples directly describing the record. Component/source triples may remain,
    # but the record identifier itself no longer resolves as an AcousticPerformanceRecord.
    for triple in original:
        if triple[0] != rec:
            g.add(triple)
    return g


def main() -> None:
    parser = argparse.ArgumentParser(description="Test 3 v2: non-circular semantic robustness scenarios.")
    script_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=script_dir / "data")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "final_test3_results_v2")
    args = parser.parse_args()

    data = args.data_dir.expanduser().resolve()
    out = args.results_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    ifc_path = data / "HFT_Bau1_2026.02.18.ifc"
    registry_path = data / "acoustic_registry_v1.ttl"
    for p in (ifc_path, registry_path):
        if not p.exists():
            raise SystemExit(f"Missing required input: {p}")

    print("=" * 92)
    print("TEST 3 v2 — MAPPING AND SEMANTIC ROBUSTNESS")
    print("=" * 92)
    print("Purpose: test correspondence states, not predict acoustic performance.")
    print("Expected labels are used only after classification for scenario checking; they are not inputs to the classifier.\n")

    model = ifcopenshell.open(str(ifc_path))
    actual = {key: extract_wall_signature(model, key) for key in ACTUAL_WALLS}

    base_graph = Graph()
    base_graph.parse(registry_path, format="turtle")
    base_records = parse_records(base_graph)
    if REAL_RECORD_URI not in base_records:
        raise RuntimeError(f"Expected source record not found: {REAL_RECORD_URI}")
    real_record = base_records[REAL_RECORD_URI]

    exact = controlled_exact_wall(real_record, "CONTROLLED-ACCEPTABLE-001", "Controlled exact assembly fixture")

    # Controlled registry states are generated from the real RDF record. They are clearly synthetic
    # and exist only to exercise candidate-selection/resource-resolution branches.
    duplicate_graph = Graph()
    for prefix, ns in base_graph.namespaces():
        duplicate_graph.bind(prefix, ns)
    for t in base_graph:
        duplicate_graph.add(t)
    add_synthetic_near_duplicate(duplicate_graph, real_record)
    duplicate_records = parse_records(duplicate_graph)
    duplicate_graph.serialize(out / "test3_control_registry_multiple_candidates.ttl", format="turtle")

    broken_graph = graph_without_record(base_graph, REAL_RECORD_URI)
    broken_records = parse_records(broken_graph)
    broken_graph.serialize(out / "test3_control_registry_record_unavailable.ttl", format="turtle")

    # Controlled semantic mutation: previous snapshot corresponds exactly to the record;
    # current snapshot retains the same object identity but changes the construction family.
    stale_current = deepcopy(exact)
    stale_current.source = "CONTROLLED_MODEL_VERSION_T1"
    stale_current.name = "Controlled same wall after construction-family change"
    stale_current.construction_family = "concrete"
    stale_current.material_names = ["Concrete"]
    stale_current.evidence_text = "Controlled model revision: construction changed to concrete"

    scenarios = [
        {
            "case_id": "controlled_acceptable",
            "case_kind": "CONTROLLED_POSITIVE_FIXTURE",
            "wall": exact,
            "records": base_records,
            "linked_uri": REAL_RECORD_URI,
            "prior_wall": None,
            "ground_truth": "ACCEPTABLE",
        },
        {
            "case_id": "actual_metal_stud_ambiguous",
            "case_kind": "ACTUAL_IFC_WALL",
            "wall": actual["pilot_metal_stud"],
            "records": base_records,
            "linked_uri": REAL_RECORD_URI,
            "prior_wall": None,
            "ground_truth": "AMBIGUOUS",
        },
        {
            "case_id": "actual_concrete_wrong_link",
            "case_kind": "ACTUAL_IFC_WALL_INTENTIONAL_WRONG_REFERENCE",
            "wall": actual["concrete_150"],
            "records": base_records,
            "linked_uri": REAL_RECORD_URI,
            "prior_wall": None,
            "ground_truth": "INVALID",
        },
        {
            "case_id": "actual_concrete_no_candidate",
            "case_kind": "ACTUAL_IFC_WALL_CANDIDATE_DISCOVERY",
            "wall": actual["concrete_300"],
            "records": base_records,
            "linked_uri": None,
            "prior_wall": None,
            "ground_truth": "UNMATCHED",
        },
        {
            "case_id": "controlled_multiple_candidates",
            "case_kind": "CONTROLLED_REGISTRY_EXTENSION",
            "wall": exact,
            "records": duplicate_records,
            "linked_uri": None,
            "prior_wall": None,
            "ground_truth": "MULTIPLE_CANDIDATES",
        },
        {
            "case_id": "external_record_unavailable",
            "case_kind": "CONTROLLED_RESOURCE_FAILURE",
            "wall": actual["pilot_metal_stud"],
            "records": broken_records,
            "linked_uri": REAL_RECORD_URI,
            "prior_wall": None,
            "ground_truth": "BROKEN",
        },
        {
            "case_id": "controlled_semantic_staleness",
            "case_kind": "CONTROLLED_MODEL_VERSION_CHANGE",
            "wall": stale_current,
            "records": base_records,
            "linked_uri": REAL_RECORD_URI,
            "prior_wall": exact,
            "ground_truth": "SEMANTICALLY_STALE",
        },
    ]

    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for scenario in scenarios:
        observed, rationale, metrics = evaluate_link(
            wall=scenario["wall"],
            records=scenario["records"],
            linked_uri=scenario["linked_uri"],
            prior_wall=scenario["prior_wall"],
        )
        passed = observed == scenario["ground_truth"]
        wall: WallSignature = scenario["wall"]
        rows.append({
            "case_id": scenario["case_id"],
            "case_kind": scenario["case_kind"],
            "wall_global_id": wall.global_id,
            "wall_name": wall.name,
            "ground_truth": scenario["ground_truth"],
            "observed_status": observed,
            "scenario_pass": passed,
            "linked_uri": scenario["linked_uri"] or "",
            "wall_construction_family": wall.construction_family,
            "wall_total_thickness_m": wall.total_thickness_m,
            "technical_resolution": metrics.get("technical_resolution", "N/A"),
            "candidate_count": metrics.get("candidate_count", "N/A"),
            "record_construction_family": metrics.get("record_family", "N/A"),
            "record_total_thickness_m": metrics.get("record_thickness_m", "N/A"),
            "thickness_delta_m": metrics.get("thickness_delta_m", "N/A"),
            "layer_token_overlap": metrics.get("layer_token_overlap", "N/A"),
            "rationale": rationale,
        })
        details.append({
            "case_id": scenario["case_id"],
            "case_kind": scenario["case_kind"],
            "ground_truth": scenario["ground_truth"],
            "observed_status": observed,
            "scenario_pass": passed,
            "wall_signature": asdict(wall),
            "prior_wall_signature": asdict(scenario["prior_wall"]) if scenario["prior_wall"] else None,
            "linked_uri": scenario["linked_uri"],
            "decision_metrics": metrics,
            "rationale": rationale,
        })

    write_csv(out / "test3_semantic_robustness_results.csv", rows)
    (out / "test3_semantic_robustness_details.json").write_text(
        json.dumps({
            "source_record": asdict(real_record),
            "actual_wall_signatures": {k: asdict(v) for k, v in actual.items()},
            "scenarios": details,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    n_pass = sum(bool(r["scenario_pass"]) for r in rows)
    summary_lines = [
        "TEST 3 v2 — SEMANTIC ROBUSTNESS SUMMARY",
        "",
        f"Source RDF record: {REAL_RECORD_URI}",
        f"Scenario agreement: {n_pass}/{len(rows)}",
        "",
        "Important interpretation:",
        "- This is a controlled scenario/decision-rule evaluation, not statistical validation of an acoustic-matching algorithm.",
        "- The real Bau 1 metal-stud case tests ambiguity from incomplete/non-equivalent assembly evidence.",
        "- The concrete wrong-link and no-candidate cases use actual IFC walls.",
        "- The positive, duplicate-candidate and semantic-staleness cases are explicitly controlled fixtures/mutations.",
        "- BROKEN means technical resolution failed; INVALID/AMBIGUOUS/STALE concern semantic correspondence.",
        "- No Rw value is predicted for any Bau 1 wall.",
    ]
    (out / "test3_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print("SOURCE RECORD")
    print(f"  Assembly:       {real_record.assembly}")
    print(f"  Construction:   {real_record.construction}")
    print(f"  Thickness:      {real_record.total_thickness_m} m")
    print(f"  Layer count:    {len(real_record.layer_names)}")

    print("\nACTUAL IFC SIGNATURES USED")
    for key, sig in actual.items():
        print(f"  {key:<20} family={sig.construction_family:<12} thickness={sig.total_thickness_m} materials={sig.material_names[:4]}")

    print("\nSEMANTIC ROBUSTNESS SCENARIOS")
    print(f"{'Case':<34} {'Ground truth':<24} {'Observed':<24} {'Pass'}")
    for row in rows:
        print(f"{row['case_id']:<34} {row['ground_truth']:<24} {row['observed_status']:<24} {row['scenario_pass']}")

    print(f"\nScenario agreement: {n_pass}/{len(rows)}")
    print("\nDo not interpret scenario agreement as statistical accuracy; the purpose is controlled robustness/decision-logic coverage.")
    print("RESULTS WRITTEN TO:", out)


if __name__ == "__main__":
    main()
