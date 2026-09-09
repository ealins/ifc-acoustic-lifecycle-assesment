from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import FairAcousticPackage
from .research_object import PROFILE_ID, PROFILE_LABEL


RO_CRATE_METADATA = "ro-crate-metadata.json"

# Self-contained context avoids network resolution during validation while following
# RO-Crate's JSON-LD entity graph pattern. The profile documentation explains that
# this is a prototype profile, not an approved community RO-Crate profile.
RO_CONTEXT: dict[str, Any] = {
    "@vocab": "https://schema.org/",
    "schema": "https://schema.org/",
    "dct": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "fairac": "https://example.org/fair-acoustic/vocab/",
    "conformsTo": {"@id": "dct:conformsTo", "@type": "@id"},
    "hasPart": {"@id": "schema:hasPart", "@type": "@id"},
    "about": {"@id": "schema:about", "@type": "@id"},
    "license": {"@id": "schema:license", "@type": "@id"},
    "subjectComponent": {"@id": "fairac:subjectComponent", "@type": "@id"},
    "objectMeasurement": {"@id": "fairac:objectMeasurement", "@type": "@id"},
    "hasEvidence": {"@id": "fairac:hasEvidence", "@type": "@id"},
    "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
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
    records_by_path = {record.get("path"): record for record in package.asset_records if record.get("path")}
    entities: list[dict[str, Any]] = []
    derived = {
        RO_CRATE_METADATA,
        package.metadata_reference,
        "manifest.json",
        "checksums/sha256sums.txt",
        "README.txt",
    }
    for path, payload in sorted(package.assets.items()):
        if path in derived or path.startswith("reports/"):
            continue
        record = records_by_path.get(path, {})
        entity = {
            "@id": path,
            "@type": "File",
            "name": record.get("original_filename") or record.get("source_filename") or Path(path).name,
            "encodingFormat": record.get("media_type") or package.metadata.get("measurement_media_type") if path == package.measurement_reference else record.get("media_type"),
            "contentSize": len(payload),
            "fairac:assetRole": record.get("role") or ("ifc-model" if path == package.geometry_reference else "measurement-dataset" if path == package.measurement_reference else "research-asset"),
            "fairac:sha256": package.checksums.get(path, "").replace("sha256:", "") or None,
            "fairac:version": record.get("version"),
        }
        entities.append(_clean(entity))
    return entities


def build_ro_crate(package: FairAcousticPackage) -> dict[str, Any]:
    component_id = f"#ifc-component-{package.ifc_global_id or 'unresolved'}"
    measurement_id = f"#measurement-{package.metadata.get('measurement_identifier') or package.package_id}"
    package_parts = [_ref(package.geometry_reference), _ref(package.measurement_reference), _ref(package.metadata_reference)]
    package_parts.extend(_ref(record["path"]) for record in package.asset_records if record.get("path") not in {package.geometry_reference, package.measurement_reference})
    package_parts.extend([_ref("reports/fair-assessment.json"), _ref("reports/lifecycle-assessment.json"), _ref("reports/relationship-evidence.json")])

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
            "identifier": package.identifier,
            "name": package.title,
            "description": package.metadata.get("description"),
            "version": package.version,
            "dateCreated": package.created,
            "dateModified": package.modified,
            "creator": package.creator,
            "license": _ref(package.license) if package.license and str(package.license).startswith(("http://", "https://", "urn:")) else package.license,
            "keywords": package.metadata.get("keywords"),
            "conformsTo": _ref(PROFILE_ID),
            "hasPart": package_parts,
            "fairac:fairSupportStatus": package.fair_support_status,
            "fairac:lifecycleStatus": package.lifecycle_status,
            "fairac:scientificSuitabilityStatus": package.scientific_suitability_status,
        }),
        {
            "@id": PROFILE_ID,
            "@type": "CreativeWork",
            "name": PROFILE_LABEL,
            "description": "Prototype profile for IFC-linked acoustic component research objects; not an approved community standard.",
        },
        _clean({
            "@id": component_id,
            "@type": ["fairac:IfcComponent", "Thing"],
            "identifier": package.ifc_global_id,
            "name": package.metadata.get("geometry_name"),
            "fairac:ifcEntityType": package.metadata.get("geometry_ifc_class"),
            "fairac:ifcSchema": package.metadata.get("geometry_ifc_schema"),
            "fairac:componentType": package.metadata.get("geometry_component_type") or package.metadata.get("geometry_semantic_classification"),
            "fairac:materialSummary": package.metadata.get("geometry_materials"),
            "fairac:totalThicknessM": package.metadata.get("geometry_total_thickness_m"),
            "fairac:sourceAsset": _ref(package.geometry_reference),
            "fairac:sourceVersion": package.metadata.get("model_version"),
        }),
        _clean({
            "@id": measurement_id,
            "@type": ["Dataset", "fairac:MeasurementDataset"],
            "identifier": package.metadata.get("measurement_identifier"),
            "name": package.metadata.get("source_measurement_filename") or Path(package.measurement_reference).name,
            "encodingFormat": package.metadata.get("measurement_media_type"),
            "url": package.dataset_uri,
            "fairac:originClassification": (package.metadata.get("measurement_inspection") or {}).get("origin_classification") or package.measurement_context.get("origin_classification"),
            "fairac:measurementType": package.measurement_context.get("measurement_type"),
            "fairac:measurementMethod": package.measurement_context.get("measurement_method"),
            "fairac:unit": package.measurement_context.get("unit") or package.measurement_context.get("units"),
            "fairac:sourceAsset": _ref(package.measurement_reference),
            "fairac:sourceVersion": package.measurement_context.get("measurement_version"),
        }),
        {
            "@id": package.metadata_reference,
            "@type": "File",
            "name": "Domain RDF and provenance metadata",
            "encodingFormat": "text/turtle",
            "about": _ref("./"),
        },
        {
            "@id": "reports/fair-assessment.json",
            "@type": "File",
            "name": "FAIR-support assessment report",
            "encodingFormat": "application/json",
            "about": _ref("#fair-support-assessment"),
        },
        {
            "@id": "reports/lifecycle-assessment.json",
            "@type": "File",
            "name": "Lifecycle stewardship assessment report",
            "encodingFormat": "application/json",
            "about": _ref("#lifecycle-assessment"),
        },
        {
            "@id": "reports/relationship-evidence.json",
            "@type": "File",
            "name": "Qualified geometry-measurement relationship evidence",
            "encodingFormat": "application/json",
        },
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
            "@type": "fairac:LifecycleAssessment",
            "fairac:lifecycleStatus": package.lifecycle_status,
            "fairac:mappingSeries": package.mapping_series_uri,
            "fairac:latestMappingAssertion": package.latest_mapping_assertion_uri,
        }),
    ]

    graph.extend(_asset_entities(package))

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
            "fairac:relationshipVersion": relationship.get("relationship_version"),
            "fairac:sourceComponentVersion": relationship.get("source_component_version"),
            "fairac:sourceMeasurementVersion": relationship.get("source_measurement_version"),
            "fairac:reviewStatus": relationship.get("status"),
        }))
        for evidence in relationship.get("evidence", []):
            graph.append(_clean({
                "@id": f"#evidence-{evidence.get('evidence_id')}",
                "@type": "fairac:EvidenceItem",
                "identifier": evidence.get("evidence_id"),
                "fairac:evidenceType": evidence.get("evidence_type"),
                "fairac:observedValue": evidence.get("observed_value"),
                "fairac:expectedValue": evidence.get("expected_value"),
                "fairac:comparisonResult": evidence.get("comparison_result"),
                "fairac:sourceAsset": _ref(evidence["source_asset"]) if evidence.get("source_asset") else None,
                "fairac:sourceLocation": evidence.get("source_location"),
                "creator": evidence.get("created_by"),
                "fairac:reliability": evidence.get("reliability"),
                "description": evidence.get("notes"),
            }))

    return {"@context": RO_CONTEXT, "@graph": graph}


def ro_crate_json(package: FairAcousticPackage) -> str:
    return json.dumps(build_ro_crate(package), indent=2, ensure_ascii=False)
