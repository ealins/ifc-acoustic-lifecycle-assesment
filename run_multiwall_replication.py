from __future__ import annotations

import csv
import json
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import get_psets
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

AC = Namespace("https://example.org/hft-acoustic/vocab/")
PROV = Namespace("http://www.w3.org/ns/prov#")

UPDATED_RW_DELTA = 1.0
UPDATED_VERSION = "control-v2"
GEOMETRY_SHIFT_X_M = 0.10


@dataclass(frozen=True)
class Case:
    case_id: str
    wall_guid: str
    wall_step_id: int
    expected_name_contains: str
    record_id: str
    rw: float
    thickness_m: float
    assembly: str
    construction_type: str
    source: str
    source_reference: str
    source_uri: str
    year: str
    method: str
    version: str
    mapping_status: str
    mapping_basis: str
    is_real_source_record: bool

    @property
    def rdf_uri(self) -> str:
        return f"https://example.org/hft-acoustic/record/{self.record_id}"

    @property
    def native_uri(self) -> str:
        return f"https://example.org/hft-acoustic-native/record/{self.record_id}.json"


CASES = [
    Case(
        case_id="pilot_metal_stud",
        wall_guid="2qL6OSUnz6ZAzEOn1HxeD2",
        wall_step_id=1439505,
        expected_name_contains="Walls_3OGArc01",
        record_id="vabdat-310",
        rw=44.1,
        thickness_m=0.100,
        assembly="B_bGP12_frM75||iMW60_bGP12",
        construction_type="metal frame construction (MFC)",
        source="ift Rosenheim",
        source_reference="Anhang, Luftschallmessung-Nr. M_25",
        source_uri="https://www.vabdat.de/BauteilKennzahl/view/310",
        year="2022",
        method="Not explicitly specified in the VaBDat source used for this prototype",
        version="prototype-v1",
        mapping_status="AMBIGUOUS_REFERENCE_MATCH",
        mapping_basis=(
            "Shared metal-stud construction family; reference record used for workflow validation only. "
            "This is not an in-situ Bau 1 measurement."
        ),
        is_real_source_record=True,
    ),
    Case(
        case_id="control_concrete_150",
        wall_guid="0wnAJp1nDEywwo7Vo$xbfn",
        wall_step_id=35263,
        expected_name_contains="Generic - Concrete - 0.15",
        record_id="control-concrete-150",
        rw=50.0,
        thickness_m=0.150,
        assembly="CONTROL - Generic concrete wall 0.15 m",
        construction_type="concrete",
        source="CONTROLLED SYNTHETIC RECORD",
        source_reference="architecture-replication-control-150",
        source_uri="https://example.org/control/concrete-150",
        year="2026",
        method="Synthetic controlled record; not an acoustic measurement",
        version="control-v1",
        mapping_status="CONTROLLED_REFERENCE",
        mapping_basis="Synthetic control record used only to replicate information-architecture behavior.",
        is_real_source_record=False,
    ),
    Case(
        case_id="control_concrete_300",
        wall_guid="1You9r7r15Ax77pHYWcjAi",
        wall_step_id=33989,
        expected_name_contains="Generic - Concrete - 0.30",
        record_id="control-concrete-300",
        rw=55.0,
        thickness_m=0.300,
        assembly="CONTROL - Generic concrete wall 0.30 m",
        construction_type="concrete",
        source="CONTROLLED SYNTHETIC RECORD",
        source_reference="architecture-replication-control-300",
        source_uri="https://example.org/control/concrete-300",
        year="2026",
        method="Synthetic controlled record; not an acoustic measurement",
        version="control-v1",
        mapping_status="CONTROLLED_REFERENCE",
        mapping_basis="Synthetic control record used only to replicate information-architecture behavior.",
        is_real_source_record=False,
    ),
    Case(
        case_id="control_wood_100",
        wall_guid="3jVfQlWajACA3M083XXgEN",
        wall_step_id=916076,
        expected_name_contains="Generic -Wood - 0.10 2",
        record_id="control-wood-100",
        rw=40.0,
        thickness_m=0.100,
        assembly="CONTROL - Generic wood wall 0.10 m",
        construction_type="wood",
        source="CONTROLLED SYNTHETIC RECORD",
        source_reference="architecture-replication-control-wood-100",
        source_uri="https://example.org/control/wood-100",
        year="2026",
        method="Synthetic controlled record; not an acoustic measurement",
        version="control-v1",
        mapping_status="CONTROLLED_REFERENCE",
        mapping_basis="Synthetic control record used only to replicate information-architecture behavior.",
        is_real_source_record=False,
    ),
]


def open_ifc(path: Path):
    return ifcopenshell.open(str(path))


def get_wall(model, case: Case):
    wall = model.by_guid(case.wall_guid)
    if wall is None:
        raise RuntimeError(f"[{case.case_id}] wall not found: {case.wall_guid}")
    if case.expected_name_contains not in str(wall.Name or ""):
        raise RuntimeError(
            f"[{case.case_id}] unexpected wall name: {wall.Name!r}; "
            f"expected it to contain {case.expected_name_contains!r}"
        )
    return wall


def psets(wall) -> dict[str, Any]:
    return get_psets(wall, psets_only=False, qtos_only=False, should_inherit=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def metrics(path: Path) -> dict[str, int]:
    model = open_ifc(path)
    return {
        "bytes": path.stat().st_size,
        "entities": sum(1 for _ in model),
        "props": len(model.by_type("IfcPropertySingleValue")),
    }


def count5(result: dict[str, Any]) -> int:
    return sum(result.get(f"Q{i}") not in (None, [], {}) for i in range(1, 6))


def step_escape(value: str) -> str:
    return str(value).replace("'", "''")


@lru_cache(maxsize=2)
def original_step_context(original: Path) -> tuple[bytes, bytes, int, int]:
    """Return prefix before the final DATA ENDSEC, suffix, max STEP id, and OwnerHistory id.

    Baselines are appended at STEP text level so original bytes remain untouched and
    byte-overhead measurements stay comparable to the first pilot experiment.
    """
    raw = original.read_bytes()
    marker = b"ENDSEC;"
    pos = raw.rfind(marker)
    if pos < 0:
        raise RuntimeError("Could not locate final ENDSEC in IFC")
    prefix, suffix = raw[:pos], raw[pos:]

    max_id = 0
    owner_id = None
    for line in raw.splitlines():
        if not line.startswith(b"#") or b"=" not in line:
            continue
        try:
            sid = int(line[1:line.index(b"=")])
            max_id = max(max_id, sid)
        except Exception:
            pass
        if owner_id is None and b"=IFCOWNERHISTORY(" in line:
            try:
                owner_id = int(line[1:line.index(b"=")])
            except Exception:
                pass
    if owner_id is None:
        raise RuntimeError("IfcOwnerHistory not found")
    return prefix, suffix, max_id, owner_id


def write_appended_ifc(original: Path, out: Path, lines: list[str]) -> None:
    prefix, suffix, _, _ = original_step_context(original)
    addition = ("\n" + "\n".join(lines) + "\n").encode("utf-8")
    out.write_bytes(prefix + addition + suffix)


def make_embedded(original: Path, out: Path, case: Case) -> None:
    _, _, max_id, owner_id = original_step_context(original)
    ids = iter(range(max_id + 1, max_id + 21))
    props: list[tuple[int, str]] = []

    def t(name: str, value: str):
        i = next(ids); props.append((i, f"#{i}=IFCPROPERTYSINGLEVALUE('{step_escape(name)}',$,IFCTEXT('{step_escape(value)}'),$);"))

    def r(name: str, value: float):
        i = next(ids); props.append((i, f"#{i}=IFCPROPERTYSINGLEVALUE('{step_escape(name)}',$,IFCREAL({value}),$);"))

    t("RecordIdentifier", case.record_id)
    t("AcousticMetric", "Rw")
    r("AcousticValue", case.rw)
    t("AcousticUnit", "dB")
    t("AssemblyDescription", case.assembly)
    t("ConstructionType", case.construction_type)
    r("TotalThickness_m", case.thickness_m)
    r("TestArea_m2", 10.0)
    r("SpecimenLengthX_m", 4.0)
    r("SpecimenLengthY_m", 2.5)
    r("SurfaceMass_kg_m2", 100.0)
    t("MethodType", case.method)
    t("SourceType", "controlled architecture replication")
    t("SourceReference", case.source_reference)
    t("DataYear", case.year)
    t("RecordVersion", case.version)
    t("ResponsibleAgent", case.source)
    t("SourceURI", case.source_uri)

    pset_id = next(ids)
    rel_id = next(ids)
    prop_refs = ",".join(f"#{i}" for i, _ in props)
    lines = [line for _, line in props]
    lines.append(
        f"#{pset_id}=IFCPROPERTYSET('{ifcopenshell.guid.new()}',#{owner_id},'Pset_AcousticEmbedded',$,({prop_refs}));"
    )
    lines.append(
        f"#{rel_id}=IFCRELDEFINESBYPROPERTIES('{ifcopenshell.guid.new()}',#{owner_id},$,$,(#{case.wall_step_id}),#{pset_id});"
    )
    write_appended_ifc(original, out, lines)


def make_native(original: Path, out: Path, case: Case) -> None:
    _, _, max_id, owner_id = original_step_context(original)
    wall_id = case.wall_step_id
    doc_id, rel_id = max_id + 1, max_id + 2
    lines = [
        f"#{doc_id}=IFCDOCUMENTREFERENCE('{step_escape(case.native_uri)}','{step_escape(case.record_id)}','External acoustic reference','{step_escape(case.mapping_status + ': ' + case.mapping_basis)}',$);",
        f"#{rel_id}=IFCRELASSOCIATESDOCUMENT('{ifcopenshell.guid.new()}',#{owner_id},'Acoustic external reference',$,(#{wall_id}),#{doc_id});",
    ]
    write_appended_ifc(original, out, lines)


def make_rdf_link(original: Path, out: Path, case: Case) -> None:
    _, _, max_id, owner_id = original_step_context(original)
    wall_id = case.wall_step_id
    p1, p2, p3, pset_id, rel_id = range(max_id + 1, max_id + 6)
    lines = [
        f"#{p1}=IFCPROPERTYSINGLEVALUE('AcousticRecordURI',$,IFCTEXT('{step_escape(case.rdf_uri)}'),$);",
        f"#{p2}=IFCPROPERTYSINGLEVALUE('MappingStatus',$,IFCLABEL('{step_escape(case.mapping_status)}'),$);",
        f"#{p3}=IFCPROPERTYSINGLEVALUE('MappingBasis',$,IFCTEXT('{step_escape(case.mapping_basis)}'),$);",
        f"#{pset_id}=IFCPROPERTYSET('{ifcopenshell.guid.new()}',#{owner_id},'Pset_AcousticLink',$,(#{p1},#{p2},#{p3}));",
        f"#{rel_id}=IFCRELDEFINESBYPROPERTIES('{ifcopenshell.guid.new()}',#{owner_id},$,$,(#{wall_id}),#{pset_id});",
    ]
    write_appended_ifc(original, out, lines)

def make_native_json(path: Path, case: Case) -> None:
    payload = {
        "claim_scope": (
            "Real external reference record; not an in-situ Bau 1 measurement."
            if case.is_real_source_record
            else "CONTROLLED SYNTHETIC RECORD used only for architecture replication; not an acoustic measurement."
        ),
        "record": {
            "RecordIdentifier": case.record_id,
            "AcousticMetric": "Rw",
            "AcousticValue": case.rw,
            "AcousticUnit": "dB",
            "AssemblyDescription": case.assembly,
            "ConstructionType": case.construction_type,
            "TotalThickness_m": case.thickness_m,
            "TestArea_m2": 10.0,
            "MethodType": case.method,
            "SourceReference": case.source_reference,
            "SourceURI": case.source_uri,
            "ResponsibleAgent": case.source,
            "DataYear": case.year,
            "RecordVersion": case.version,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_rdf_registry(path: Path, case: Case) -> None:
    g = Graph()
    rec = URIRef(case.rdf_uri)
    source = URIRef(f"https://example.org/hft-acoustic/source/{case.record_id}")
    agent = URIRef(f"https://example.org/hft-acoustic/agent/{case.record_id}")
    activity = URIRef(f"https://example.org/hft-acoustic/activity/{case.record_id}")
    component = URIRef(f"https://example.org/hft-acoustic/component/{case.record_id}")

    g.add((rec, RDF.type, AC.AcousticPerformanceRecord))
    g.add((rec, AC.acousticMetric, Literal("Rw")))
    g.add((rec, AC.acousticUnit, Literal("dB")))
    g.add((rec, AC.weightedSoundReductionIndex, Literal(str(case.rw), datatype=XSD.decimal)))
    g.add((rec, AC.describesComponent, component))
    g.add((rec, AC.sourceReference, Literal(case.source_reference)))
    g.add((rec, AC.methodType, Literal(case.method)))
    g.add((rec, AC.dataYear, Literal(case.year)))
    g.add((rec, DCTERMS.hasVersion, Literal(case.version)))
    g.add((rec, PROV.wasAttributedTo, agent))
    g.add((rec, PROV.wasDerivedFrom, source))
    g.add((rec, PROV.wasGeneratedBy, activity))

    g.add((component, DCTERMS.title, Literal(case.assembly)))
    g.add((component, AC.constructionType, Literal(case.construction_type)))
    g.add((component, AC.totalThickness_m, Literal(str(case.thickness_m), datatype=XSD.decimal)))
    g.add((rec, AC.testArea_m2, Literal("10.0", datatype=XSD.decimal)))
    g.add((agent, DCTERMS.title, Literal(case.source)))
    g.add((source, DCTERMS.identifier, Literal(case.source_reference)))
    g.serialize(destination=str(path), format="turtle")


def find_native_doc(model, wall, case: Case):
    for rel in model.by_type("IfcRelAssociatesDocument"):
        if wall not in (getattr(rel, "RelatedObjects", None) or []):
            continue
        doc = getattr(rel, "RelatingDocument", None)
        if doc and doc.is_a("IfcDocumentReference") and str(getattr(doc, "Identification", "")) == case.record_id:
            return doc
    raise RuntimeError(f"[{case.case_id}] native document reference not found")


def retrieve_embedded(path: Path, case: Case):
    model = open_ifc(path)
    wall = get_wall(model, case)
    p = psets(wall).get("Pset_AcousticEmbedded")
    if not p:
        return {f"Q{i}": None for i in range(1, 6)}, "UNMATCHED"
    linked = []
    for candidate in model.by_type("IfcWall"):
        cp = psets(candidate).get("Pset_AcousticEmbedded")
        if cp and str(cp.get("RecordIdentifier")) == case.record_id:
            linked.append({"global_id": candidate.GlobalId, "name": candidate.Name})
    return {
        "Q1": {"value": p.get("AcousticValue"), "unit": p.get("AcousticUnit"), "metric": p.get("AcousticMetric")},
        "Q2": {"assembly": p.get("AssemblyDescription"), "construction": p.get("ConstructionType")},
        "Q3": {"source": p.get("ResponsibleAgent"), "reference": p.get("SourceReference")},
        "Q4": {"method": p.get("MethodType"), "year": p.get("DataYear"), "version": p.get("RecordVersion")},
        "Q5": linked,
    }, "N/A"


def retrieve_native(path: Path, case: Case, resource_map: dict[str, Path]):
    model = open_ifc(path)
    wall = get_wall(model, case)
    doc = find_native_doc(model, wall, case)
    uri = str(doc.Location or "")
    q5 = [{"global_id": wall.GlobalId, "name": wall.Name, "record_uri": uri}]
    external = resource_map.get(uri)
    if external is None or not external.exists():
        return {"Q1": None, "Q2": None, "Q3": None, "Q4": None, "Q5": q5}, "BROKEN"
    p = json.loads(external.read_text(encoding="utf-8"))["record"]
    return {
        "Q1": {"value": p.get("AcousticValue"), "unit": p.get("AcousticUnit"), "metric": p.get("AcousticMetric")},
        "Q2": {"assembly": p.get("AssemblyDescription"), "construction": p.get("ConstructionType")},
        "Q3": {"source": p.get("ResponsibleAgent"), "reference": p.get("SourceReference")},
        "Q4": {"method": p.get("MethodType"), "year": p.get("DataYear"), "version": p.get("RecordVersion")},
        "Q5": q5,
    }, "VALID"


def retrieve_rdf(path: Path, case: Case, registry: Path):
    model = open_ifc(path)
    wall = get_wall(model, case)
    p = psets(wall).get("Pset_AcousticLink")
    if not p:
        return {f"Q{i}": None for i in range(1, 6)}, "UNMATCHED"
    uri = str(p.get("AcousticRecordURI") or "")
    q5 = [{"global_id": wall.GlobalId, "name": wall.Name, "mapping_status": p.get("MappingStatus")}]
    g = Graph()
    g.parse(registry, format="turtle")
    rec = URIRef(uri)
    if not any(g.triples((rec, None, None))):
        return {"Q1": None, "Q2": None, "Q3": None, "Q4": None, "Q5": q5}, "BROKEN"
    component = g.value(rec, AC.describesComponent)
    agent = g.value(rec, PROV.wasAttributedTo)
    return {
        "Q1": {
            "value": str(g.value(rec, AC.weightedSoundReductionIndex)),
            "unit": str(g.value(rec, AC.acousticUnit)),
            "metric": str(g.value(rec, AC.acousticMetric)),
        },
        "Q2": {
            "assembly": str(g.value(component, DCTERMS.title)),
            "construction": str(g.value(component, AC.constructionType)),
        },
        "Q3": {
            "source": str(g.value(agent, DCTERMS.title)),
            "reference": str(g.value(rec, AC.sourceReference)),
        },
        "Q4": {
            "method": str(g.value(rec, AC.methodType)),
            "year": str(g.value(rec, AC.dataYear)),
            "version": str(g.value(rec, DCTERMS.hasVersion)),
        },
        "Q5": q5,
    }, "VALID"


def update_embedded_value(src: Path, dst: Path, case: Case) -> None:
    model = open_ifc(src)
    wall = get_wall(model, case)
    p = psets(wall)["Pset_AcousticEmbedded"]
    ent = model.by_id(int(p["id"]))
    ifcopenshell.api.run("pset.edit_pset", model, pset=ent, properties={"AcousticValue": case.rw + UPDATED_RW_DELTA})
    model.write(str(dst))


def update_embedded_source(src: Path, dst: Path, case: Case) -> None:
    model = open_ifc(src)
    wall = get_wall(model, case)
    p = psets(wall)["Pset_AcousticEmbedded"]
    ent = model.by_id(int(p["id"]))
    ifcopenshell.api.run("pset.edit_pset", model, pset=ent, properties={
        "SourceReference": case.source_reference + " [CONTROLLED REVISION]",
        "RecordVersion": UPDATED_VERSION,
    })
    model.write(str(dst))


def break_native_link(src: Path, dst: Path, case: Case) -> None:
    model = open_ifc(src)
    wall = get_wall(model, case)
    doc = find_native_doc(model, wall, case)
    doc.Location = case.native_uri + ".MISSING"
    model.write(str(dst))


def break_rdf_link(src: Path, dst: Path, case: Case) -> None:
    model = open_ifc(src)
    wall = get_wall(model, case)
    p = psets(wall)["Pset_AcousticLink"]
    ent = model.by_id(int(p["id"]))
    ifcopenshell.api.run("pset.edit_pset", model, pset=ent, properties={"AcousticRecordURI": case.rdf_uri + "/MISSING"})
    model.write(str(dst))


def shift_geometry(src: Path, dst: Path, case: Case) -> None:
    model = open_ifc(src)
    wall = get_wall(model, case)
    placement = wall.ObjectPlacement
    relative = placement.RelativePlacement if placement else None
    location = relative.Location if relative else None
    coords = list(location.Coordinates) if location and location.Coordinates else []
    if not coords:
        raise RuntimeError(f"[{case.case_id}] wall placement could not be resolved")
    coords[0] = float(coords[0]) + GEOMETRY_SHIFT_X_M
    location.Coordinates = tuple(coords)
    model.write(str(dst))


def scenario_signature(rows: list[dict[str, Any]], case_id: str) -> tuple:
    relevant = [r for r in rows if r["case_id"] == case_id]
    return tuple(
        (r["scenario"], r["approach"], r["ifc_modified"], r["external_record_modified"], r["retrieval_questions_successful"], r["link_status"])
        for r in relevant
    )


def main() -> None:
    root = Path(__file__).resolve().parent
    data = root / "data"
    original = data / "HFT_Bau1_2026.02.18.ifc"
    results = root / "results_multiwall"
    results.mkdir(exist_ok=True)

    if not original.exists():
        raise SystemExit(f"Missing original IFC: {original}")

    print("=" * 84)
    print("MULTI-WALL REPLICATION OF THREE-BASELINE ARCHITECTURE EXPERIMENT")
    print("=" * 84)
    print("Original IFC:", original)
    print("Cases:", len(CASES))
    print("NOTE: only pilot_metal_stud uses a real external VaBDat source record.")
    print("      Other acoustic records are controlled synthetic records for architecture replication.\n")

    original_m = metrics(original)
    baseline_rows: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []
    query_results: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="multiwall_architecture_replication_") as td:
        temp = Path(td)

        for case in CASES:
            print(f"\n--- {case.case_id} ---")
            model = open_ifc(original)
            wall = get_wall(model, case)
            print("Wall:", wall.GlobalId, "|", wall.Name)
            print("Record:", case.record_id, "|", "REAL SOURCE" if case.is_real_source_record else "SYNTHETIC CONTROL")

            embedded = temp / f"{case.case_id}_embedded.ifc"
            native = temp / f"{case.case_id}_native.ifc"
            rdf = temp / f"{case.case_id}_rdf.ifc"
            native_json = temp / f"{case.case_id}.json"
            rdf_ttl = temp / f"{case.case_id}.ttl"

            make_embedded(original, embedded, case)
            make_native(original, native, case)
            make_rdf_link(original, rdf, case)
            make_native_json(native_json, case)
            make_rdf_registry(rdf_ttl, case)

            e0, es = retrieve_embedded(embedded, case)
            n0, ns = retrieve_native(native, case, {case.native_uri: native_json})
            r0, rs = retrieve_rdf(rdf, case, rdf_ttl)
            query_results[case.case_id] = {
                "wall_guid": case.wall_guid,
                "wall_name": wall.Name,
                "record_id": case.record_id,
                "record_scope": "real source reference" if case.is_real_source_record else "synthetic architecture control",
                "initial": {"Embedded IFC": e0, "Native IFC reference": n0, "Proposed IFC-RDF": r0},
            }

            for approach, path, payload, status in [
                ("Embedded IFC", embedded, e0, es),
                ("Native IFC reference", native, n0, ns),
                ("Proposed IFC-RDF", rdf, r0, rs),
            ]:
                m = metrics(path)
                baseline_rows.append({
                    "case_id": case.case_id,
                    "wall_global_id": case.wall_guid,
                    "wall_name": wall.Name,
                    "record_scope": "REAL_SOURCE_REFERENCE" if case.is_real_source_record else "SYNTHETIC_CONTROL",
                    "approach": approach,
                    "initial_retrieval_success": count5(payload),
                    "initial_retrieval_total": 5,
                    "link_status": status,
                    "ifc_entities_added": m["entities"] - original_m["entities"],
                    "ifc_single_value_properties_added": m["props"] - original_m["props"],
                    "ifc_bytes_added": m["bytes"] - original_m["bytes"],
                })

            def add(approach, scenario, ifc_edit, ext_edit, payload, status):
                scenario_rows.append({
                    "case_id": case.case_id,
                    "wall_global_id": case.wall_guid,
                    "approach": approach,
                    "scenario": scenario,
                    "ifc_modified": ifc_edit,
                    "external_record_modified": ext_edit,
                    "retrieval_questions_successful": count5(payload),
                    "retrieval_questions_total": 5,
                    "link_status": status,
                })

            add("Embedded IFC", "Initial creation", True, False, e0, "N/A")
            add("Native IFC reference", "Initial creation", True, True, n0, ns)
            add("Proposed IFC-RDF", "Initial creation", True, True, r0, rs)

            e_value = temp / f"{case.case_id}_e_value.ifc"
            update_embedded_value(embedded, e_value, case)
            payload, status = retrieve_embedded(e_value, case)
            add("Embedded IFC", "Acoustic-value update", True, False, payload, status)

            n_value_json = temp / f"{case.case_id}_n_value.json"
            j = json.loads(native_json.read_text(encoding="utf-8"))
            j["record"]["AcousticValue"] = case.rw + UPDATED_RW_DELTA
            n_value_json.write_text(json.dumps(j, indent=2), encoding="utf-8")
            payload, status = retrieve_native(native, case, {case.native_uri: n_value_json})
            add("Native IFC reference", "Acoustic-value update", False, True, payload, status)

            r_value_ttl = temp / f"{case.case_id}_r_value.ttl"
            g = Graph(); g.parse(rdf_ttl, format="turtle"); rec = URIRef(case.rdf_uri)
            for triple in list(g.triples((rec, AC.weightedSoundReductionIndex, None))): g.remove(triple)
            g.add((rec, AC.weightedSoundReductionIndex, Literal(str(case.rw + UPDATED_RW_DELTA), datatype=XSD.decimal)))
            g.serialize(destination=str(r_value_ttl), format="turtle")
            payload, status = retrieve_rdf(rdf, case, r_value_ttl)
            add("Proposed IFC-RDF", "Acoustic-value update", False, True, payload, status)

            e_source = temp / f"{case.case_id}_e_source.ifc"
            update_embedded_source(embedded, e_source, case)
            payload, status = retrieve_embedded(e_source, case)
            add("Embedded IFC", "Provenance/source update", True, False, payload, status)

            n_source_json = temp / f"{case.case_id}_n_source.json"
            j = json.loads(native_json.read_text(encoding="utf-8"))
            j["record"]["SourceReference"] = case.source_reference + " [CONTROLLED REVISION]"
            j["record"]["RecordVersion"] = UPDATED_VERSION
            n_source_json.write_text(json.dumps(j, indent=2), encoding="utf-8")
            payload, status = retrieve_native(native, case, {case.native_uri: n_source_json})
            add("Native IFC reference", "Provenance/source update", False, True, payload, status)

            r_source_ttl = temp / f"{case.case_id}_r_source.ttl"
            g = Graph(); g.parse(rdf_ttl, format="turtle"); rec = URIRef(case.rdf_uri)
            for triple in list(g.triples((rec, AC.sourceReference, None))): g.remove(triple)
            for triple in list(g.triples((rec, DCTERMS.hasVersion, None))): g.remove(triple)
            g.add((rec, AC.sourceReference, Literal(case.source_reference + " [CONTROLLED REVISION]")))
            g.add((rec, DCTERMS.hasVersion, Literal(UPDATED_VERSION)))
            g.serialize(destination=str(r_source_ttl), format="turtle")
            payload, status = retrieve_rdf(rdf, case, r_source_ttl)
            add("Proposed IFC-RDF", "Provenance/source update", False, True, payload, status)

            add("Embedded IFC", "Broken-link case", False, False, e0, "N/A")
            n_broken = temp / f"{case.case_id}_n_broken.ifc"
            break_native_link(native, n_broken, case)
            payload, status = retrieve_native(n_broken, case, {case.native_uri: native_json})
            add("Native IFC reference", "Broken-link case", True, False, payload, status)
            r_broken = temp / f"{case.case_id}_r_broken.ifc"
            break_rdf_link(rdf, r_broken, case)
            payload, status = retrieve_rdf(r_broken, case, rdf_ttl)
            add("Proposed IFC-RDF", "Broken-link case", True, False, payload, status)

            
            print("Initial retrieval:", f"Embedded {count5(e0)}/5 | Native {count5(n0)}/5 | RDF {count5(r0)}/5")

    write_csv(results / "multiwall_baseline_metrics.csv", baseline_rows)
    write_csv(results / "multiwall_scenario_results.csv", scenario_rows)
    (results / "multiwall_query_results.json").write_text(json.dumps(query_results, indent=2, ensure_ascii=False), encoding="utf-8")

    signatures = {case.case_id: scenario_signature(scenario_rows, case.case_id) for case in CASES}
    first = signatures[CASES[0].case_id]
    same_pattern = [case.case_id for case in CASES if signatures[case.case_id] == first]

    print("\n" + "=" * 84)
    print("REPLICATION SUMMARY")
    print("=" * 84)
    print(f"Same scenario outcome pattern as first case: {len(same_pattern)}/{len(CASES)} cases")
    for case in CASES:
        print(f"  {case.case_id:<24} {'SAME' if case.case_id in same_pattern else 'DIFFERENT'}")

    print("\nIFC OVERHEAD BY CASE")
    print(f"{'Case':<24} {'Approach':<24} {'Entities':>8} {'Props':>7} {'Bytes':>9}")
    for row in baseline_rows:
        print(f"{row['case_id']:<24} {row['approach']:<24} {row['ifc_entities_added']:>8} {row['ifc_single_value_properties_added']:>7} {row['ifc_bytes_added']:>9}")

    print("\nInterpretation:")
    if len(same_pattern) == len(CASES):
        print("  The controlled architectural behavior replicated across all selected walls.")
        print("  This supports the expectation that update-coupling and broken-link behavior are properties")
        print("  of the representation architecture, not of wall material/type.")
    else:
        print("  At least one case behaved differently. Inspect multiwall_scenario_results.csv before drawing conclusions.")

    print("\nResult files:")
    for p in [results / "multiwall_baseline_metrics.csv", results / "multiwall_scenario_results.csv", results / "multiwall_query_results.json"]:
        print(" ", p)


if __name__ == "__main__":
    main()
