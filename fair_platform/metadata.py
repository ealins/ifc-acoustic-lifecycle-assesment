from __future__ import annotations

import re
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from .models import FairAcousticPackage

FAIRAC = Namespace("https://example.org/fair-acoustic/vocab/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
SH = Namespace("http://www.w3.org/ns/shacl#")


def _term(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_") or "value"


def _uri(value: str | None, fallback: str) -> URIRef:
    text = str(value or "").strip()
    return URIRef(text if text.startswith(("http://", "https://", "urn:")) else fallback)


def _add_context(graph: Graph, subject: URIRef, context: dict) -> None:
    for key, value in context.items():
        if value in (None, "", []):
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if item not in (None, ""):
                    graph.add((subject, FAIRAC[_term(key)], Literal(str(item))))
        elif isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if nested_value not in (None, "", []):
                    graph.add((subject, FAIRAC[_term(f"{key}_{nested_key}")], Literal(str(nested_value))))
        else:
            graph.add((subject, FAIRAC[_term(key)], Literal(str(value))))


def _add_supplementary_resources(
    graph: Graph,
    package_uri: URIRef,
    parent_uri: URIRef,
    records: list[dict] | None,
    role: str,
) -> None:
    for index, record in enumerate(records or [], start=1):
        path = str(record.get("path") or f"{role}-{index}")
        node = URIRef(f"{package_uri}#{role}-resource-{index}")
        graph.add((node, RDF.type, DCAT.Distribution))
        graph.add((node, RDF.type, FAIRAC.ResearchResource))
        graph.add((node, DCTERMS.identifier, Literal(path)))
        graph.add((node, FAIRAC.filePath, Literal(path)))
        graph.add((node, FAIRAC.resourceRole, Literal(role)))
        if record.get("source_filename"):
            graph.add((node, DCTERMS.title, Literal(str(record["source_filename"]))))
        if record.get("media_type"):
            graph.add((node, DCTERMS.format, Literal(str(record["media_type"]))))
        graph.add((package_uri, FAIRAC.hasResearchResource, node))
        graph.add((parent_uri, FAIRAC.hasResource, node))


def build_metadata_graph(package: FairAcousticPackage) -> Graph:
    graph = Graph()
    graph.bind("fairac", FAIRAC)
    graph.bind("dct", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("dcat", DCAT)
    graph.bind("sh", SH)

    package_uri = _uri(package.identifier, f"https://example.org/fair-acoustic/package/{package.package_id}")
    geometry_uri = URIRef(f"{package_uri}#geometry")
    measurement_uri = _uri(package.dataset_uri, f"{package_uri}#measurement")
    metadata_uri = URIRef(f"{package_uri}#metadata")
    research_uri = URIRef(f"{package_uri}#research-study")
    simulation_uri = URIRef(f"{package_uri}#simulation-study")

    graph.add((package_uri, RDF.type, FAIRAC.FairAcousticPackage))
    graph.add((package_uri, RDF.type, DCAT.Dataset))
    graph.add((package_uri, DCTERMS.identifier, Literal(package.package_id)))
    graph.add((package_uri, DCTERMS.title, Literal(package.title)))
    graph.add((package_uri, DCTERMS.hasVersion, Literal(package.version)))
    graph.add((package_uri, DCTERMS.created, Literal(package.created, datatype=XSD.dateTime)))
    graph.add((package_uri, FAIRAC.hasGeometry, geometry_uri))
    graph.add((package_uri, FAIRAC.hasMeasurement, measurement_uri))
    graph.add((package_uri, FAIRAC.hasMetadata, metadata_uri))
    graph.add((package_uri, FAIRAC.fairStatus, Literal(package.fair_status.value)))
    graph.add((package_uri, FAIRAC.lifecycleStatus, Literal(package.lifecycle_display_status)))
    graph.add((package_uri, FAIRAC.findable, Literal(package.findable, datatype=XSD.boolean)))
    graph.add((package_uri, FAIRAC.accessible, Literal(package.accessible, datatype=XSD.boolean)))
    graph.add((package_uri, FAIRAC.interoperable, Literal(package.interoperable, datatype=XSD.boolean)))
    graph.add((package_uri, FAIRAC.reusable, Literal(package.reusable, datatype=XSD.boolean)))

    if package.research_context:
        graph.add((package_uri, FAIRAC.hasResearchStudy, research_uri))
        graph.add((research_uri, RDF.type, FAIRAC.AcousticResearchStudy))
        graph.add((research_uri, PROV.wasDerivedFrom, geometry_uri))
        graph.add((research_uri, PROV.wasDerivedFrom, measurement_uri))
        _add_context(graph, research_uri, package.research_context)

    if package.simulation_context:
        graph.add((package_uri, FAIRAC.hasSimulationStudy, simulation_uri))
        graph.add((simulation_uri, RDF.type, FAIRAC.AcousticSimulationStudy))
        graph.add((simulation_uri, PROV.used, geometry_uri))
        graph.add((simulation_uri, PROV.wasAssociatedWith, research_uri))
        _add_context(graph, simulation_uri, package.simulation_context)

    _add_supplementary_resources(
        graph,
        package_uri,
        simulation_uri,
        package.metadata.get("simulation_resources"),
        "simulation",
    )
    _add_supplementary_resources(
        graph,
        package_uri,
        research_uri,
        package.metadata.get("research_resources"),
        "research",
    )

    shacl = package.metadata.get("shacl_validation") or {}
    if shacl:
        graph.add((package_uri, FAIRAC.shaclValidationAvailable, Literal(bool(shacl.get("available")), datatype=XSD.boolean)))
        graph.add((package_uri, FAIRAC.shaclConforms, Literal(bool(shacl.get("conforms")), datatype=XSD.boolean)))
        graph.add((package_uri, FAIRAC.shaclViolationCount, Literal(int(shacl.get("violation_count", 0)), datatype=XSD.integer)))

    if package.metadata.get("description"):
        graph.add((package_uri, DCTERMS.description, Literal(package.metadata["description"])))
    keywords = package.metadata.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [item.strip() for item in keywords.split(",") if item.strip()]
    for keyword in keywords:
        graph.add((package_uri, DCTERMS.subject, Literal(keyword)))
    if package.creator:
        graph.add((package_uri, DCTERMS.creator, Literal(package.creator)))
    if package.license:
        license_value = URIRef(package.license) if str(package.license).startswith(("http://", "https://", "urn:")) else Literal(package.license)
        graph.add((package_uri, DCTERMS.license, license_value))
    if package.mapping_series_uri:
        graph.add((package_uri, FAIRAC.stewardedBy, URIRef(package.mapping_series_uri)))
    if package.latest_mapping_assertion_uri:
        graph.add((package_uri, FAIRAC.latestStewardshipAssertion, URIRef(package.latest_mapping_assertion_uri)))

    graph.add((geometry_uri, RDF.type, FAIRAC.IFCGeometry))
    graph.add((geometry_uri, DCTERMS.format, Literal("IFC")))
    graph.add((geometry_uri, DCTERMS.identifier, Literal(package.geometry_reference)))
    if package.ifc_global_id:
        graph.add((geometry_uri, FAIRAC.ifcGlobalId, Literal(package.ifc_global_id)))
    for key in ("geometry_ifc_class", "geometry_name", "geometry_construction_family", "geometry_total_thickness_m", "geometry_semantic_classification"):
        value = package.metadata.get(key)
        if value not in (None, "", []):
            graph.add((geometry_uri, FAIRAC[_term(key)], Literal(str(value))))
    for material in package.metadata.get("geometry_materials", []) or []:
        graph.add((geometry_uri, FAIRAC.material, Literal(str(material))))
    spatial = package.metadata.get("geometry_spatial_context") or {}
    if isinstance(spatial, dict):
        for key, value in spatial.items():
            if value not in (None, "", []):
                graph.add((geometry_uri, FAIRAC[_term(f"spatial_{key}")], Literal(str(value))))

    graph.add((measurement_uri, RDF.type, FAIRAC.MeasurementDataset))
    graph.add((measurement_uri, RDF.type, DCAT.Dataset))
    graph.add((measurement_uri, DCTERMS.identifier, Literal(package.metadata.get("measurement_identifier", package.package_id))))
    graph.add((measurement_uri, DCTERMS.format, Literal(package.metadata.get("measurement_media_type", "application/octet-stream"))))
    graph.add((package_uri, PROV.wasDerivedFrom, geometry_uri))
    graph.add((package_uri, PROV.wasDerivedFrom, measurement_uri))

    inspection = package.metadata.get("measurement_inspection") or {}
    if inspection:
        graph.add((measurement_uri, FAIRAC.inspectionValid, Literal(bool(inspection.get("valid")), datatype=XSD.boolean)))
        graph.add((measurement_uri, FAIRAC.inspectedFormat, Literal(str(inspection.get("format", "")))))
        graph.add((measurement_uri, FAIRAC.inspectionSummary, Literal(str(inspection.get("summary", "")))))
        for signal in inspection.get("semantic_signals", []) or []:
            graph.add((measurement_uri, FAIRAC.detectedSignal, Literal(str(signal))))

    _add_context(graph, measurement_uri, package.measurement_context)
    _add_context(graph, measurement_uri, package.quality_information)

    graph.add((metadata_uri, RDF.type, FAIRAC.MetadataRecord))
    graph.add((metadata_uri, DCTERMS.format, Literal("text/turtle")))
    graph.add((metadata_uri, DCTERMS.identifier, Literal(package.metadata_reference)))

    agent_name = package.provenance.get("institution") or package.provenance.get("creator") or package.creator
    if agent_name:
        agent_uri = URIRef(f"{package_uri}#agent")
        graph.add((agent_uri, RDF.type, PROV.Agent))
        graph.add((agent_uri, DCTERMS.title, Literal(str(agent_name))))
        graph.add((package_uri, PROV.wasAttributedTo, agent_uri))
        graph.add((measurement_uri, PROV.wasAttributedTo, agent_uri))
        if package.research_context:
            graph.add((research_uri, PROV.wasAssociatedWith, agent_uri))
        if package.simulation_context:
            graph.add((simulation_uri, PROV.wasAssociatedWith, agent_uri))

    for path, checksum in package.checksums.items():
        checksum_node = URIRef(f"{package_uri}#checksum-{_term(path)}")
        graph.add((checksum_node, RDF.type, FAIRAC.Checksum))
        graph.add((checksum_node, FAIRAC.filePath, Literal(path)))
        graph.add((checksum_node, FAIRAC.sha256, Literal(checksum.replace("sha256:", ""))))
        graph.add((package_uri, FAIRAC.hasChecksum, checksum_node))

    stewardship_ttl = package.metadata.get("stewardship_rdf_turtle")
    if stewardship_ttl:
        try:
            stewardship = Graph().parse(data=stewardship_ttl, format="turtle")
            graph += stewardship
        except Exception:
            pass

    return graph


def metadata_turtle(package: FairAcousticPackage) -> str:
    return build_metadata_graph(package).serialize(format="turtle")
