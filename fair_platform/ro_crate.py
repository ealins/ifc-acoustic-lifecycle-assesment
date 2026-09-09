from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metadata_profile import PROFILE_ID as METADATA_PROFILE_ID, PROFILE_LABEL as METADATA_PROFILE_LABEL
from .models import FairAcousticPackage
from .research_object import PROFILE_ID, PROFILE_LABEL


RO_CRATE_METADATA = "ro-crate-metadata.json"

# Self-contained context avoids network resolution during validation while following
# RO-Crate's JSON-LD entity graph pattern. This remains a prototype profile, not an
# approved RO-Crate community profile.
RO_CONTEXT: dict[str, Any] = {
    "@vocab": "https://schema.org/",
    "schema": "https://schema.org/",
    "dct": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "prov": "http://www.w3.org/ns/prov#",
    "fairac": "https://example.org/fair-acoustic/vocab/",
    "conformsTo": {"@id": "dct:conformsTo", "@type": "@id"},
    "hasPart": {"@id": "schema:hasPart", "@type": "@id"},
    "about": {"@id": "schema:about", "@type": "@id"},
    "license": {"@id": "schema:license", "@type": "@id"},
    "contentUrl": {"@id": "schema:contentUrl", "@type": "@id"},
    "subjectComponent": {"@id": "fairac:subjectComponent", "@type": "@id"},
    "objectMeasurement": {"@id": "fairac:objectMeasurement", "@type": "@id"},
    "hasEvidence": {"@id": "fairac:hasEvidence", "@type": "@id"},
    "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
    "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
}


def _ref(identifier: str) -> dict[str, str]:
    return {"@id": identifier}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean(val) for key, val in value.items() if val not in (None, "", [], {})}
    if isinstance(value, list):
        return [_clean(item) for item in value if item not in (None, "", [], {})]
    return value


def _asset_entities(package: FairAcousticPackage) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in package.asset_records:
        path = str(record.get("path") or "")
        packaged = bool(record.get("packaged", path in package.assets))
        entity_id = path if packaged else str(record.get("source_uri") or path)
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        payload = package.assets.get(path)
        entities.append(_clean({
            "@id": entity_id,
            "@type": "File",
            "name": record.get("original_filename") or record.get("source_filename") or Path(path).name,
            "encodingFormat": record.get("media_type"),
            "contentSize": len(payload) if payload is not None else None,
            "contentUrl": _ref(str(record.get("source_uri"))) if record.get("source_uri") else None,
            "fairac:assetId": record.get("asset_id"),
            "fairac:assetRole": record.get("role"),
            "fairac:packaged": packaged,
            "fairac:sha256": package.checksums.get(path, "").replace("sha256:", "") or None if packaged else None,
            "fairac:version": record.get("version"),
            "fairac:accessRights": record.get("access_rights"),
            "fairac:reachabilityStatus": record.get("reachability_status"),
            "fairac:lastAccessCheck": record.get("last_check_time"),
        }))
    return entities


def _source_asset_ref(package: FairAcousticPackage, path: str) -> dict[str, str]:
    record = next((item for item in package.asset_records if item.get("path") == path), {})
    if record.get("packaged", path in package.assets):
        return _ref(path)
    return _ref(str(record.get("source_uri") or path))


def build_ro_crate(package: FairAcousticPackage) -> dict[str, Any]:
    component_id = f"#ifc-component-{package.ifc_global_id or 'unresolved'}"
    dataset_identifier = package.metadata.get("measurement_identifier") or package.package_id
    measurement_id = f"#acoustic-dataset-{dataset_identifier}"

    package_parts = [
        _source_asset_ref(package, package.geometry_reference),
        _source_asset_ref(package, package.measurement_reference),
        _ref(package.metadata_reference),
        _ref("profiles/acoustic-metadata-profile.json"),
        _ref("reports/metadata-completeness-assessment.json"),
        _ref("reports/fair-support-assessment.json"),
        _ref("reports/relationship-lifecycle-assessment.json"),
        _ref("evidence/relationship-evidence.json"),
    ]
    for record in package.asset_records:
        if record.get("path") in {package.geometry_reference, package.measurement_reference}:
            continue
        package_parts.append(_source_asset_ref(package, str(record.get("path") or "")))

    graph: list[dict[str, Any]] = [
        {
            "@id": RO_CRATE_METADATA,
            "@type": "CreativeWork",
            "about": _ref("./"),
            "conformsTo": _ref(PROFILE_ID),
        },
        _clean({
            "@id": "./",
            "@type": ["Dataset", "fairac:AcousticComponentResearchObject"],
            "identifier": package.identifier or None,
            "fairac:localPackageId": package.package_id,
            "name": package.metadata.get("title") or None,
            "description": package.metadata.get("description"),
            "version": package.version,
            "dateCreated": package.created,
            "dateModified": package.modified,
            "creator": package.creator,
            "license": _ref(package.license) if package.license and str(package.license).startswith(("http://", "https://", "urn:")) else package.license,
            "keywords": package.metadata.get("keywords"),
            "inLanguage": package.metadata.get("metadata_language") or package.metadata.get("language"),
            "conformsTo": [_ref(PROFILE_ID), _ref(METADATA_PROFILE_ID)],
            "hasPart": package_parts,
            "fairac:metadataCompletenessStatus": package.metadata_completeness_status,
            "fairac:fairSupportStatus": package.fair_support_status,
            "fairac:lifecycleStatus": package.lifecycle_status,
            "fairac:scientificSuitabilityStatus": package.scientific_suitability_status,
        }),
        {
            "@id": PROFILE_ID,
            "@type": "CreativeWork",
            "name": PROFILE_LABEL,
            "description": "Prototype research-object/package profile for IFC-linked acoustic component data; not an approved community standard.",
        },
        {
            "@id": METADATA_PROFILE_ID,
            "@type": "CreativeWork",
            "name": METADATA_PROFILE_LABEL,
            "version": package.metadata_profile_version,
            "description": "Prototype FAIR-oriented acoustic component metadata profile for the selected IFC/VaBDat use case; not a universal acoustic metadata standard.",
        },
        {
            "@id": "profiles/acoustic-metadata-profile.json",
            "@type": "File",
            "name": "Machine-readable acoustic metadata profile snapshot",
            "encodingFormat": "application/json",
            "about": _ref(METADATA_PROFILE_ID),
        },
        _clean({
            "@id": component_id,
            "@type": ["fairac:IfcComponent", "Thing"],
            "identifier": package.ifc_global_id,
            "name": package.metadata.get("geometry_name"),
            "description": package.metadata.get("geometry_description"),
            "fairac:ifcEntityType": package.metadata.get("geometry_ifc_class"),
            "fairac:ifcSchema": package.metadata.get("geometry_ifc_schema"),
            "fairac:typeAssignment": package.metadata.get("geometry_type_assignment"),
            "fairac:componentClassification": package.metadata.get("geometry_semantic_classification"),
            "fairac:materialSummary": package.metadata.get("geometry_materials"),
            "fairac:layerSummary": package.metadata.get("geometry_material_layers"),
            "fairac:totalThicknessM": package.metadata.get("geometry_total_thickness_m"),
            "fairac:spatialContext": package.metadata.get("geometry_spatial_context"),
            "fairac:sourceAsset": _source_asset_ref(package, package.geometry_reference),
            "fairac:sourceVersion": package.metadata.get("model_version"),
            "fairac:sourceChecksum": package.checksums.get(package.geometry_reference),
        }),
        _clean({
            "@id": measurement_id,
            "@type": ["Dataset", "fairac:AcousticDataset"],
            "identifier": package.metadata.get("measurement_identifier"),
            "name": package.metadata.get("source_measurement_filename") or Path(package.measurement_reference).name,
            "encodingFormat": package.metadata.get("measurement_media_type"),
            "url": package.dataset_uri,
            "fairac:originClassification": package.measurement_context.get("origin_classification") or (package.metadata.get("measurement_inspection") or {}).get("origin_classification"),
            "fairac:recordType": package.measurement_context.get("measurement_type"),
            "fairac:measuredQuantity": package.measurement_context.get("measured_quantity"),
            "fairac:measurementMethod": package.measurement_context.get("measurement_method"),
            "fairac:unit": package.measurement_context.get("unit") or package.measurement_context.get("units"),
            "fairac:sourceAsset": _source_asset_ref(package, package.measurement_reference),
            "fairac:sourceVersion": package.measurement_context.get("measurement_version"),
            "fairac:sourceChecksum": package.checksums.get(package.measurement_reference),
        }),
        {
            "@id": package.metadata_reference,
            "@type": "File",
            "name": "Domain RDF, provenance, qualified relationships, and assessment metadata",
            "encodingFormat": "text/turtle",
            "about": _ref("./"),
        },
        {
            "@id": "reports/metadata-completeness-assessment.json",
            "@type": "File",
            "name": "Metadata completeness assessment report",
            "encodingFormat": "application/json",
            "about": _ref("#metadata-completeness-assessment"),
        },
        {
            "@id": "reports/fair-support-assessment.json",
            "@type": "File",
            "name": "Selected FAIR-support assessment report",
            "encodingFormat": "application/json",
            "about": _ref("#fair-support-assessment"),
        },
        {
            "@id": "reports/relationship-lifecycle-assessment.json",
            "@type": "File",
            "name": "Component-dataset relationship lifecycle assessment report",
            "encodingFormat": "application/json",
            "about": _ref("#lifecycle-assessment"),
        },
        {
            "@id": "evidence/relationship-evidence.json",
            "@type": "File",
            "name": "Qualified component-dataset relationship evidence",
            "encodingFormat": "application/json",
        },
        _clean({
            "@id": "#metadata-completeness-assessment",
            "@type": "fairac:MetadataCompletenessAssessment",
            "identifier": package.metadata_completeness_assessment.get("assessment_id"),
            "conformsTo": _ref(METADATA_PROFILE_ID),
            "fairac:assessmentStatus": package.metadata_completeness_status,
            "fairac:requiredFieldsSatisfied": (package.metadata_completeness_assessment.get("summary") or {}).get("required_fields_satisfied"),
            "fairac:requiredFieldsTotal": (package.metadata_completeness_assessment.get("summary") or {}).get("required_fields_total"),
        }),
        _clean({
            "@id": "#fair-support-assessment",
            "@type": "fairac:FairSupportAssessment",
            "identifier": package.fair_support_assessment.get("assessment_id"),
            "fairac:assessmentProfile": package.fair_support_assessment.get("assessment_profile"),
            "fairac:assessmentProfileVersion": package.fair_support_assessment.get("profile_version"),
            "fairac:assessmentStatus": package.fair_support_status,
        }),
        _clean({
            "@id": "#lifecycle-assessment",
            "@type": "fairac:RelationshipLifecycleAssessment",
            "fairac:lifecycleStatus": package.lifecycle_status,
            "fairac:mappingSeries": package.mapping_series_uri,
            "fairac:latestMappingAssertion": package.latest_mapping_assertion_uri,
        }),
    ]

    graph.extend(_asset_entities(package))

    # Provenance/activity entities are only emitted when supplied by source/user data.
    if package.provenance.get("generating_activity"):
        graph.append(_clean({
            "@id": "#generation-activity",
            "@type": "prov:Activity",
            "name": package.provenance.get("generating_activity"),
            "wasDerivedFrom": _ref(str(package.provenance.get("original_source"))) if package.provenance.get("original_source") and str(package.provenance.get("original_source")).startswith(("http://", "https://", "urn:")) else None,
        }))
    if package.measurement_context.get("instrument"):
        graph.append(_clean({
            "@id": "#instrument",
            "@type": "Thing",
            "name": package.measurement_context.get("instrument"),
            "manufacturer": package.measurement_context.get("instrument_manufacturer"),
            "model": package.measurement_context.get("instrument_model"),
        }))
    processing_software = package.measurement_context.get("processing_software")
    if processing_software:
        graph.append(_clean({"@id": "#processing-software", "@type": "SoftwareApplication", "name": processing_software}))
    simulation_software = package.simulation_context.get("software")
    if simulation_software:
        graph.append(_clean({
            "@id": "#generation-software",
            "@type": "SoftwareApplication",
            "name": simulation_software,
            "softwareVersion": package.simulation_context.get("software_version"),
            "description": "Software provenance for a supplied simulation/prediction result; this application does not run the simulation.",
        }))

    for relationship in package.relationships:
        relationship_id = f"#relationship-{relationship.get('relationship_id')}"
        evidence_refs = [_ref(f"#evidence-{item.get('evidence_id')}") for item in relationship.get("evidence", [])]
        graph.append(_clean({
            "@id": relationship_id,
            "@type": "fairac:GeometryMeasurementRelationship",
            "identifier": relationship.get("relationship_id"),
            "subjectComponent": _ref(component_id),
            "objectMeasurement": _ref(measurement_id),
            "fairac:relationshipType": relationship.get("relationship_type"),
            "fairac:scope": relationship.get("scope"),
            "fairac:rationale": relationship.get("rationale"),
            "hasEvidence": evidence_refs,
            "creator": relationship.get("created_by"),
            "fairac:reviewedBy": relationship.get("last_reviewed_by"),
            "fairac:reviewedAt": relationship.get("last_reviewed_at"),
            "fairac:approvalStatus": relationship.get("approval_status"),
            "fairac:relationshipVersion": relationship.get("relationship_version"),
            "fairac:sourceComponentVersion": relationship.get("source_component_version"),
            "fairac:sourceMeasurementVersion": relationship.get("source_measurement_version"),
            "fairac:sourceIfcChecksum": relationship.get("source_ifc_checksum"),
            "fairac:sourceDatasetChecksum": relationship.get("source_dataset_checksum"),
            "fairac:reviewStatus": relationship.get("status"),
            "fairac:recommendedAction": relationship.get("recommended_action"),
        }))
        for evidence in relationship.get("evidence", []):
            source_asset = evidence.get("source_asset")
            graph.append(_clean({
                "@id": f"#evidence-{evidence.get('evidence_id')}",
                "@type": "fairac:EvidenceItem",
                "identifier": evidence.get("evidence_id"),
                "fairac:evidenceType": evidence.get("evidence_type"),
                "fairac:observedValue": evidence.get("observed_value"),
                "fairac:expectedValue": evidence.get("expected_value"),
                "fairac:comparisonResult": evidence.get("comparison_result"),
                "fairac:sourceAsset": _ref(str(source_asset)) if source_asset else None,
                "fairac:sourceLocation": evidence.get("source_location"),
                "creator": evidence.get("created_by"),
                "fairac:reviewedBy": evidence.get("reviewed_by"),
                "fairac:reliability": evidence.get("reliability"),
                "description": evidence.get("notes"),
            }))

    return {"@context": RO_CONTEXT, "@graph": graph}


def ro_crate_json(package: FairAcousticPackage) -> str:
    return json.dumps(build_ro_crate(package), indent=2, ensure_ascii=False)
