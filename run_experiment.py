from __future__ import annotations

import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import get_psets
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

# -----------------------------------------------------------------------------
# Controlled pilot configuration
# -----------------------------------------------------------------------------
WALL_GUID = "2qL6OSUnz6ZAzEOn1HxeD2"
RECORD_ID = "vabdat-310"
RDF_RECORD_URI = "https://example.org/hft-acoustic/record/vabdat-310"
NATIVE_RECORD_URI = "https://example.org/hft-acoustic-native/record/vabdat-310.json"

AC = Namespace("https://example.org/hft-acoustic/vocab/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# The update values below are CONTROLLED EXPERIMENTAL CHANGES.
# They are not claimed to be VaBDat or Bau 1 source measurements.
UPDATED_RW = 45.0
UPDATED_SOURCE_REFERENCE = "Anhang, Luftschallmessung-Nr. M_25 [CONTROLLED REVISION]"
UPDATED_VERSION = "prototype-v2"
BROKEN_NATIVE_URI = "https://example.org/hft-acoustic-native/record/MISSING.json"
BROKEN_RDF_URI = "https://example.org/hft-acoustic/record/MISSING"
GEOMETRY_SHIFT_X_M = 0.10


# -----------------------------------------------------------------------------
# General helpers
# -----------------------------------------------------------------------------
def open_ifc(path: Path):
    print(f"Opening IFC: {path.name}")
    return ifcopenshell.open(str(path))


def get_wall(model):
    wall = model.by_guid(WALL_GUID)
    if wall is None:
        raise RuntimeError(f"Wall GlobalId {WALL_GUID} was not found")
    return wall


def get_pset_dict(wall, name: str) -> dict[str, Any] | None:
    return get_psets(
        wall,
        psets_only=False,
        qtos_only=False,
        should_inherit=True,
    ).get(name)


def get_pset_entity(model, wall, name: str):
    pset = get_pset_dict(wall, name)
    if not pset:
        raise RuntimeError(f"{name} not found on wall {WALL_GUID}")
    pset_id = pset.get("id")
    if not pset_id:
        raise RuntimeError(f"IfcOpenShell did not return the entity id for {name}")
    return model.by_id(int(pset_id))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def ifc_metrics(path: Path) -> dict[str, int]:
    model = open_ifc(path)
    # list(model) is the closest reproducible entity-count comparison across arms.
    entity_count = sum(1 for _ in model)
    property_count = len(model.by_type("IfcPropertySingleValue"))
    return {
        "ifc_bytes": path.stat().st_size,
        "ifc_entities": entity_count,
        "ifc_single_value_properties": property_count,
    }


def success_count(result: dict[str, Any]) -> int:
    return sum(
        1
        for key in ("Q1", "Q2", "Q3", "Q4", "Q5")
        if result.get(key) not in (None, [], {})
    )


def find_native_reference(model, wall):
    for rel in model.by_type("IfcRelAssociatesDocument"):
        try:
            if wall not in (rel.RelatedObjects or []):
                continue
            doc = rel.RelatingDocument
            if not doc or not doc.is_a("IfcDocumentReference"):
                continue
            if getattr(doc, "Identification", None) == RECORD_ID:
                return doc
        except Exception:
            continue
    raise RuntimeError(f"Native IfcDocumentReference {RECORD_ID} not found")


def shift_wall_x(model, wall, delta_m: float) -> tuple[float, float]:
    placement = getattr(wall, "ObjectPlacement", None)
    if placement is None:
        raise RuntimeError("Selected wall has no ObjectPlacement")
    relative = getattr(placement, "RelativePlacement", None)
    location = getattr(relative, "Location", None) if relative else None
    coordinates = getattr(location, "Coordinates", None) if location else None
    if not coordinates:
        raise RuntimeError("Could not resolve wall placement coordinates")

    coords = list(coordinates)
    old_x = float(coords[0])
    coords[0] = old_x + delta_m
    location.Coordinates = tuple(coords)
    return old_x, float(coords[0])


# -----------------------------------------------------------------------------
# Equivalent retrieval for each comparison arm
# -----------------------------------------------------------------------------
def retrieve_embedded(ifc_path: Path) -> tuple[dict[str, Any], str]:
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    p = get_pset_dict(wall, "Pset_AcousticEmbedded")
    if not p:
        return {f"Q{i}": None for i in range(1, 6)}, "UNMATCHED"

    # Q5: find all walls carrying the same embedded record identifier.
    walls = []
    for candidate in model.by_type("IfcWall"):
        cp = get_pset_dict(candidate, "Pset_AcousticEmbedded")
        if cp and str(cp.get("RecordIdentifier")) == RECORD_ID:
            walls.append({
                "global_id": candidate.GlobalId,
                "step_id": candidate.id(),
                "name": candidate.Name,
            })

    return {
        "Q1": {
            "value": p.get("AcousticValue"),
            "unit": p.get("AcousticUnit"),
            "metric": p.get("AcousticMetric"),
        },
        "Q2": {
            "assembly": p.get("AssemblyDescription"),
            "construction_type": p.get("ConstructionType"),
            "thickness_m": p.get("TotalThickness_m"),
            "test_area_m2": p.get("TestArea_m2"),
        },
        "Q3": {
            "responsible_agent": p.get("ResponsibleAgent"),
            "source_reference": p.get("SourceReference"),
            "source_uri": p.get("SourceURI"),
        },
        "Q4": {
            "method": p.get("MethodType"),
            "date_year": p.get("DataYear"),
            "version": p.get("RecordVersion"),
        },
        "Q5": walls,
    }, "N/A"


def retrieve_native(
    ifc_path: Path,
    resource_map: dict[str, Path],
) -> tuple[dict[str, Any], str]:
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    doc = find_native_reference(model, wall)
    uri = str(doc.Location or "")

    # Q5 can still be answered from IFC even if the external resource is broken.
    walls = []
    for candidate in model.by_type("IfcWall"):
        try:
            cdoc = find_native_reference(model, candidate)
            if str(cdoc.Location or "") == uri:
                walls.append({
                    "global_id": candidate.GlobalId,
                    "step_id": candidate.id(),
                    "name": candidate.Name,
                    "record_uri": uri,
                })
        except RuntimeError:
            continue

    resource = resource_map.get(uri)
    if resource is None or not resource.exists():
        return {
            "Q1": None,
            "Q2": None,
            "Q3": None,
            "Q4": None,
            "Q5": walls,
        }, "BROKEN"

    payload = json.loads(resource.read_text(encoding="utf-8"))
    p = payload["record"]
    return {
        "Q1": {
            "value": p.get("AcousticValue"),
            "unit": p.get("AcousticUnit"),
            "metric": p.get("AcousticMetric"),
        },
        "Q2": {
            "assembly": p.get("AssemblyDescription"),
            "construction_type": p.get("ConstructionType"),
            "thickness_m": p.get("TotalThickness_m"),
            "test_area_m2": p.get("TestArea_m2"),
        },
        "Q3": {
            "responsible_agent": p.get("ResponsibleAgent"),
            "source_reference": p.get("SourceReference"),
            "source_uri": p.get("SourceURI"),
        },
        "Q4": {
            "method": p.get("MethodType"),
            "date_year": p.get("DataYear"),
            "version": p.get("RecordVersion"),
        },
        "Q5": walls,
    }, "VALID"


def build_rdf_query_graph(ifc_path: Path, registry_path: Path) -> tuple[Graph, str, str, str]:
    model = open_ifc(ifc_path)
    wall = get_wall(model)
    pset = get_pset_dict(wall, "Pset_AcousticLink")
    if not pset:
        raise RuntimeError("Pset_AcousticLink not found")
    uri = str(pset.get("AcousticRecordURI") or "")
    status = str(pset.get("MappingStatus") or "")
    basis = str(pset.get("MappingBasis") or "")

    g = Graph()
    g.parse(registry_path, format="turtle")

    # Lightweight semantic link graph only; this is NOT full IFC->RDF conversion.
    for candidate in model.by_type("IfcWall"):
        cp = get_pset_dict(candidate, "Pset_AcousticLink")
        if not cp or not cp.get("AcousticRecordURI"):
            continue
        wall_uri = URIRef(f"https://example.org/hft-ifc/wall/{candidate.GlobalId}")
        g.add((wall_uri, RDF.type, AC.IFCWallLink))
        g.add((wall_uri, DCTERMS.identifier, Literal(candidate.GlobalId)))
        g.add((wall_uri, AC.ifcStepId, Literal(candidate.id())))
        g.add((wall_uri, AC.ifcName, Literal(candidate.Name or "")))
        g.add((wall_uri, AC.acousticRecord, URIRef(str(cp["AcousticRecordURI"]))))
        if cp.get("MappingStatus"):
            g.add((wall_uri, AC.mappingStatus, Literal(str(cp["MappingStatus"]))))
    return g, uri, status, basis


def retrieve_rdf(ifc_path: Path, registry_path: Path) -> tuple[dict[str, Any], str]:
    g, uri, _, _ = build_rdf_query_graph(ifc_path, registry_path)
    rec = URIRef(uri)
    exists = any(True for _ in g.triples((rec, None, None)))

    q5 = list(g.query(f"""
        PREFIX ac: <https://example.org/hft-acoustic/vocab/>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT ?globalId ?ifcName ?mappingStatus
        WHERE {{
          ?wall ac:acousticRecord <{uri}> ;
                dct:identifier ?globalId ;
                ac:ifcName ?ifcName .
          OPTIONAL {{ ?wall ac:mappingStatus ?mappingStatus }}
        }}
    """))
    q5_payload = [
        {
            "global_id": str(row[0]),
            "name": str(row[1]),
            "mapping_status": None if row[2] is None else str(row[2]),
        }
        for row in q5
    ]

    if not exists:
        return {
            "Q1": None,
            "Q2": None,
            "Q3": None,
            "Q4": None,
            "Q5": q5_payload,
        }, "BROKEN"

    q1 = list(g.query(f"""
        PREFIX ac: <https://example.org/hft-acoustic/vocab/>
        SELECT ?value ?unit ?metric
        WHERE {{
          <{uri}> ac:weightedSoundReductionIndex ?value ;
                  ac:acousticUnit ?unit .
          OPTIONAL {{ <{uri}> ac:acousticMetric ?metric }}
        }}
    """))
    q2 = list(g.query(f"""
        PREFIX ac: <https://example.org/hft-acoustic/vocab/>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT ?assembly ?constructionType ?thickness ?testArea
        WHERE {{
          <{uri}> ac:describesComponent ?component .
          ?component dct:title ?assembly .
          OPTIONAL {{ ?component ac:constructionType ?constructionType }}
          OPTIONAL {{ ?component ac:totalThickness_m ?thickness }}
          OPTIONAL {{ <{uri}> ac:testArea_m2 ?testArea }}
        }}
    """))
    q3 = list(g.query(f"""
        PREFIX ac: <https://example.org/hft-acoustic/vocab/>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT ?agent ?sourceReference ?source
        WHERE {{
          <{uri}> ac:sourceReference ?sourceReference .
          OPTIONAL {{
            <{uri}> ac:sourceOrganisation ?agentUri .
            ?agentUri dct:title ?agent .
          }}
          OPTIONAL {{
            <{uri}> <http://www.w3.org/ns/prov#wasDerivedFrom> ?source .
          }}
        }}
    """))
    q4 = list(g.query(f"""
        PREFIX ac: <https://example.org/hft-acoustic/vocab/>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT ?method ?dateYear ?version
        WHERE {{
          OPTIONAL {{ <{uri}> ac:methodType ?method }}
          OPTIONAL {{ <{uri}> ac:dataYear ?dateYear }}
          OPTIONAL {{ <{uri}> dct:hasVersion ?version }}
        }}
    """))

    return {
        "Q1": None if not q1 else {
            "value": str(q1[0][0]),
            "unit": str(q1[0][1]),
            "metric": None if q1[0][2] is None else str(q1[0][2]),
        },
        "Q2": None if not q2 else {
            "assembly": str(q2[0][0]),
            "construction_type": None if q2[0][1] is None else str(q2[0][1]),
            "thickness_m": None if q2[0][2] is None else str(q2[0][2]),
            "test_area_m2": None if q2[0][3] is None else str(q2[0][3]),
        },
        "Q3": None if not q3 else {
            "responsible_agent": None if q3[0][0] is None else str(q3[0][0]),
            "source_reference": str(q3[0][1]),
            "derived_from": [str(row[2]) for row in q3 if row[2] is not None],
        },
        "Q4": None if not q4 else {
            "method": None if q4[0][0] is None else str(q4[0][0]),
            "date_year": None if q4[0][1] is None else str(q4[0][1]),
            "version": None if q4[0][2] is None else str(q4[0][2]),
        },
        "Q5": q5_payload,
    }, "VALID"


# -----------------------------------------------------------------------------
# Controlled modifications
# -----------------------------------------------------------------------------
def embedded_update_value(src: Path, dst: Path) -> None:
    model = open_ifc(src)
    wall = get_wall(model)
    pset = get_pset_entity(model, wall, "Pset_AcousticEmbedded")
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset,
        properties={"AcousticValue": UPDATED_RW},
    )
    model.write(str(dst))


def embedded_update_source(src: Path, dst: Path) -> None:
    model = open_ifc(src)
    wall = get_wall(model)
    pset = get_pset_entity(model, wall, "Pset_AcousticEmbedded")
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset,
        properties={
            "SourceReference": UPDATED_SOURCE_REFERENCE,
            "RecordVersion": UPDATED_VERSION,
        },
    )
    model.write(str(dst))


def native_break_link(src: Path, dst: Path) -> None:
    model = open_ifc(src)
    wall = get_wall(model)
    doc = find_native_reference(model, wall)
    doc.Location = BROKEN_NATIVE_URI
    model.write(str(dst))


def rdf_break_link(src: Path, dst: Path) -> None:
    model = open_ifc(src)
    wall = get_wall(model)
    pset = get_pset_entity(model, wall, "Pset_AcousticLink")
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset,
        properties={"AcousticRecordURI": BROKEN_RDF_URI},
    )
    model.write(str(dst))


def geometry_shift(src: Path, dst: Path) -> tuple[float, float]:
    model = open_ifc(src)
    wall = get_wall(model)
    old_x, new_x = shift_wall_x(model, wall, GEOMETRY_SHIFT_X_M)
    model.write(str(dst))
    return old_x, new_x


# -----------------------------------------------------------------------------
# Main experiment
# -----------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the controlled three-arm IFC acoustic information-management experiment."
    )
    script_dir = Path(__file__).resolve().parent
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=script_dir / "data",
        help="Folder containing the four IFC inputs plus JSON/Turtle acoustic records.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=script_dir / "results",
        help="Folder where experiment outputs will be written.",
    )
    args = parser.parse_args()

    data = args.data_dir.expanduser().resolve()
    results_dir = args.results_dir.expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "original": data / "HFT_Bau1_2026.02.18.ifc",
        "embedded": data / "HFT_Bau1_baseline_embedded.ifc",
        "native": data / "HFT_Bau1_baseline_native_reference.ifc",
        "rdf": data / "HFT_Bau1_baseline_proposed_ifc_rdf.ifc",
        "native_json": data / "native_external_record_v1.json",
        "rdf_registry": data / "acoustic_registry_v1.ttl",
    }

    print("\nInput folder:")
    print(f"  {data}")
    print("\nChecking required files:")
    for key, path in paths.items():
        status = "FOUND" if path.exists() else "MISSING"
        size = f" ({path.stat().st_size / (1024*1024):.1f} MB)" if path.exists() else ""
        print(f"  [{status}] {key:12s} -> {path.name}{size}")

    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "\nThe experiment cannot start because these inputs are missing:\n  "
            + "\n  ".join(missing)
            + "\n\nPut the files in the printed data folder, or run with an explicit path, for example:\n"
              "python run_experiment.py --data-dir \"E:\\\\thesis_experiment\\\\data\""
        )

    print("\n" + "=" * 72)
    print("THREE-ARM IFC ACOUSTIC INFORMATION-MANAGEMENT EXPERIMENT")
    print("=" * 72)
    print(f"Wall GlobalId: {WALL_GUID}")
    print(f"Reference record: {RECORD_ID}")
    print("Claim scope: external reference acoustic performance record; not an in-situ Bau 1 measurement.")

    # ------------------------------------------------------------------
    # Initial equivalent retrieval
    # ------------------------------------------------------------------
    embedded_initial, embedded_status = retrieve_embedded(paths["embedded"])
    native_initial, native_status = retrieve_native(
        paths["native"], {NATIVE_RECORD_URI: paths["native_json"]}
    )
    rdf_initial, rdf_status = retrieve_rdf(paths["rdf"], paths["rdf_registry"])

    initial = {
        "Embedded IFC": embedded_initial,
        "Native IFC reference": native_initial,
        "Proposed IFC-RDF": rdf_initial,
    }

    print("\nINITIAL FIVE INFORMATION QUESTIONS")
    for name, payload in initial.items():
        print(f"  {name:<24} {success_count(payload)}/5")

    # ------------------------------------------------------------------
    # IFC-side overhead
    # ------------------------------------------------------------------
    original_metrics = ifc_metrics(paths["original"])
    baseline_rows: list[dict[str, Any]] = []
    for name, key, status in [
        ("Embedded IFC", "embedded", embedded_status),
        ("Native IFC reference", "native", native_status),
        ("Proposed IFC-RDF", "rdf", rdf_status),
    ]:
        m = ifc_metrics(paths[key])
        baseline_rows.append({
            "approach": name,
            "initial_retrieval_success": success_count(initial[name]),
            "initial_retrieval_total": 5,
            "link_status": status,
            "ifc_bytes_added": m["ifc_bytes"] - original_metrics["ifc_bytes"],
            "ifc_entities_added": m["ifc_entities"] - original_metrics["ifc_entities"],
            "ifc_single_value_properties_added": (
                m["ifc_single_value_properties"] - original_metrics["ifc_single_value_properties"]
            ),
        })

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------
    scenario_rows: list[dict[str, Any]] = []

    def add_scenario(
        approach: str,
        scenario: str,
        ifc_modified: bool,
        external_modified: bool,
        retrieval: dict[str, Any],
        link_status: str,
        note: str,
    ) -> None:
        scenario_rows.append({
            "approach": approach,
            "scenario": scenario,
            "ifc_modified": ifc_modified,
            "external_record_modified": external_modified,
            "retrieval_questions_successful": success_count(retrieval),
            "retrieval_questions_total": 5,
            "link_status": link_status,
            "note": note,
        })

    for approach, retrieval, status in [
        ("Embedded IFC", embedded_initial, "N/A"),
        ("Native IFC reference", native_initial, native_status),
        ("Proposed IFC-RDF", rdf_initial, rdf_status),
    ]:
        add_scenario(
            approach,
            "Initial creation",
            True,
            approach != "Embedded IFC",
            retrieval,
            status,
            "Initial controlled baseline representation.",
        )

    with tempfile.TemporaryDirectory(prefix="ifc_acoustic_experiment_") as temp:
        tempdir = Path(temp)

        # --------------------------------------------------------------
        # Acoustic value update
        # --------------------------------------------------------------
        embedded_value_ifc = tempdir / "embedded_value.ifc"
        embedded_update_value(paths["embedded"], embedded_value_ifc)
        r, s = retrieve_embedded(embedded_value_ifc)
        add_scenario(
            "Embedded IFC", "Acoustic-value update", True, False, r, s,
            f"Controlled update 44.1 -> {UPDATED_RW} dB required editing the IFC.",
        )

        native_value_json = tempdir / "native_value.json"
        payload = json.loads(paths["native_json"].read_text(encoding="utf-8"))
        payload["record"]["AcousticValue"] = UPDATED_RW
        payload["control_test_note"] = "Hypothetical controlled update; not a source measurement."
        native_value_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        r, s = retrieve_native(paths["native"], {NATIVE_RECORD_URI: native_value_json})
        add_scenario(
            "Native IFC reference", "Acoustic-value update", False, True, r, s,
            f"External JSON changed to {UPDATED_RW} dB; IFC remained unchanged.",
        )

        rdf_value_ttl = tempdir / "rdf_value.ttl"
        g = Graph()
        g.parse(paths["rdf_registry"], format="turtle")
        rec = URIRef(RDF_RECORD_URI)
        for triple in list(g.triples((rec, AC.weightedSoundReductionIndex, None))):
            g.remove(triple)
        g.add((rec, AC.weightedSoundReductionIndex, Literal(str(UPDATED_RW), datatype=XSD.decimal)))
        g.serialize(destination=str(rdf_value_ttl), format="turtle")
        r, s = retrieve_rdf(paths["rdf"], rdf_value_ttl)
        add_scenario(
            "Proposed IFC-RDF", "Acoustic-value update", False, True, r, s,
            f"External RDF changed to {UPDATED_RW} dB; IFC remained unchanged.",
        )

        # --------------------------------------------------------------
        # Source/provenance update
        # --------------------------------------------------------------
        embedded_source_ifc = tempdir / "embedded_source.ifc"
        embedded_update_source(paths["embedded"], embedded_source_ifc)
        r, s = retrieve_embedded(embedded_source_ifc)
        add_scenario(
            "Embedded IFC", "Provenance/source update", True, False, r, s,
            "Source reference and record version were changed inside IFC.",
        )

        native_source_json = tempdir / "native_source.json"
        payload = json.loads(paths["native_json"].read_text(encoding="utf-8"))
        payload["record"]["SourceReference"] = UPDATED_SOURCE_REFERENCE
        payload["record"]["RecordVersion"] = UPDATED_VERSION
        native_source_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        r, s = retrieve_native(paths["native"], {NATIVE_RECORD_URI: native_source_json})
        add_scenario(
            "Native IFC reference", "Provenance/source update", False, True, r, s,
            "External JSON source/version changed; IFC remained unchanged.",
        )

        rdf_source_ttl = tempdir / "rdf_source.ttl"
        g = Graph()
        g.parse(paths["rdf_registry"], format="turtle")
        for triple in list(g.triples((rec, AC.sourceReference, None))):
            g.remove(triple)
        g.add((rec, AC.sourceReference, Literal(UPDATED_SOURCE_REFERENCE)))
        for triple in list(g.triples((rec, DCTERMS.hasVersion, None))):
            g.remove(triple)
        g.add((rec, DCTERMS.hasVersion, Literal(UPDATED_VERSION)))
        g.serialize(destination=str(rdf_source_ttl), format="turtle")
        r, s = retrieve_rdf(paths["rdf"], rdf_source_ttl)
        add_scenario(
            "Proposed IFC-RDF", "Provenance/source update", False, True, r, s,
            "External RDF source/version changed; IFC remained unchanged.",
        )

        # --------------------------------------------------------------
        # Broken-link case
        # --------------------------------------------------------------
        r, _ = retrieve_embedded(paths["embedded"])
        add_scenario(
            "Embedded IFC", "Broken-link case", False, False, r, "N/A",
            "Not applicable: no external acoustic link exists in the embedded arm.",
        )

        native_broken_ifc = tempdir / "native_broken.ifc"
        native_break_link(paths["native"], native_broken_ifc)
        r, s = retrieve_native(native_broken_ifc, {NATIVE_RECORD_URI: paths["native_json"]})
        add_scenario(
            "Native IFC reference", "Broken-link case", True, False, r, s,
            "Document Location intentionally changed to a nonexistent URI.",
        )

        rdf_broken_ifc = tempdir / "rdf_broken.ifc"
        rdf_break_link(paths["rdf"], rdf_broken_ifc)
        r, s = retrieve_rdf(rdf_broken_ifc, paths["rdf_registry"])
        add_scenario(
            "Proposed IFC-RDF", "Broken-link case", True, False, r, s,
            "Pset_AcousticLink URI intentionally changed to an absent RDF resource.",
        )

        # --------------------------------------------------------------
        # Wall geometry/location change
        # --------------------------------------------------------------
        for approach, key, retriever in [
            ("Embedded IFC", "embedded", lambda p: retrieve_embedded(p)),
            ("Native IFC reference", "native", lambda p: retrieve_native(p, {NATIVE_RECORD_URI: paths["native_json"]})),
            ("Proposed IFC-RDF", "rdf", lambda p: retrieve_rdf(p, paths["rdf_registry"])),
        ]:
            shifted = tempdir / f"{key}_geometry.ifc"
            old_x, new_x = geometry_shift(paths[key], shifted)
            r, s = retriever(shifted)
            add_scenario(
                approach, "Wall-geometry change", True, False, r, s,
                f"Wall local X placement shifted +{GEOMETRY_SHIFT_X_M} m ({old_x} -> {new_x}); acoustic record not edited.",
            )

    # ------------------------------------------------------------------
    # Provenance structure note
    # ------------------------------------------------------------------
    rdf_graph = Graph()
    rdf_graph.parse(paths["rdf_registry"], format="turtle")
    rdf_prov_predicates = sorted({
        str(predicate)
        for _, predicate, _ in rdf_graph.triples((URIRef(RDF_RECORD_URI), None, None))
        if str(predicate).startswith(str(PROV))
    })

    # Save all outputs.
    write_csv(results_dir / "baseline_metrics.csv", baseline_rows)
    write_csv(results_dir / "scenario_results.csv", scenario_rows)
    (results_dir / "query_results.json").write_text(
        json.dumps({
            "wall_global_id": WALL_GUID,
            "record_id": RECORD_ID,
            "claim_scope": "External reference acoustic performance record; not an in-situ Bau 1 measurement.",
            "initial_results": initial,
            "rdf_explicit_prov_predicates": rdf_prov_predicates,
            "source_method_warning": "The method type is not explicitly specified in the VaBDat source used for this pilot; the experiment reports that absence rather than inventing a method.",
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Console summary.
    print("\nIFC-SIDE OVERHEAD")
    print(f"{'Approach':<24} {'Entities':>10} {'Props':>8} {'Bytes':>10}")
    for row in baseline_rows:
        print(
            f"{row['approach']:<24} "
            f"{row['ifc_entities_added']:>10} "
            f"{row['ifc_single_value_properties_added']:>8} "
            f"{row['ifc_bytes_added']:>10}"
        )

    print("\nCONTROLLED SCENARIOS")
    print(f"{'Scenario':<28} {'Approach':<24} {'IFC edit':<9} {'External edit':<13} {'Retrieved':<10} {'Link'}")
    for row in scenario_rows:
        print(
            f"{row['scenario']:<28} {row['approach']:<24} "
            f"{str(row['ifc_modified']):<9} {str(row['external_record_modified']):<13} "
            f"{row['retrieval_questions_successful']}/5{'':<7} {row['link_status']}"
        )

    print("\nRDF explicit PROV predicates on the acoustic record:")
    for predicate in rdf_prov_predicates:
        print("  -", predicate)

    print("\nRESULT FILES")
    print(" ", results_dir / "baseline_metrics.csv")
    print(" ", results_dir / "scenario_results.csv")
    print(" ", results_dir / "query_results.json")
    print("\nExperiment complete.")


if __name__ == "__main__":
    main()
