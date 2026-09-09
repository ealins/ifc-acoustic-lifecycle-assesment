from __future__ import annotations

import re
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from .models import FairAcousticPackage

FAIRAC = Namespace("https://example.org/fair-acoustic/vocab/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
SH = Namespace("http://www.w3.org/ns/shacl#")
SCHEMA = Namespace("https://schema.org/")


def _term(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_") or "value"


def _uri(value: str | None, fallback: str) -> URIRef:
    text = str(value or "").strip()
    return URIRef(text if text.startswith(("http://", "https://", "urn:")) else fallback)


def _add_context(graph: Graph, subject: URIRef, context: dict) -> None:
    for key, value in context.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if item not in (None, ""):
                    graph.add((subject, FAIRAC[_term(key)], Literal(str(item))))
        elif isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if nested_value not in (None, "", [], {}):
                    graph.add((subject, FAIRAC[_term(f"{key}_{nested_key}")], Literal(str(nested_value))))
        else:
            graph.add((subject, FAIRAC[_term(key)], Literal(str(value))))


def _add_supplementary_resources(graph: Graph, package_uri: URIRef, parent_uri: URIRef, records: list[dict] | None, role: str) -> None:
    for index, record in enumerate(records or [], start=1):
        path = str(record.get("path") or f"{role}-{index}")
        node = URIRef(f"{package_uri}#{role}-resource-{index}")
        graph.add((node, RDF.type, DCAT.Distribution))
        graph.add((node, RDF.type, FAIRAC.ResearchResource))
        graph.add((node, DCTERMS.identifier, Literal(path)))
        graph.add((node, FAIRAC.filePath, Literal(path)))
        graph.add((node, FAIRAC.resourceRole, Literal(role)))
        if record.get("original_filename") or record.get("source_filename"):
            graph.add((node, DCTERMS.title, Literal(str(record.get("original_filename") or record.get("source_filename")))))
        if record.get("media_type"):
            graph.add((node, DCTERMS.format, Literal(str(record["media_type"]))))
        if record.get("version"):
            graph.add((node, DCTERMS.hasVersion, Literal(str(record["version"]))))
        if record.get("source_uri"):
            graph.add((node, DCAT.accessURL, URIRef(str(record["source_uri"]))))
        graph.add((package_uri, FAIRAC.hasResearchResource, node))
        graph.add((parent_uri, FAIRAC.hasResource, node))


def _add_relationships(graph: Graph, package_uri: URIRef, component_uri: URIRef, measurement_uri: URIRef, package: FairAcousticPackage) -> None:
    for relationship in package.relationships:
        rid = str(relationship.get("relationship_id") or "unidentified")
        rel_uri = URIRef(f"{package_uri}#relationship-{_term(rid)}")
        graph.add((rel_uri, RDF.type, FAIRAC.GeometryMeasurementRelationship))
        graph.add((rel_uri, DCTERMS.identifier, Literal(rid)))
        graph.add((rel_uri, FAIRAC.subjectComponent, component_uri))
        graph.add((rel_uri, FAIRAC.objectMeasurement, measurement_uri))
        graph.add((rel_uri, FAIRAC.relationshipType, Literal(str(relationship.get("relationship_type") or "unknownRelationship"))))
        graph.add((package_uri, FAIRAC.hasGeometryMeasurementRelationship, rel_uri))
        for key in (
            "scope", "rationale", "confidence_basis", "created_at", "created_by", "approved_at", "approved_by",
            "approval_status", "last_reviewed_at", "last_reviewed_by", "relationship_version", "source_component_version",
            "source_measurement_version", "source_ifc_checksum", "source_dataset_checksum", "status", "recommended_action",
            "supersedes_relationship", "invalidated_by", "notes",
        ):
            value = relationship.get(key)
            if value not in (None, "", [], {}):
                graph.add((rel_uri, FAIRAC[_term(key)], Literal(str(value))))
        for value in relationship.get("matching_attributes", []) or []:
            graph.add((rel_uri, FAIRAC.matchingAttribute, Literal(str(value))))
        for value in relationship.get("excluded_attributes", []) or []:
            graph.add((rel_uri, FAIRAC.excludedAttribute, Literal(str(value))))
        for evidence in relationship.get("evidence", []) or []:
            eid = str(evidence.get("evidence_id") or "unidentified")
            evi_uri = URIRef(f"{package_uri}#evidence-{_term(eid)}")
            graph.add((evi_uri, RDF.type, FAIRAC.EvidenceItem))
            graph.add((evi_uri, DCTERMS.identifier, Literal(eid)))
            graph.add((rel_uri, FAIRAC.hasEvidence, evi_uri))
            for key in (
                "evidence_type", "observed_value", "expected_value", "comparison_result", "source_asset",
                "source_location", "created_at", "created_by", "reviewed_by", "reliability", "notes",
            ):
                value = evidence.get(key)
                if value not in (None, "", [], {}):
                    graph.add((evi_uri, FAIRAC[_term(key)], Literal(str(value))))


def _add_completeness_assessment(graph: Graph, package_uri: URIRef, package: FairAcousticPackage) -> None:
    assessment = package.metadata_completeness_assessment or {}
    node = URIRef(f"{package_uri}#metadata-completeness-assessment")
    graph.add((node, RDF.type, FAIRAC.MetadataCompletenessAssessment))
    graph.add((package_uri, FAIRAC.hasMetadataCompletenessAssessment, node))
    graph.add((node, FAIRAC.assessmentStatus, Literal(package.metadata_completeness_status)))
    if assessment.get("assessment_id"):
        graph.add((node, DCTERMS.identifier, Literal(str(assessment["assessment_id"]))))
    if assessment.get("profile_id"):
        graph.add((node, DCTERMS.conformsTo, URIRef(str(assessment["profile_id"]))))
    summary = assessment.get("summary") or {}
    _add_context(graph, node, summary)
    for index, item in enumerate(assessment.get("fields", []) or [], start=1):
        field_node = URIRef(f"{node}/field/{index}")
        graph.add((field_node, RDF.type, FAIRAC.MetadataFieldAssessment))
        graph.add((node, FAIRAC.hasFieldAssessment, field_node))
        for key in ("field_name", "label", "category", "requirement_level", "status", "source", "recommendation", "note"):
            value = item.get(key)
            if value not in (None, "", [], {}):
                graph.add((field_node, FAIRAC[_term(key)], Literal(str(value))))


def build_metadata_graph(package: FairAcousticPackage) -> Graph:
    graph = Graph()
    graph.bind("fairac", FAIRAC)
    graph.bind("dct", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("dcat", DCAT)
    graph.bind("schema", SCHEMA)
    graph.bind("sh", SH)

    package_uri = _uri(package.identifier, f"urn:fair-acoustic:package:{package.package_id}")
    geometry_uri = URIRef(f"{package_uri}#geometry-file")
    component_uri = URIRef(f"{package_uri}#ifc-component-{_term(package.ifc_global_id or 'unresolved')}")
    measurement_uri = _uri(package.dataset_uri, f"{package_uri}#measurement")
    metadata_uri = URIRef(f"{package_uri}#metadata")
    research_uri = URIRef(f"{package_uri}#research-study")
    simulation_uri = URIRef(f"{package_uri}#simulation-generation-context")

    graph.add((package_uri, RDF.type, FAIRAC.AcousticComponentResearchObject))
    graph.add((package_uri, RDF.type, DCAT.Dataset))
    graph.add((package_uri, DCTERMS.identifier, Literal(package.identifier or package.package_id)))
    graph.add((package_uri, DCTERMS.title, Literal(package.title)))
    graph.add((package_uri, DCTERMS.hasVersion, Literal(package.version)))
    graph.add((package_uri, DCTERMS.created, Literal(package.created, datatype=XSD.dateTime)))
    graph.add((package_uri, DCTERMS.conformsTo, URIRef(package.research_object_profile)))
    graph.add((package_uri, DCTERMS.conformsTo, URIRef(package.metadata_profile)))
    graph.add((package_uri, FAIRAC.metadataProfileVersion, Literal(package.metadata_profile_version)))
    graph.add((package_uri, FAIRAC.hasGeometry, geometry_uri))
    graph.add((package_uri, FAIRAC.hasIfcComponent, component_uri))
    graph.add((package_uri, FAIRAC.hasMeasurement, measurement_uri))
    graph.add((package_uri, FAIRAC.hasMetadata, metadata_uri))
    graph.add((package_uri, FAIRAC.metadataCompletenessStatus, Literal(package.metadata_completeness_status)))
    graph.add((package_uri, FAIRAC.fairSupportStatus, Literal(package.fair_support_status)))
    graph.add((package_uri, FAIRAC.lifecycleStatus, Literal(package.lifecycle_status)))
    graph.add((package_uri, FAIRAC.scientificSuitabilityStatus, Literal(package.scientific_suitability_status)))

    # Legacy FAIR booleans remain compatibility evidence only.
    graph.add((package_uri, FAIRAC.legacyFairStatus, Literal(package.fair_status.value)))
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
        graph.add((package_uri, DCTERMS.license, URIRef(package.license) if str(package.license).startswith(("http://", "https://", "urn:")) else Literal(package.license)))
    _add_context(graph, package_uri, package.access_context)

    graph.add((geometry_uri, RDF.type, FAIRAC.IfcModel))
    graph.add((geometry_uri, DCTERMS.format, Literal("IFC")))
    graph.add((geometry_uri, DCTERMS.identifier, Literal(package.geometry_reference)))
    graph.add((component_uri, RDF.type, FAIRAC.IfcComponent))
    graph.add((component_uri, FAIRAC.sourceAsset, geometry_uri))
    if package.ifc_global_id:
        graph.add((component_uri, FAIRAC.ifcGlobalId, Literal(package.ifc_global_id)))
    for key in (
        "geometry_ifc_schema", "geometry_ifc_class", "geometry_name", "geometry_description", "geometry_component_type",
        "geometry_construction_family", "geometry_total_thickness_m", "geometry_semantic_classification", "model_version",
        "source_ifc_sha256", "geometry_type_assignment",
    ):
        value = package.metadata.get(key)
        if value not in (None, "", [], {}):
            graph.add((component_uri, FAIRAC[_term(key)], Literal(str(value))))
    for material in package.metadata.get("geometry_materials", []) or []:
        graph.add((component_uri, FAIRAC.material, Literal(str(material))))
    _add_context(graph, component_uri, package.metadata.get("geometry_spatial_context") or {})

    graph.add((measurement_uri, RDF.type, FAIRAC.AcousticDataset))
    graph.add((measurement_uri, RDF.type, DCAT.Dataset))
    graph.add((measurement_uri, DCTERMS.identifier, Literal(package.metadata.get("measurement_identifier") or package.measurement_reference)))
    graph.add((measurement_uri, DCTERMS.format, Literal(package.metadata.get("measurement_media_type", "application/octet-stream"))))
    origin = package.measurement_context.get("origin_classification") or (package.metadata.get("measurement_inspection") or {}).get("origin_classification")
    if origin:
        graph.add((measurement_uri, FAIRAC.originClassification, Literal(str(origin))))
    if package.dataset_uri:
        graph.add((measurement_uri, DCAT.accessURL, URIRef(package.dataset_uri)))
    inspection = package.metadata.get("measurement_inspection") or {}
    if inspection:
        graph.add((measurement_uri, FAIRAC.inspectionValid, Literal(bool(inspection.get("valid", True)), datatype=XSD.boolean)))
        graph.add((measurement_uri, FAIRAC.inspectedFormat, Literal(str(inspection.get("format", "")))))
        for signal in inspection.get("semantic_signals", []) or []:
            graph.add((measurement_uri, FAIRAC.detectedSignal, Literal(str(signal))))
    _add_context(graph, measurement_uri, package.measurement_context)
    _add_context(graph, measurement_uri, package.quality_information)

    if package.research_context:
        graph.add((package_uri, FAIRAC.hasResearchStudy, research_uri))
        graph.add((research_uri, RDF.type, FAIRAC.AcousticResearchStudy))
        graph.add((research_uri, PROV.used, component_uri))
        graph.add((research_uri, PROV.used, measurement_uri))
        _add_context(graph, research_uri, package.research_context)
    if package.simulation_context:
        # This node only describes provenance of supplied simulation/prediction results;
        # the application itself does not run acoustic simulation.
        graph.add((package_uri, FAIRAC.hasGenerationContext, simulation_uri))
        graph.add((simulation_uri, RDF.type, PROV.Activity))
        graph.add((simulation_uri, PROV.used, geometry_uri))
        _add_context(graph, simulation_uri, package.simulation_context)

    _add_supplementary_resources(graph, package_uri, simulation_uri, package.metadata.get("simulation_resources"), "simulation")
    _add_supplementary_resources(graph, package_uri, research_uri, package.metadata.get("research_resources"), "research")
    _add_relationships(graph, package_uri, component_uri, measurement_uri, package)
    _add_completeness_assessment(graph, package_uri, package)

    fair_assessment_uri = URIRef(f"{package_uri}#fair-support-assessment")
    graph.add((fair_assessment_uri, RDF.type, FAIRAC.FairSupportAssessment))
    graph.add((package_uri, FAIRAC.hasFairSupportAssessment, fair_assessment_uri))
    _add_context(graph, fair_assessment_uri, {key: package.fair_support_assessment.get(key) for key in ("assessment_id", "assessment_profile", "profile_version", "assessment_date", "overall")})

    lifecycle_uri = URIRef(f"{package_uri}#lifecycle-assessment")
    graph.add((lifecycle_uri, RDF.type, FAIRAC.RelationshipLifecycleAssessment))
    graph.add((package_uri, FAIRAC.hasLifecycleAssessment, lifecycle_uri))
    graph.add((lifecycle_uri, FAIRAC.lifecycleStatus, Literal(package.lifecycle_status)))
    if package.mapping_series_uri:
        graph.add((package_uri, FAIRAC.stewardedBy, URIRef(package.mapping_series_uri)))
    if package.latest_mapping_assertion_uri:
        graph.add((package_uri, FAIRAC.latestStewardshipAssertion, URIRef(package.latest_mapping_assertion_uri)))

    graph.add((metadata_uri, RDF.type, FAIRAC.MetadataRecord))
    graph.add((metadata_uri, DCTERMS.format, Literal("text/turtle")))
    graph.add((metadata_uri, DCTERMS.identifier, Literal(package.metadata_reference)))
    graph.add((metadata_uri, DCTERMS.conformsTo, URIRef(package.metadata_profile)))

    agent_name = package.provenance.get("institution") or package.provenance.get("responsible_agent") or package.provenance.get("creator") or package.creator
    if agent_name:
        agent_uri = URIRef(f"{package_uri}#agent")
        graph.add((agent_uri, RDF.type, PROV.Agent))
        graph.add((agent_uri, DCTERMS.title, Literal(str(agent_name))))
        graph.add((package_uri, PROV.wasAttributedTo, agent_uri))
        graph.add((measurement_uri, PROV.wasAttributedTo, agent_uri))

    generating_activity = package.provenance.get("generating_activity")
    if generating_activity:
        activity_uri = URIRef(f"{package_uri}#generation-activity")
        graph.add((activity_uri, RDF.type, PROV.Activity))
        graph.add((activity_uri, DCTERMS.description, Literal(str(generating_activity))))
        graph.add((measurement_uri, PROV.wasGeneratedBy, activity_uri))
        if package.provenance.get("original_source"):
            graph.add((activity_uri, PROV.used, Literal(str(package.provenance["original_source"]))))

    for path, checksum in package.checksums.items():
        checksum_node = URIRef(f"{package_uri}#checksum-{_term(path)}")
        graph.add((checksum_node, RDF.type, FAIRAC.Checksum))
        graph.add((checksum_node, FAIRAC.filePath, Literal(path)))
        graph.add((checksum_node, FAIRAC.sha256, Literal(checksum.replace("sha256:", ""))))
        graph.add((package_uri, FAIRAC.hasChecksum, checksum_node))

    shacl = package.metadata.get("shacl_validation") or {}
    if shacl:
        graph.add((package_uri, FAIRAC.shaclValidationAvailable, Literal(bool(shacl.get("available")), datatype=XSD.boolean)))
        graph.add((package_uri, FAIRAC.shaclConforms, Literal(bool(shacl.get("conforms")), datatype=XSD.boolean)))

    stewardship_ttl = package.metadata.get("stewardship_rdf_turtle")
    if stewardship_ttl:
        try:
            graph += Graph().parse(data=stewardship_ttl, format="turtle")
        except Exception:
            pass
    return graph


def metadata_turtle(package: FairAcousticPackage) -> str:
    return build_metadata_graph(package).serialize(format="turtle")
