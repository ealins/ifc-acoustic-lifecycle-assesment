from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Namespace, RDF

from .metadata import build_metadata_graph
from .models import FairAcousticPackage

SH = Namespace("http://www.w3.org/ns/shacl#")


def _default_shapes_path() -> Path:
    return Path(__file__).resolve().parent.parent / "metadata" / "fair_shapes.ttl"


def validate_package_shacl(package: FairAcousticPackage, shapes_path: str | Path | None = None) -> dict:
    """Execute the repository SHACL profile against generated package metadata.

    The returned report is JSON-serializable so conformance and individual violations
    can be displayed in Streamlit and retained as package evidence.
    """
    try:
        from pyshacl import validate
    except ImportError as exc:
        return {
            "available": False,
            "conforms": False,
            "violation_count": 0,
            "results": [],
            "report_text": f"pyshacl is not installed: {exc}",
            "shapes_path": str(shapes_path or _default_shapes_path()),
        }

    path = Path(shapes_path or _default_shapes_path())
    shapes_graph = Graph().parse(path, format="turtle")
    data_graph = build_metadata_graph(package)
    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        meta_shacl=True,
        advanced=True,
    )

    results = []
    for node in report_graph.subjects(RDF.type, SH.ValidationResult):
        messages = [str(value) for value in report_graph.objects(node, SH.resultMessage)]
        paths = [str(value) for value in report_graph.objects(node, SH.resultPath)]
        focus_nodes = [str(value) for value in report_graph.objects(node, SH.focusNode)]
        severities = [str(value).rsplit("#", 1)[-1] for value in report_graph.objects(node, SH.resultSeverity)]
        source_shapes = [str(value) for value in report_graph.objects(node, SH.sourceShape)]
        results.append({
            "focus_node": focus_nodes[0] if focus_nodes else "",
            "path": paths[0] if paths else "",
            "severity": severities[0] if severities else "Violation",
            "message": " | ".join(messages) if messages else "SHACL constraint violation",
            "source_shape": source_shapes[0] if source_shapes else "",
        })

    return {
        "available": True,
        "conforms": bool(conforms),
        "violation_count": len(results),
        "results": results,
        "report_text": str(report_text),
        "shapes_path": str(path),
        "data_triples": len(data_graph),
        "shape_triples": len(shapes_graph),
    }
