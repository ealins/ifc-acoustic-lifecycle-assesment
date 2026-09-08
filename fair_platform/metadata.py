from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from .models import FairAcousticPackage

FAIRAC = Namespace("https://example.org/fair-acoustic/vocab/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")


def build_metadata_graph(package: FairAcousticPackage) -> Graph:
    graph = Graph()
    graph.bind("fairac", FAIRAC)
    graph.bind("dct", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("dcat", DCAT)

    package_uri = URIRef(package.identifier)
    geometry_uri = URIRef(f"{package.identifier}#geometry")
    measurement_uri = URIRef(package.dataset_uri or f"{package.identifier}#measurement")

    graph.add((package_uri, RDF.type, FAIRAC.FairAcousticPackage))
    graph.add((package_uri, DCTERMS.identifier, Literal(package.package_id)))
    graph.add((package_uri, DCTERMS.hasVersion, Literal(package.version)))
    graph.add((package_uri, DCTERMS.created, Literal(package.created, datatype=XSD.dateTime)))
    graph.add((package_uri, FAIRAC.hasGeometry, geometry_uri))
    graph.add((package_uri, FAIRAC.hasMeasurement, measurement_uri))
    graph.add((package_uri, FAIRAC.fairStatus, Literal(package.fair_status.value)))
    graph.add((package_uri, FAIRAC.lifecycleStatus, Literal(package.lifecycle_status)))

    if package.creator:
        graph.add((package_uri, DCTERMS.creator, Literal(package.creator)))
    if package.license:
        graph.add((package_uri, DCTERMS.license, URIRef(package.license) if package.license.startswith("http") else Literal(package.license)))
    if package.mapping_series_uri:
        graph.add((package_uri, FAIRAC.stewardedBy, URIRef(package.mapping_series_uri)))

    graph.add((geometry_uri, RDF.type, FAIRAC.IFCGeometry))
    if package.ifc_global_id:
        graph.add((geometry_uri, FAIRAC.ifcGlobalId, Literal(package.ifc_global_id)))
    graph.add((geometry_uri, DCTERMS.format, Literal("IFC")))

    graph.add((measurement_uri, RDF.type, DCAT.Dataset))
    graph.add((measurement_uri, DCTERMS.identifier, Literal(package.metadata.get("measurement_identifier", package.package_id))))
    graph.add((measurement_uri, DCTERMS.format, Literal(package.metadata.get("measurement_media_type", "application/octet-stream"))))

    for key, value in package.measurement_context.items():
        if value not in (None, "", []):
            graph.add((measurement_uri, FAIRAC[str(key)], Literal(str(value))))

    for key, value in package.quality_information.items():
        if value not in (None, "", []):
            graph.add((measurement_uri, FAIRAC[str(key)], Literal(str(value))))

    provenance_agent = package.provenance.get("institution") or package.provenance.get("creator")
    if provenance_agent:
        agent_uri = URIRef(f"{package.identifier}#agent")
        graph.add((agent_uri, RDF.type, PROV.Agent))
        graph.add((agent_uri, DCTERMS.title, Literal(str(provenance_agent))))
        graph.add((measurement_uri, PROV.wasAttributedTo, agent_uri))

    return graph


def metadata_turtle(package: FairAcousticPackage) -> str:
    return build_metadata_graph(package).serialize(format="turtle")
