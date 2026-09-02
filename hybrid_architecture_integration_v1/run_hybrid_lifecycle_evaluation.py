from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from association_lifecycle import series_uri


def nominal_value_text(value) -> str:
    if value is None:
        return ""
    wrapped = getattr(value, "wrappedValue", None)
    return str(wrapped if wrapped is not None else value)


def inspect_ifc_hybrid_links(ifc_path: Path, global_id: str, identification: str | None = None) -> dict:
    try:
        import ifcopenshell
    except ImportError as e:
        raise RuntimeError("IfcOpenShell is required. Run inside the thesis .venv.") from e

    model = ifcopenshell.open(str(ifc_path))
    wall = model.by_guid(global_id)
    if wall is None:
        raise RuntimeError(f"IFC element with GlobalId {global_id} was not found in {ifc_path}")

    refs = []
    hft = None
    for rel in model.get_inverse(wall):
        try:
            rtype = rel.is_a()
        except Exception:
            continue

        if rtype == "IfcRelAssociatesDocument":
            doc = getattr(rel, "RelatingDocument", None)
            if doc is None or doc.is_a() != "IfcDocumentReference":
                continue
            row = {
                "relation_step_id": rel.id(),
                "document_step_id": doc.id(),
                "location": str(getattr(doc, "Location", "") or ""),
                "identification": str(getattr(doc, "Identification", "") or ""),
                "name": str(getattr(doc, "Name", "") or ""),
                "description": str(getattr(doc, "Description", "") or ""),
            }
            if row["location"]:
                refs.append(row)

        elif rtype == "IfcRelDefinesByProperties":
            pset = getattr(rel, "RelatingPropertyDefinition", None)
            if pset is None or pset.is_a() != "IfcPropertySet":
                continue
            if str(getattr(pset, "Name", "") or "") != "HFT_AcousticLink":
                continue
            props = {}
            for prop in getattr(pset, "HasProperties", None) or []:
                props[str(getattr(prop, "Name", "") or "")] = nominal_value_text(getattr(prop, "NominalValue", None))
            hft = {"pset_step_id": pset.id(), "properties": props}

    candidates = refs
    if identification:
        candidates = [r for r in refs if r["identification"] == identification]
    elif len(refs) > 1:
        acoustic = [r for r in refs if "acoustic" in (r["name"] + " " + r["description"]).lower()]
        if len(acoustic) == 1:
            candidates = acoustic

    if not candidates:
        raise RuntimeError(
            "No IFC-native IfcDocumentReference with a Location URI was found for the target wall. "
            "Build the hybrid IFC first or specify --native-reference-identification."
        )
    if len(candidates) != 1:
        raise RuntimeError(
            f"Found {len(candidates)} candidate native document references for the wall. "
            "Use --native-reference-identification to select one explicitly."
        )

    return {
        "wall": {"global_id": str(wall.GlobalId), "name": str(getattr(wall, "Name", "") or ""), "step_id": wall.id()},
        "selected_native_reference": candidates[0],
        "all_native_references": refs,
        "hft_semantic_anchor": hft,
    }


def registry_record_id(registry: Path, record_uri: str) -> str:
    g = Graph()
    if registry.exists():
        g.parse(registry, format="turtle")
        ident = next(g.objects(URIRef(record_uri), DCTERMS.identifier), None)
        if ident is not None:
            return str(ident)
    return record_uri.rstrip("/").rsplit("/", 1)[-1]


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Hybrid end-to-end evaluator: resolve the acoustic-record URI through the IFC-native "
            "IfcDocumentReference, verify the HFT_AcousticLink MappingSeries semantic anchor, then "
            "run the unchanged v7 lifecycle evaluator."
        )
    )
    p.add_argument("--ifc", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--association-graph", type=Path, required=True)
    p.add_argument("--global-id", required=True)
    p.add_argument("--native-reference-identification", default=None)
    p.add_argument("--require-hft-anchor", action="store_true")
    p.add_argument("--model-version", default=None)
    p.add_argument("--record-version", required=True)
    p.add_argument("--wall-thickness", type=float, default=None)
    p.add_argument("--thickness-tolerance", type=float, default=0.02)
    p.add_argument("--trigger", default="hybrid-lifecycle-evaluation")
    p.add_argument("--unavailable", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--schema", type=Path, default=Path(__file__).with_name("association_model_schema.ttl"))
    p.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args()

    links = inspect_ifc_hybrid_links(args.ifc, args.global_id, args.native_reference_identification)
    native = links["selected_native_reference"]
    record_uri = native["location"]
    record_id = registry_record_id(args.registry, record_uri)
    expected_series = str(series_uri(args.global_id, record_id))

    hft = links["hft_semantic_anchor"]
    hft_props = hft["properties"] if hft else {}
    mapping_series_uri = hft_props.get("MappingSeriesURI", "")
    forbidden = [k for k in ("AcousticRecordURI", "MappingStatus", "MappingBasis") if k in hft_props]

    checks = {
        "native_reference_found": True,
        "native_location_present": bool(record_uri),
        "hft_anchor_present": hft is not None,
        "mapping_series_uri_present": bool(mapping_series_uri),
        "mapping_series_matches_wall_record_pair": mapping_series_uri == expected_series if mapping_series_uri else False,
        "hft_does_not_duplicate_record_uri_or_mutable_status": not forbidden,
    }
    if args.require_hft_anchor and not all([
        checks["hft_anchor_present"],
        checks["mapping_series_uri_present"],
        checks["mapping_series_matches_wall_record_pair"],
        checks["hft_does_not_duplicate_record_uri_or_mutable_status"],
    ]):
        raise RuntimeError("HFT semantic-anchor verification failed: " + json.dumps(checks))

    output_path = args.json_out or args.association_graph.with_suffix(".evaluation.json")
    cmd = [
        sys.executable,
        str(Path(__file__).with_name("run_lifecycle_evaluation.py")),
        "--ifc", str(args.ifc),
        "--registry", str(args.registry),
        "--association-graph", str(args.association_graph),
        "--global-id", args.global_id,
        "--record-uri", record_uri,
        "--record-version", args.record_version,
        "--thickness-tolerance", str(args.thickness_tolerance),
        "--trigger", args.trigger,
        "--schema", str(args.schema),
        "--json-out", str(output_path),
    ]
    if args.model_version:
        cmd += ["--model-version", args.model_version]
    if args.wall_thickness is not None:
        cmd += ["--wall-thickness", str(args.wall_thickness)]
    if args.unavailable:
        cmd.append("--unavailable")
    if args.force:
        cmd.append("--force")

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    report["input"]["record_uri_source"] = "IfcDocumentReference.Location"
    report["input"]["record_uri_manual_argument_used"] = False
    report["hybrid_link_validation"] = {
        "selected_native_reference": native,
        "record_id_resolved_from_registry_or_uri": record_id,
        "expected_mapping_series_uri": expected_series,
        "hft_semantic_anchor": hft,
        "forbidden_duplicated_hft_properties": forbidden,
        "checks": checks,
        "overall_pass": (
            checks["native_reference_found"]
            and checks["native_location_present"]
            and (not args.require_hft_anchor or (
                checks["hft_anchor_present"]
                and checks["mapping_series_uri_present"]
                and checks["mapping_series_matches_wall_record_pair"]
                and checks["hft_does_not_duplicate_record_uri_or_mutable_status"]
            ))
        ),
        "architecture_interpretation": (
            "IfcDocumentReference.Location is the authoritative technical acoustic-record URI. "
            "HFT_AcousticLink provides only the stable semantic MappingSeries anchor. "
            "Mutable status, rationale, evidence and revision history remain in the external RDF association graph."
        ),
    }
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nHybrid evaluation report: {output_path}")
    print("Hybrid architecture check:", "PASS" if report["hybrid_link_validation"]["overall_pass"] else "FAIL")


if __name__ == "__main__":
    main()
