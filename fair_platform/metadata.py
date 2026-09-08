from __future__ import annotations

import re
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from .models import FairAcousticPackage

FAIRAC = Namespace("https://example.org/fair-acoustic/vocab/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")


def _term(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_") or "value"


def _uri(value: str | None, fallback: str) -> URIRef:
    text = str(value or "").strip()
    return URIRef(text if text.startswith(("http://", "https://", "urn:")) else fallback)


def build_metadata_graph(package: FairAcousticPackage) -> Graph:
    graph = Graph()
    graph.bind("fairac", FAIRAC)
    graph.bind("dct", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("dcat", DCAT)

    package_uri = _uri(package.identifier, f"https://example.org/fair-acoustic/package/{package.package_id}")
    geometry_uri = URIRef(f"{package_uri}#geometry")
    measurement_uri = _uri(package.dataset_uri, f"{package_uri}#measurement")
    metadata_uri = URIRef(f"{package_uri}#metadata")

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
    for key in ("geometry_ifc_class", "geometry_name", "geometry_construction_family", "geometry_total_thickness_m"):
        value = package.metadata.get(key)
        if value not in (None, "", []):
            graph.add((geometry_uri, FAIRAC[_term(key)], Literal(str(value))))
    for material in package.metadata.get("geometry_materials", []) or []:
        graph.add((geometry_uri, FAIRAC.material, Literal(str(material))))

    graph.add((measurement_uri, RDF.type, FAIRAC.MeasurementDataset))
    graph.add((measurement_uri, RDF.type, DCAT.Dataset))
    graph.add((measurement_uri, DCTERMS.identifier, Literal(package.metadata.get("measurement_identifier", package.package_id))))
    graph.add((measurement_uri, DCTERMS.format, Literal(package.metadata.get("measurement_media_type", "application/octet-stream"))))
    graph.add((package_uri, PROV.wasDerivedFrom, geometry_uri))
    graph.add((package_uri, PROV.wasDerivedFrom, measurement_uri))

    for key, value in package.measurement_context.items():
        if value not in (None, "", []):
            graph.add((measurement_uri, FAIRAC[_term(key)], Literal(str(value))))
    for key, value in package.quality_information.items():
        if value not in (None, "", []):
            graph.add((measurement_uri, FAIRAC[_term(key)], Literal(str(value))))

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
