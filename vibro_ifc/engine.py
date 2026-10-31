"""Engine for the v0.6 SLDV sidecar profile (vibro_ifc.engine).

The sidecar is a JSON-LD record built from published vocabularies.  This module
reads a record, validates it against the v0.6 SHACL shapes, checks the
files it points to against their recorded SHA-256 values, lists the fields it
declares as absent or unresolved, and derives the class-level graph shown in
the dashboard.  The Blender add-on is a separate consumer of the same records.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef

PROFILE_DIR = Path(__file__).resolve().parent.parent / "profile" / "v0.6"
RECORDS_DIR = PROFILE_DIR / "records"
SHAPES_PATH = PROFILE_DIR / "shapes_v0.6.ttl"

SH = Namespace("http://www.w3.org/ns/shacl#")
DQV = Namespace("http://www.w3.org/ns/dqv#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
SPDX = Namespace("http://spdx.org/rdf/terms#")
LS = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#")
LDV = Namespace("https://example.org/ldv/profile#")
BOT = Namespace("https://w3id.org/bot#")
OWL_VERSION = URIRef("http://www.w3.org/2002/07/owl#versionInfo")

# namespace -> (prefix, steward).  Stewards are as named in the attribute map.
VOCABULARIES: dict[str, tuple[str, str]] = {
    "http://www.w3.org/ns/sosa/": ("sosa", "W3C / OGC"),
    "http://www.w3.org/ns/ssn/systems/": ("ssn-system", "W3C / OGC"),
    "http://www.w3.org/ns/prov#": ("prov", "W3C"),
    "http://www.w3.org/ns/dcat#": ("dcat", "W3C"),
    "http://www.w3.org/ns/csvw#": ("csvw", "W3C"),
    "http://www.w3.org/ns/dqv#": ("dqv", "W3C"),
    "http://purl.org/dc/terms/": ("dcterms", "DCMI"),
    "http://spdx.org/rdf/terms#": ("spdx", "SPDX"),
    "http://qudt.org/schema/qudt/": ("qudt", "QUDT"),
    "https://w3id.org/bot#": ("bot", "W3C LBD CG"),
    "http://www.opengis.net/ont/geosparql#": ("geo", "OGC"),
    "https://schema.org/": ("schema", "schema.org"),
    "http://xmlns.com/foaf/0.1/": ("foaf", "FOAF"),
    "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#": ("ls", "ISO 21597"),
    "https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#": ("ifc", "buildingSMART"),
    "http://www.w3.org/2004/02/skos/core#": ("skos", "W3C"),
    "http://www.w3.org/2002/07/owl#": ("owl", "W3C"),
    "https://example.org/ldv/profile#": ("ldv", "this thesis"),
}


def _local(iri: Any) -> str:
    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rstrip("/").rsplit("/", 1)[-1]


def vocabulary_of(iri: Any) -> tuple[str, str]:
    text = str(iri)
    for ns, info in VOCABULARIES.items():
        if text.startswith(ns):
            return info
    return ("other", "unknown")


# --------------------------------------------------------------------- loading
def list_records(records_dir: Path | str = RECORDS_DIR) -> list[Path]:
    return sorted(Path(records_dir).glob("point_*.jsonld"))


def load_record(path: Path | str) -> Graph:
    return Graph().parse(str(path), format="json-ld")


# ------------------------------------------------------------------ validation
def validate_record(graph: Graph, shapes_path: Path | str = SHAPES_PATH) -> dict[str, Any]:
    """Run the v0.6 shapes.  Violation = mandatory, Warning = recommended or known gap."""
    from pyshacl import validate

    shapes = Graph().parse(str(shapes_path), format="turtle")
    conforms, report, _ = validate(graph, shacl_graph=shapes, inference="none")
    rows = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        path = report.value(result, SH.resultPath)
        rows.append({
            "severity": _local(report.value(result, SH.resultSeverity)),
            "focus": _local(report.value(result, SH.focusNode)),
            "path": _local(path) if path else "-",
            "message": str(report.value(result, SH.resultMessage) or ""),
        })
    order = {"Violation": 0, "Warning": 1, "Info": 2}
    rows.sort(key=lambda r: (order.get(r["severity"], 3), r["focus"], r["path"]))
    counts = Counter(r["severity"] for r in rows)
    return {
        "conforms": bool(conforms),
        "violations": counts.get("Violation", 0),
        "warnings": counts.get("Warning", 0),
        "results": rows,
        "shape_triples": len(shapes),
        "data_triples": len(graph),
    }


# ---------------------------------------------------------------- file checks
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_checks(graph: Graph, data_dir: Path | str | None) -> list[dict[str, Any]]:
    """Compare every file the record points to with its recorded SHA-256.

    Status is `match`, `MISMATCH`, or `file not found` (the dashboard does not
    treat a missing file as a failure: the record can travel without the data).
    """
    rows = []
    folder = Path(data_dir) if data_dir else None
    for dist in graph.subjects(RDF.type, DCAT.Distribution):
        url = graph.value(dist, DCAT.downloadURL)
        node = graph.value(dist, SPDX.checksum)
        value = graph.value(node, SPDX.checksumValue) if node is not None else None
        if url is None:
            continue
        name = str(url).rsplit("/", 1)[-1]
        role = "IFC model" if name.lower().endswith(".ifc") else "Measurement file"
        status, actual = "file not found", ""
        if folder is not None and (folder / name).is_file():
            actual = _sha256(folder / name)
            status = "match" if value is not None and actual == str(value) else "MISMATCH"
        rows.append({"role": role, "file": name, "recorded": str(value or ""), "actual": actual, "status": status})
    rows.sort(key=lambda r: r["role"])
    return rows


# --------------------------------------------------------------------- gaps
def gap_report(graph: Graph) -> dict[str, Any]:
    """Fields the record itself declares as absent or unresolved, and status notes."""
    absent: list[str] = []
    unresolved: list[str] = []
    notes: list[dict[str, str]] = []
    unit_pending = 0
    for m in graph.subjects(RDF.type, DQV.QualityMeasurement):
        metric = _local(graph.value(m, DQV.isMeasurementOf) or "")
        values = [str(v) for v in graph.objects(m, DQV.value)]
        if metric == "absentFields":
            absent.extend(values)
        elif metric == "unresolvedFields":
            unresolved.extend(values)
        elif metric == "unitStatus" and values and "not yet resolved" in values[0]:
            unit_pending += 1
        else:
            notes.append({"metric": metric, "value": "; ".join(values)})
    return {"absent": sorted(absent), "unresolved": sorted(unresolved),
            "units_pending": unit_pending, "notes": notes}


# -------------------------------------------------------------- architecture
def summary(graph: Graph) -> dict[str, Any]:
    """Facts for the three-layer view: data file, sidecar, IFC element, trust flags."""
    record = next(graph.subjects(RDF.type, DCAT.CatalogRecord), None)
    link = next(graph.subjects(RDF.type, LS.DirectedLink), None)
    wall = next(graph.subjects(RDF.type, BOT.Element), None)
    guid = ""
    for ident in graph.subjects(RDF.type, LS.StringBasedIdentifier):
        guid = str(graph.value(ident, LS.identifier) or "")
    hypothesis = next(graph.subjects(RDF.type, LDV.RegistrationHypothesis), None)
    hyp_status = ""
    if hypothesis is not None:
        for m in graph.objects(hypothesis, DQV.hasQualityMeasurement):
            hyp_status = str(graph.value(m, DQV.value) or "")
    files = {r["role"]: r["file"] for r in data_checks(graph, None)}
    return {
        "record": _local(record) if record else "",
        "profile": str(graph.value(record, OWL_VERSION) or "") if record else "",
        "measurement_file": files.get("Measurement file", ""),
        "ifc_file": files.get("IFC model", ""),
        "ifc_label": str(graph.value(wall, URIRef("http://www.w3.org/2000/01/rdf-schema#label")) or "") if wall else "",
        "global_id": guid,
        "association_level": str(graph.value(link, LDV.associationLevel) or "") if link else "",
        "registration": str(graph.value(link, LDV.registration) or "") if link else "",
        "hypothesis_source": next((str(o) for pr, o in graph.predicate_objects(hypothesis) if _local(pr) == "source"), "") if hypothesis else "",
        "hypothesis_status": hyp_status,
        "triples": len(graph),
    }


# ------------------------------------------------------------------ node graph
def class_graph(graph: Graph, include_quality: bool = False) -> dict[str, Any]:
    """Class-level graph: one node per class, edges counted over instances."""
    def classes_of(node) -> list[str]:
        return [str(t) for t in graph.objects(node, RDF.type) if isinstance(t, URIRef)]

    skip = {str(DQV.QualityMeasurement)}
    counts: Counter[str] = Counter()
    for node in set(graph.subjects(RDF.type, None)):
        for cls in classes_of(node):
            if include_quality or cls not in skip:
                counts[cls] += 1
    edges: dict[tuple[str, str, str], int] = defaultdict(int)
    for s, p, o in graph:
        if p == RDF.type or not isinstance(o, (URIRef, BNode)):
            continue
        for sc in classes_of(s):
            for oc in classes_of(o):
                if not include_quality and (sc in skip or oc in skip):
                    continue
                if sc in counts and oc in counts:
                    edges[(sc, _local(p), oc)] += 1
    nodes = []
    for cls, n in counts.items():
        prefix, steward = vocabulary_of(cls)
        nodes.append({"id": cls, "label": f"{prefix}:{_local(cls)}", "prefix": prefix,
                      "steward": steward, "count": n, "own": prefix == "ldv"})
    links = [{"source": a, "label": p, "target": b, "count": n} for (a, p, b), n in edges.items()]
    return {"nodes": sorted(nodes, key=lambda n: -n["count"]), "links": links}


def vocabulary_table(graph: Graph) -> list[dict[str, Any]]:
    """Classes per vocabulary: shows which parts reuse published terms and which are own."""
    table: dict[str, dict[str, Any]] = {}
    for node in class_graph(graph)["nodes"]:
        row = table.setdefault(node["prefix"], {"vocabulary": node["prefix"], "steward": node["steward"], "classes": 0, "instances": 0})
        row["classes"] += 1
        row["instances"] += node["count"]
    return sorted(table.values(), key=lambda r: (-r["classes"], r["vocabulary"]))
