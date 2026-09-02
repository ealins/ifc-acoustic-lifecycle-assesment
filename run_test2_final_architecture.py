from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import ifcopenshell
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

# Reuse the already-tested pilot helpers. Keep this file beside run_experiment.py.
from run_experiment import (
    AC,
    PROV,
    WALL_GUID,
    RECORD_ID,
    RDF_RECORD_URI,
    NATIVE_RECORD_URI,
    UPDATED_RW,
    UPDATED_SOURCE_REFERENCE,
    UPDATED_VERSION,
    open_ifc,
    get_wall,
    get_pset_dict,
    find_native_reference,
    retrieve_embedded,
    retrieve_native,
    retrieve_rdf,
    embedded_update_value,
    embedded_update_source,
    ifc_metrics,
    success_count,
)

CUSTOM_LINK_PSET_NAMES = ("HFT_AcousticLink", "Pset_AcousticLink")
EMBEDDED_PSET_NAMES = ("HFT_AcousticEmbedded", "Pset_AcousticEmbedded")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def first_value(graph: Graph, subject: URIRef, predicate: URIRef):
    for value in graph.objects(subject, predicate):
        return value
    return None


def find_custom_link_pset(wall) -> tuple[str | None, dict[str, Any] | None]:
    for name in CUSTOM_LINK_PSET_NAMES:
        p = get_pset_dict(wall, name)
        if p:
            return name, p
    return None, None


def native_walls_pointing_to_uri(model, uri: str) -> list[dict[str, Any]]:
    walls = []
    for rel in model.by_type("IfcRelAssociatesDocument"):
        try:
            doc = rel.RelatingDocument
            if not doc or not doc.is_a("IfcDocumentReference"):
                continue
            if str(getattr(doc, "Location", "") or "") != uri:
                continue
            for obj in rel.RelatedObjects or []:
                if obj.is_a("IfcWall"):
                    walls.append({
                        "global_id": obj.GlobalId,
                        "step_id": obj.id(),
                        "name": obj.Name,
                        "record_uri": uri,
                    })
        except Exception:
            continue
    return walls


def custom_walls_pointing_to_uri(model, uri: str) -> list[dict[str, Any]]:
    walls = []
    for candidate in model.by_type("IfcWall"):
        _, p = find_custom_link_pset(candidate)
        if not p:
            continue
        if str(p.get("AcousticRecordURI") or "") != uri:
            continue
        walls.append({
            "global_id": candidate.GlobalId,
            "step_id": candidate.id(),
            "name": candidate.Name,
            "record_uri": uri,
            "mapping_status": p.get("MappingStatus"),
        })
    return walls


def rdf_record_questions(registry_path: Path, record_uri: str) -> dict[str, Any]:
    g = Graph()
    g.parse(registry_path, format="turtle")
    rec = URIRef(record_uri)
    if not any(True for _ in g.triples((rec, None, None))):
        return {"Q1": None, "Q2": None, "Q3": None, "Q4": None}

    component = first_value(g, rec, AC.describesComponent)
    source_org = first_value(g, rec, AC.sourceOrganisation)

    q1 = {
        "value": str(first_value(g, rec, AC.weightedSoundReductionIndex)) if first_value(g, rec, AC.weightedSoundReductionIndex) is not None else None,
        "unit": str(first_value(g, rec, AC.acousticUnit)) if first_value(g, rec, AC.acousticUnit) is not None else None,
        "metric": str(first_value(g, rec, AC.acousticMetric)) if first_value(g, rec, AC.acousticMetric) is not None else None,
    }

    q2 = {
        "assembly": str(first_value(g, component, DCTERMS.title)) if component and first_value(g, component, DCTERMS.title) is not None else None,
        "construction_type": str(first_value(g, component, AC.constructionType)) if component and first_value(g, component, AC.constructionType) is not None else None,
        "thickness_m": str(first_value(g, component, AC.totalThickness_m)) if component and first_value(g, component, AC.totalThickness_m) is not None else None,
        "test_area_m2": str(first_value(g, rec, AC.testArea_m2)) if first_value(g, rec, AC.testArea_m2) is not None else None,
    }

    q3 = {
        "responsible_agent": str(first_value(g, source_org, DCTERMS.title)) if source_org and first_value(g, source_org, DCTERMS.title) is not None else None,
        "source_reference": str(first_value(g, rec, AC.sourceReference)) if first_value(g, rec, AC.sourceReference) is not None else None,
        "derived_from": [str(v) for v in g.objects(rec, PROV.wasDerivedFrom)],
    }

    q4 = {
        "method": str(first_value(g, rec, AC.methodType)) if first_value(g, rec, AC.methodType) is not None else None,
        "date_year": str(first_value(g, rec, AC.dataYear)) if first_value(g, rec, AC.dataYear) is not None else None,
        "version": str(first_value(g, rec, DCTERMS.hasVersion)) if first_value(g, rec, DCTERMS.hasVersion) is not None else None,
    }

    return {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4}


def make_native_to_same_rdf_ifc(src_native_ifc: Path, dst: Path) -> None:
    model = open_ifc(src_native_ifc)
    wall = get_wall(model)
    doc = find_native_reference(model, wall)
    # Only the external target is changed. The linking mechanism remains IFC-native.
    doc.Location = RDF_RECORD_URI
    try:
        doc.Name = "Acoustic RDF record"
    except Exception:
        pass
    model.write(str(dst))


def retrieve_native_rdf(ifc_path: Path, registry_path: Path | None) -> tuple[dict[str, Any], str]:
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    doc = find_native_reference(model, wall)
    uri = str(doc.Location or "")
    q5 = native_walls_pointing_to_uri(model, uri)

    if registry_path is None or not registry_path.exists():
        return {"Q1": None, "Q2": None, "Q3": None, "Q4": None, "Q5": q5}, "BROKEN"

    q = rdf_record_questions(registry_path, uri)
    q["Q5"] = q5
    status = "VALID" if q["Q1"] is not None else "BROKEN"
    return q, status


def retrieve_custom_rdf_safe(ifc_path: Path, registry_path: Path | None) -> tuple[dict[str, Any], str]:
    if registry_path is not None and registry_path.exists():
        return retrieve_rdf(ifc_path, registry_path)

    # Corrected external-resource-unavailable test: do NOT alter the IFC-side URI.
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    _, p = find_custom_link_pset(wall)
    if not p:
        return {f"Q{i}": None for i in range(1, 6)}, "UNMATCHED"
    uri = str(p.get("AcousticRecordURI") or "")
    q5 = custom_walls_pointing_to_uri(model, uri)
    return {"Q1": None, "Q2": None, "Q3": None, "Q4": None, "Q5": q5}, "BROKEN"


def update_rdf_value(src: Path, dst: Path) -> None:
    g = Graph()
    g.parse(src, format="turtle")
    rec = URIRef(RDF_RECORD_URI)
    for triple in list(g.triples((rec, AC.weightedSoundReductionIndex, None))):
        g.remove(triple)
    g.add((rec, AC.weightedSoundReductionIndex, Literal(str(UPDATED_RW), datatype=XSD.decimal)))
    g.serialize(destination=str(dst), format="turtle")


def update_rdf_provenance(src: Path, dst: Path) -> None:
    g = Graph()
    g.parse(src, format="turtle")
    rec = URIRef(RDF_RECORD_URI)
    for triple in list(g.triples((rec, AC.sourceReference, None))):
        g.remove(triple)
    g.add((rec, AC.sourceReference, Literal(UPDATED_SOURCE_REFERENCE)))
    for triple in list(g.triples((rec, DCTERMS.hasVersion, None))):
        g.remove(triple)
    g.add((rec, DCTERMS.hasVersion, Literal(UPDATED_VERSION)))
    g.serialize(destination=str(dst), format="turtle")


def update_native_json_value(src: Path, dst: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    payload["record"]["AcousticValue"] = UPDATED_RW
    payload["control_test_note"] = "Controlled experimental update; not a source measurement."
    dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def update_native_json_provenance(src: Path, dst: Path) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    payload["record"]["SourceReference"] = UPDATED_SOURCE_REFERENCE
    payload["record"]["RecordVersion"] = UPDATED_VERSION
    dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def provenance_profile_json(json_path: Path) -> dict[str, Any]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))["record"]
    fields = [
        "ResponsibleAgent", "SourceReference", "SourceURI", "MethodType", "DataYear", "RecordVersion"
    ]
    return {
        "representation": "application-defined JSON key/value structure",
        "explicit_prov_o_predicates": 0,
        "provenance_fields_present": sum(1 for f in fields if payload.get(f) not in (None, "")),
        "note": "Provenance can be represented, but its semantics are defined by the application-specific JSON schema used in this experiment.",
    }


def provenance_profile_rdf(ttl_path: Path) -> dict[str, Any]:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    rec = URIRef(RDF_RECORD_URI)
    predicates = sorted({str(p) for _, p, _ in g.triples((rec, None, None)) if str(p).startswith(str(PROV))})
    return {
        "representation": "RDF graph with explicit PROV-O relationships",
        "explicit_prov_o_predicates": len(predicates),
        "prov_o_predicates": predicates,
        "note": "The RDF registry explicitly distinguishes attribution, derivation and generation relationships.",
    }


def provenance_profile_embedded(ifc_path: Path) -> dict[str, Any]:
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    p = None
    used_name = None
    for name in EMBEDDED_PSET_NAMES:
        p = get_pset_dict(wall, name)
        if p:
            used_name = name
            break
    fields = ["ResponsibleAgent", "SourceReference", "SourceURI", "MethodType", "DataYear", "RecordVersion"]
    return {
        "representation": f"IFC property-set fields ({used_name or 'not found'})",
        "explicit_prov_o_predicates": 0,
        "provenance_fields_present": sum(1 for f in fields if p and p.get(f) not in (None, "")),
        "note": "The selected pilot embeds provenance/context as IFC property values rather than graph relations.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Final controlled architecture comparison for the thesis.")
    script_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=script_dir / "data")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "final_test2_results")
    args = parser.parse_args()

    data = args.data_dir.expanduser().resolve()
    out = args.results_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    paths = {
        "original": data / "HFT_Bau1_2026.02.18.ifc",
        "embedded": data / "HFT_Bau1_baseline_embedded.ifc",
        "native_json_ifc": data / "HFT_Bau1_baseline_native_reference.ifc",
        "custom_rdf_ifc": data / "HFT_Bau1_baseline_proposed_ifc_rdf.ifc",
        "native_json": data / "native_external_record_v1.json",
        "rdf_registry": data / "acoustic_registry_v1.ttl",
    }

    print("=" * 88)
    print("TEST 2 — CONTROLLED ARCHITECTURE COMPARISON")
    print("=" * 88)
    print(f"Wall GlobalId: {WALL_GUID}")
    print(f"Acoustic record: {RECORD_ID}")
    print("Primary arms: Embedded IFC | Native IFC -> JSON | Custom IFC link -> RDF")
    print("Sensitivity arm: Native IFC -> SAME RDF registry")

    missing = [p for p in paths.values() if not p.exists()]
    if missing:
        print("\nMissing input files:")
        for p in missing:
            print("  -", p)
        raise SystemExit("Put the required files in the data folder before running Test 2.")

    sensitivity_ifc = out / "HFT_Bau1_sensitivity_native_to_same_rdf.ifc"
    make_native_to_same_rdf_ifc(paths["native_json_ifc"], sensitivity_ifc)

    # ------------------------------------------------------------------
    # Initial retrieval
    # ------------------------------------------------------------------
    initial: dict[str, dict[str, Any]] = {}
    statuses: dict[str, str] = {}

    initial["Embedded IFC"], statuses["Embedded IFC"] = retrieve_embedded(paths["embedded"])
    initial["Native IFC -> JSON"], statuses["Native IFC -> JSON"] = retrieve_native(
        paths["native_json_ifc"], {NATIVE_RECORD_URI: paths["native_json"]}
    )
    initial["Native IFC -> same RDF"], statuses["Native IFC -> same RDF"] = retrieve_native_rdf(
        sensitivity_ifc, paths["rdf_registry"]
    )
    initial["Custom IFC link -> RDF"], statuses["Custom IFC link -> RDF"] = retrieve_custom_rdf_safe(
        paths["custom_rdf_ifc"], paths["rdf_registry"]
    )

    print("\nINITIAL RETRIEVAL TEST")
    for arm, payload in initial.items():
        print(f"  {arm:<28} {success_count(payload)}/5   {statuses[arm]}")

    (out / "test2_initial_retrieval.json").write_text(
        json.dumps(initial, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ------------------------------------------------------------------
    # IFC overhead
    # ------------------------------------------------------------------
    original_metrics = ifc_metrics(paths["original"])
    arm_ifcs = {
        "Embedded IFC": paths["embedded"],
        "Native IFC -> JSON": paths["native_json_ifc"],
        "Native IFC -> same RDF": sensitivity_ifc,
        "Custom IFC link -> RDF": paths["custom_rdf_ifc"],
    }

    overhead_rows: list[dict[str, Any]] = []
    for arm, p in arm_ifcs.items():
        m = ifc_metrics(p)
        overhead_rows.append({
            "approach": arm,
            "ifc_entities_added": m["ifc_entities"] - original_metrics["ifc_entities"],
            "ifc_single_value_properties_added": m["ifc_single_value_properties"] - original_metrics["ifc_single_value_properties"],
            "ifc_bytes_added": m["ifc_bytes"] - original_metrics["ifc_bytes"],
        })
    write_csv(out / "test2_ifc_overhead.csv", overhead_rows)

    # ------------------------------------------------------------------
    # Provenance representation profile
    # ------------------------------------------------------------------
    provenance_rows = []
    profiles = {
        "Embedded IFC": provenance_profile_embedded(paths["embedded"]),
        "Native IFC -> JSON": provenance_profile_json(paths["native_json"]),
        "Native IFC -> same RDF": provenance_profile_rdf(paths["rdf_registry"]),
        "Custom IFC link -> RDF": provenance_profile_rdf(paths["rdf_registry"]),
    }
    for arm, profile in profiles.items():
        provenance_rows.append({
            "approach": arm,
            "representation": profile["representation"],
            "explicit_prov_o_predicates": profile["explicit_prov_o_predicates"],
            "provenance_fields_present": profile.get("provenance_fields_present", "N/A"),
            "note": profile["note"],
        })
    write_csv(out / "test2_provenance_structure.csv", provenance_rows)

    # ------------------------------------------------------------------
    # Controlled scenarios
    # ------------------------------------------------------------------
    baseline_hashes = {arm: sha256(path) for arm, path in arm_ifcs.items()}
    scenario_rows: list[dict[str, Any]] = []

    def add_row(
        scenario: str,
        arm: str,
        retrieval: dict[str, Any],
        link_status: str,
        scenario_ifc: Path,
        external_modified: bool,
        note: str,
    ) -> None:
        scenario_rows.append({
            "scenario": scenario,
            "approach": arm,
            "ifc_modified_from_baseline": sha256(scenario_ifc) != baseline_hashes[arm],
            "external_record_modified": external_modified,
            "retrieval_questions_successful": success_count(retrieval),
            "retrieval_questions_total": 5,
            "link_status": link_status,
            "note": note,
        })

    with tempfile.TemporaryDirectory(prefix="thesis_test2_") as td:
        temp = Path(td)

        # 2. Acoustic-value update
        emb_val = temp / "embedded_value.ifc"
        embedded_update_value(paths["embedded"], emb_val)
        r, s = retrieve_embedded(emb_val)
        add_row("Acoustic-value update", "Embedded IFC", r, s, emb_val, False,
                f"Controlled Rw update to {UPDATED_RW} dB stored inside IFC.")

        json_val = temp / "native_value.json"
        update_native_json_value(paths["native_json"], json_val)
        r, s = retrieve_native(paths["native_json_ifc"], {NATIVE_RECORD_URI: json_val})
        add_row("Acoustic-value update", "Native IFC -> JSON", r, s, paths["native_json_ifc"], True,
                "Only external JSON changed; IFC hash remains identical to its baseline.")

        rdf_val = temp / "rdf_value.ttl"
        update_rdf_value(paths["rdf_registry"], rdf_val)
        r, s = retrieve_native_rdf(sensitivity_ifc, rdf_val)
        add_row("Acoustic-value update", "Native IFC -> same RDF", r, s, sensitivity_ifc, True,
                "Only the shared RDF registry changed; IFC-native reference stayed unchanged.")
        r, s = retrieve_custom_rdf_safe(paths["custom_rdf_ifc"], rdf_val)
        add_row("Acoustic-value update", "Custom IFC link -> RDF", r, s, paths["custom_rdf_ifc"], True,
                "Only the shared RDF registry changed; custom IFC URI stayed unchanged.")

        # 3. Provenance/source update
        emb_prov = temp / "embedded_provenance.ifc"
        embedded_update_source(paths["embedded"], emb_prov)
        r, s = retrieve_embedded(emb_prov)
        add_row("Provenance/source update", "Embedded IFC", r, s, emb_prov, False,
                "Source reference/version updated inside IFC property values.")

        json_prov = temp / "native_provenance.json"
        update_native_json_provenance(paths["native_json"], json_prov)
        r, s = retrieve_native(paths["native_json_ifc"], {NATIVE_RECORD_URI: json_prov})
        add_row("Provenance/source update", "Native IFC -> JSON", r, s, paths["native_json_ifc"], True,
                "Source/version updated in application-defined external JSON.")

        rdf_prov = temp / "rdf_provenance.ttl"
        update_rdf_provenance(paths["rdf_registry"], rdf_prov)
        r, s = retrieve_native_rdf(sensitivity_ifc, rdf_prov)
        add_row("Provenance/source update", "Native IFC -> same RDF", r, s, sensitivity_ifc, True,
                "Source/version updated in shared RDF; existing PROV-O graph relations retained.")
        r, s = retrieve_custom_rdf_safe(paths["custom_rdf_ifc"], rdf_prov)
        add_row("Provenance/source update", "Custom IFC link -> RDF", r, s, paths["custom_rdf_ifc"], True,
                "Source/version updated in shared RDF; existing PROV-O graph relations retained.")

        # 4. Corrected external-resource unavailable test
        # IFC-side identifiers remain unchanged for every external arm.
        r, s = retrieve_embedded(paths["embedded"])
        add_row("External resource unavailable", "Embedded IFC", r, "N/A", paths["embedded"], False,
                "Not applicable: acoustic record is embedded, so no external resource is required.")

        r, s = retrieve_native(paths["native_json_ifc"], {})
        add_row("External resource unavailable", "Native IFC -> JSON", r, s, paths["native_json_ifc"], False,
                "IFC document Location unchanged; external JSON intentionally unavailable.")

        missing_rdf = temp / "DOES_NOT_EXIST.ttl"
        r, s = retrieve_native_rdf(sensitivity_ifc, missing_rdf)
        add_row("External resource unavailable", "Native IFC -> same RDF", r, s, sensitivity_ifc, False,
                "IFC-native RDF URI unchanged; RDF resource intentionally unavailable.")

        r, s = retrieve_custom_rdf_safe(paths["custom_rdf_ifc"], missing_rdf)
        add_row("External resource unavailable", "Custom IFC link -> RDF", r, s, paths["custom_rdf_ifc"], False,
                "Custom IFC RDF URI unchanged; RDF resource intentionally unavailable.")

    write_csv(out / "test2_scenario_results.csv", scenario_rows)

    summary_lines = [
        "TEST 2 — CONTROLLED ARCHITECTURE COMPARISON",
        "",
        f"Wall: {WALL_GUID}",
        f"Record: {RECORD_ID}",
        "",
        "Initial retrieval:",
    ]
    for arm, payload in initial.items():
        summary_lines.append(f"- {arm}: {success_count(payload)}/5 ({statuses[arm]})")
    summary_lines += ["", "Interpretation rules:",
        "- Embedded vs Native->JSON primarily isolates the effect of externalisation.",
        "- Native->JSON vs Native->same RDF isolates the effect of external representation while holding the IFC-native carrier constant.",
        "- Native->same RDF vs Custom->RDF isolates the IFC-side carrier while holding the same RDF registry constant.",
        "- External-unavailable scenarios keep every IFC-side identifier unchanged.",
        "- File-size overhead is secondary; entity/property counts are the more structurally meaningful IFC-side metrics.",
        "- 5/5 retrieval means the query was answerable, not that every source field is complete or semantically appropriate.",
    ]
    (out / "test2_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print("\nIFC-SIDE OVERHEAD")
    print(f"{'Approach':<28} {'Entities':>9} {'Props':>8} {'Bytes':>10}")
    for row in overhead_rows:
        print(f"{row['approach']:<28} {row['ifc_entities_added']:>9} {row['ifc_single_value_properties_added']:>8} {row['ifc_bytes_added']:>10}")

    print("\nCONTROLLED SCENARIOS")
    print(f"{'Scenario':<30} {'Approach':<28} {'IFC edit':<9} {'External':<9} {'Retrieved':<10} {'Link'}")
    for row in scenario_rows:
        print(
            f"{row['scenario']:<30} {row['approach']:<28} "
            f"{str(row['ifc_modified_from_baseline']):<9} {str(row['external_record_modified']):<9} "
            f"{row['retrieval_questions_successful']}/5{'':<7} {row['link_status']}"
        )

    print("\nRESULTS WRITTEN TO:", out)
    print("Next: run Test 3 only after reviewing these Test 2 outputs.")


if __name__ == "__main__":
    main()
