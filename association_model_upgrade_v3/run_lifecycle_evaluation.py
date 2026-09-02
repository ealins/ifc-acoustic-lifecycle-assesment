from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from association_lifecycle import (
    BASE,
    MAP,
    WallEvidence,
    RecordEvidence,
    create_assertion,
    current_rows,
    load_graph,
    save_graph,
    semantic_assessment,
    series_uri,
    status_name,
)

AC = Namespace("https://example.org/hft-acoustic/vocab/")


def family_from_text(text: str) -> str:
    s = text.lower()
    groups = {
        "metal_frame": ["metal stud", "metal frame", "metallständ", "metalständ", "cw75", "steel stud"],
        "concrete": ["concrete", "beton"],
        "wood": ["wood", "timber", "holz", "cerezo", "clt", "cross laminated"],
    }
    for family, terms in groups.items():
        if any(t in s for t in terms):
            return family
    return "unknown"


def material_names_from_select(mat: Any) -> list[str]:
    if mat is None:
        return []
    out: list[str] = []
    seen: set[int] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        try:
            oid = obj.id()
        except Exception:
            oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)

        try:
            typ = obj.is_a()
        except Exception:
            typ = ""

        if typ == "IfcMaterial":
            name = getattr(obj, "Name", None)
            if name:
                out.append(str(name))

        for attr in (
            "ForLayerSet", "MaterialLayers", "Material", "Materials",
            "ForProfileSet", "MaterialProfiles", "Profiles",
            "ForConstituentSet", "MaterialConstituents", "Constituents",
        ):
            val = getattr(obj, attr, None)
            if val is None:
                continue
            if isinstance(val, (tuple, list)):
                for item in val:
                    visit(item)
            else:
                visit(val)

        for attr in ("Name", "Category"):
            val = getattr(obj, attr, None)
            if val and typ != "IfcMaterial":
                out.append(str(val))

    visit(mat)
    return list(dict.fromkeys(x.strip() for x in out if x and x.strip()))


def layer_thickness_from_select(mat: Any) -> float | None:
    """Best-effort IFC material-layer thickness extraction; returns metres."""
    if mat is None:
        return None
    try:
        typ = mat.is_a()
    except Exception:
        typ = ""

    layer_set = None
    if typ == "IfcMaterialLayerSetUsage":
        layer_set = getattr(mat, "ForLayerSet", None)
    elif typ == "IfcMaterialLayerSet":
        layer_set = mat
    elif typ == "IfcMaterialLayerSetWithOffsets":
        layer_set = mat

    if layer_set is None:
        return None

    layers = getattr(layer_set, "MaterialLayers", None) or []
    vals: list[float] = []
    for layer in layers:
        t = getattr(layer, "LayerThickness", None)
        if t is not None:
            try:
                vals.append(float(t))
            except Exception:
                pass
    return sum(vals) if vals else None


def extract_wall(ifc_path: Path, global_id: str, model_version: str, thickness_override: float | None) -> WallEvidence:
    try:
        import ifcopenshell
    except ImportError as e:
        raise RuntimeError("IfcOpenShell is required. Run this inside the thesis .venv where ifcopenshell is installed.") from e

    model = ifcopenshell.open(str(ifc_path))
    wall = model.by_guid(global_id)
    if wall is None:
        raise RuntimeError(f"IFC element with GlobalId {global_id} was not found in {ifc_path}")

    material_names: list[str] = []
    type_name = ""
    thickness_candidates: list[float] = []

    def add_material(mat: Any) -> None:
        material_names.extend(material_names_from_select(mat))
        t = layer_thickness_from_select(mat)
        if t is not None:
            thickness_candidates.append(t)

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
                            add_material(getattr(inv, "RelatingMaterial", None))
                    except Exception:
                        pass
        elif rtype == "IfcRelAssociatesMaterial":
            add_material(getattr(rel, "RelatingMaterial", None))

    material_names = list(dict.fromkeys(m for m in material_names if m))
    evidence_text = " | ".join([
        str(getattr(wall, "Name", "") or ""),
        str(getattr(wall, "ObjectType", "") or ""),
        type_name,
        *material_names,
    ])
    family = family_from_text(evidence_text)
    thickness = thickness_override
    if thickness is None and thickness_candidates:
        # If repeated inverse/type paths give the same layer set, prefer the most frequent rounded value.
        rounded = [round(v, 6) for v in thickness_candidates if v > 0]
        if rounded:
            thickness = max(set(rounded), key=rounded.count)

    return WallEvidence(
        global_id=str(wall.GlobalId),
        name=str(getattr(wall, "Name", "") or ""),
        construction_family=family,
        total_thickness_m=thickness,
        material_evidence=material_names,
        model_version=model_version,
    )


def _literal_str(g: Graph, subject, predicate) -> str:
    obj = next(g.objects(subject, predicate), None)
    return str(obj) if obj is not None else ""


def _literal_float(g: Graph, subject, predicate) -> float | None:
    obj = next(g.objects(subject, predicate), None)
    if obj is None:
        return None
    try:
        return float(obj)
    except Exception:
        return None


def parse_record(registry_path: Path, record_uri: str, record_version: str, force_unavailable: bool) -> RecordEvidence:
    g = Graph()
    if not force_unavailable:
        g.parse(registry_path, format="turtle")
    rec = URIRef(record_uri)

    if force_unavailable or not any(g.triples((rec, None, None))):
        identifier = record_uri.rstrip("/").rsplit("/", 1)[-1]
        return RecordEvidence(
            uri=record_uri, identifier=identifier, assembly="", construction_family="unknown",
            total_thickness_m=None, record_version=record_version, available=False,
            derived_from=[], generated_by=[], layers=[]
        )

    identifier = str(next(g.objects(rec, DCTERMS.identifier), Literal(record_uri.rstrip("/").rsplit("/", 1)[-1])))
    component = next(g.objects(rec, AC.describesComponent), None)

    assembly = ""
    construction = ""
    thickness = None
    layers: list[dict] = []
    component_uri = str(component or "")
    if component is not None:
        assembly = _literal_str(g, component, DCTERMS.title)
        construction = _literal_str(g, component, AC.constructionType)
        thickness = _literal_float(g, component, AC.totalThickness_m)
        for layer in g.objects(component, AC.hasLayer):
            pos_obj = next(g.objects(layer, AC.layerPosition), None)
            try:
                pos = int(pos_obj) if pos_obj is not None else 999
            except Exception:
                pos = 999
            layers.append({
                "position": pos,
                "name": _literal_str(g, layer, AC.layerName),
                "category": _literal_str(g, layer, AC.materialCategory),
                "thickness_m": _literal_float(g, layer, AC.thickness_m),
            })
        layers.sort(key=lambda x: (x["position"], x["name"]))

    source_org = next(g.objects(rec, AC.sourceOrganisation), None)
    derived = sorted(str(x) for x in g.objects(rec, PROV.wasDerivedFrom))
    generated = sorted(str(x) for x in g.objects(rec, PROV.wasGeneratedBy))

    return RecordEvidence(
        uri=record_uri,
        identifier=identifier,
        assembly=assembly,
        construction_family=family_from_text(construction),
        total_thickness_m=thickness,
        record_version=record_version,
        available=True,
        weighted_sound_reduction_index=_literal_float(g, rec, AC.weightedSoundReductionIndex),
        acoustic_unit=_literal_str(g, rec, AC.acousticUnit),
        test_area_m2=_literal_float(g, rec, AC.testArea_m2),
        surface_mass_kg_m2=_literal_float(g, rec, AC.surfaceMass_kg_m2),
        data_year=_literal_str(g, rec, AC.dataYear),
        source_organisation=str(source_org or ""),
        source_reference=_literal_str(g, rec, AC.sourceReference),
        source_type=_literal_str(g, rec, AC.sourceType),
        source_note=_literal_str(g, rec, AC.sourceNote),
        derived_from=derived,
        generated_by=generated,
        component_uri=component_uri,
        layers=layers,
    )


def fingerprint(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


EVIDENCE_MODEL_VERSION = "2"


def wall_hash(w: WallEvidence) -> str:
    return fingerprint({
        "evidence_model_version": EVIDENCE_MODEL_VERSION,
        "global_id": w.global_id,
        "name": w.name,
        "family": w.construction_family,
        "thickness_m": w.total_thickness_m,
        "materials": sorted(w.material_evidence),
        "model_version": w.model_version,
    })


def record_hash(r: RecordEvidence) -> str:
    return fingerprint({
        "evidence_model_version": EVIDENCE_MODEL_VERSION,
        "uri": r.uri,
        "id": r.identifier,
        "assembly": r.assembly,
        "family": r.construction_family,
        "thickness_m": r.total_thickness_m,
        "record_version": r.record_version,
        "available": r.available,
        "weighted_sound_reduction_index": r.weighted_sound_reduction_index,
        "acoustic_unit": r.acoustic_unit,
        "test_area_m2": r.test_area_m2,
        "surface_mass_kg_m2": r.surface_mass_kg_m2,
        "data_year": r.data_year,
        "source_organisation": r.source_organisation,
        "source_reference": r.source_reference,
        "source_type": r.source_type,
        "source_note": r.source_note,
        "derived_from": sorted(r.derived_from or []),
        "generated_by": sorted(r.generated_by or []),
        "component_uri": r.component_uri,
        "layers": sorted(r.layers or [], key=lambda x: (x.get("position", 999), x.get("name", ""))),
    })


def latest_assertion(g: Graph, wall_id: str, record_id: str):
    s = series_uri(wall_id, record_id)
    return s, g.value(s, MAP.currentAssertion)


def last_nonbroken_status(g: Graph, wall_id: str, record_uri: str) -> str | None:
    wall_ref = URIRef(f"{BASE}ifc/element/{wall_id}")
    record_ref = URIRef(record_uri)
    candidates = []
    for a in g.subjects(RDF.type, MAP.MappingAssertion):
        if g.value(a, MAP.ifcElement) != wall_ref or g.value(a, MAP.acousticRecord) != record_ref:
            continue
        st = status_name(g, a)
        if st == "BROKEN":
            continue
        ts = str(g.value(a, MAP.assessedAt) or "")
        candidates.append((ts, st))
    candidates.sort()
    return candidates[-1][1] if candidates else None


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate a real IFC-to-acoustic-record association and append a lifecycle assertion only when state/evidence changes.")
    p.add_argument("--ifc", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--association-graph", type=Path, required=True)
    p.add_argument("--global-id", required=True)
    p.add_argument("--record-uri", required=True)
    p.add_argument("--model-version", default=None, help="Defaults to IFC filename stem.")
    p.add_argument("--record-version", required=True)
    p.add_argument("--wall-thickness", type=float, default=None, help="Optional documented IFC-side thickness in metres; overrides best-effort material-layer extraction.")
    p.add_argument("--thickness-tolerance", type=float, default=0.02)
    p.add_argument("--trigger", default="lifecycle-evaluation")
    p.add_argument("--unavailable", action="store_true", help="Simulate/record external registry resource unavailability without changing the IFC-side URI.")
    p.add_argument("--force", action="store_true", help="Create a new assertion even if no meaningful evidence/state change is detected.")
    p.add_argument("--schema", type=Path, default=Path(__file__).with_name("association_model_schema.ttl"))
    p.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args()

    model_version = args.model_version or args.ifc.stem
    wall = extract_wall(args.ifc, args.global_id, model_version, args.wall_thickness)
    record = parse_record(args.registry, args.record_uri, args.record_version, args.unavailable)

    g = load_graph(args.association_graph if args.association_graph.exists() else None, args.schema)
    s, current = latest_assertion(g, wall.global_id, record.identifier)
    previous_status = status_name(g, current)

    proposed_status, rationale = semantic_assessment(
        wall, record, previous_status=previous_status, thickness_tolerance_m=args.thickness_tolerance
    )

    # General lifecycle rule: if an earlier non-broken association was ACCEPTABLE and the
    # same stable URI now resolves but current evidence is no longer acceptable, expose that
    # as SEMANTICALLY_STALE rather than silently downgrading it.
    prior_semantic = last_nonbroken_status(g, wall.global_id, record.uri)
    if record.available and prior_semantic == "ACCEPTABLE" and proposed_status in {"AMBIGUOUS", "INVALID"}:
        proposed_status = "SEMANTICALLY_STALE"
        rationale = (
            "The stable external identifier still resolves, but an association that was previously "
            "acceptable no longer satisfies the current semantic correspondence assessment. " + rationale
        )

    wh = wall_hash(wall)
    rh = record_hash(record)

    old_wh = str(g.value(current, MAP.wallEvidenceHash) or "") if current else ""
    old_rh = str(g.value(current, MAP.recordEvidenceHash) or "") if current else ""
    old_status = status_name(g, current) if current else None
    old_rationale = str(g.value(current, MAP.rationale) or "") if current else ""

    changed = (
        current is None
        or wh != old_wh
        or rh != old_rh
        or proposed_status != old_status
        or rationale != old_rationale
    )

    report = {
        "input": {
            "ifc": str(args.ifc),
            "registry": str(args.registry),
            "association_graph": str(args.association_graph),
            "global_id": args.global_id,
            "record_uri": args.record_uri,
        },
        "wall_evidence": asdict(wall),
        "record_evidence": asdict(record),
        "previous": {
            "assertion": str(current or ""),
            "status": old_status,
            "wall_evidence_hash": old_wh,
            "record_evidence_hash": old_rh,
        },
        "evaluation": {
            "evidence_model_version": EVIDENCE_MODEL_VERSION,
            "status": proposed_status,
            "rationale": rationale,
            "technical_resolution": record.available,
            "wall_evidence_hash": wh,
            "record_evidence_hash": rh,
            "meaningful_change": changed,
        },
    }

    if changed or args.force:
        new_a = create_assertion(
            g,
            wall,
            record,
            trigger=args.trigger,
            status_override=proposed_status,
            rationale_override=rationale,
            wall_evidence_hash=wh,
            record_evidence_hash=rh,
            ifc_reference_location=record.uri,
            link_carrier="IfcDocumentReference",
        )
        save_graph(g, args.association_graph)
        report["action"] = "created_revision"
        report["created_assertion"] = str(new_a)
    else:
        report["action"] = "no_change_no_revision"
        report["created_assertion"] = None

    report["current"] = [r for r in current_rows(g) if r["ifc_global_id"] == wall.global_id and r["record_uri"] == record.uri]

    out = args.json_out or args.association_graph.with_suffix(".evaluation.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote evaluation report: {out}")
    if report["action"] == "created_revision":
        print(f"Updated lifecycle graph: {args.association_graph}")
    else:
        print("No RDF revision was added because the current evidence/state is unchanged.")


if __name__ == "__main__":
    main()
