from __future__ import annotations

from typing import Any

from .models import FairAcousticPackage
from .research_object import (
    LifecycleStewardshipState,
    ReassessmentTrigger,
    TriggerCategory,
    TriggerSeverity,
)


_TRIGGER_RULES: dict[str, tuple[str, TriggerCategory, TriggerSeverity, LifecycleStewardshipState, str, str]] = {
    "ifc_checksum": (
        "IFC source checksum changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Re-resolve the selected IFC component and review relationship evidence affected by the model change.",
        "Source content changed; component identity/semantic evidence may no longer represent the originally assessed state.",
    ),
    "ifc_schema": (
        "IFC schema changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Confirm that component identity and extracted properties remain comparable under the new IFC schema.",
        "IFC-side interpretation requirements may have changed.",
    ),
    "ifc_global_id": (
        "Selected IFC GlobalId changed/disappeared", TriggerCategory.RELATIONSHIP_TARGET, TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.INVALID,
        "Treat this as a relationship retargeting event and create/review a new relationship version.",
        "The relationship subject changed or can no longer be resolved.",
    ),
    "ifc_entity_type": (
        "IFC entity type changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Review whether the declared component-dataset relationship remains semantically defensible.",
        "Component semantics changed even if the source file remains accessible.",
    ),
    "material_summary": (
        "Material/layer summary changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Reassess material/layer relationship evidence and equivalence claims.",
        "Material correspondence is part of the original relationship rationale/evidence.",
    ),
    "thickness_m": (
        "Relevant component dimension changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Re-evaluate dimension/thickness evidence using the documented tolerance and rationale.",
        "A relevant physical dimension differs from the assessed source state.",
    ),
    "component_type": (
        "Component type assignment changed", TriggerCategory.COMPONENT_SEMANTIC, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Review type/assembly evidence for the relationship.",
        "The semantic/type basis for the component-dataset claim changed.",
    ),
    "measurement_checksum": (
        "Measurement content checksum changed", TriggerCategory.MEASUREMENT_CONTENT, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Inspect the new acoustic data version and re-approve relationship evidence that depends on content.",
        "Acoustic source content changed from the version used by the relationship decision.",
    ),
    "measurement_version": (
        "Measurement version changed", TriggerCategory.MEASUREMENT_CONTENT, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review changes between dataset versions and record a stewardship decision.",
        "The dataset version baseline no longer matches the previous relationship review.",
    ),
    "measurement_uri": (
        "Measurement URI changed", TriggerCategory.RELATIONSHIP_TARGET, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Verify that the new URI identifies the intended dataset rather than a different relationship target.",
        "External relationship target/reference changed.",
    ),
    "resource_status": (
        "Required acoustic resource availability changed", TriggerCategory.ACCESS, TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.BROKEN,
        "Verify the resource location/access route or restore the missing/corrupt source. Keep metadata available for traceability.",
        "A required source became missing, corrupt, or explicitly unreachable.",
    ),
    "provenance": (
        "Provenance changed", TriggerCategory.PROVENANCE, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review whether the provenance change alters origin, derivation, or responsible-agent evidence.",
        "Interpretation/reuse provenance changed and may affect the evidential meaning of the relationship.",
    ),
    "license": (
        "Licence/reuse terms changed", TriggerCategory.ACCESS, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.ACCEPTABLE,
        "Refresh metadata completeness and FAIR-support assessment; relationship semantics are not automatically invalidated.",
        "This is primarily a reuse/access change, not automatically a component-dataset semantic change.",
    ),
    "access_rights": (
        "Access rights changed", TriggerCategory.ACCESS, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.ACCEPTABLE,
        "Refresh access and FAIR-support evidence; check for broken resources separately.",
        "Access conditions changed while the relationship claim may remain semantically acceptable.",
    ),
    "metadata_profile_version": (
        "Acoustic metadata-profile version changed", TriggerCategory.PROFILE, TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Revalidate metadata and relationship evidence against the revised profile requirements.",
        "The rules used to interpret/validate the research object changed.",
    ),
    "relationship_type": (
        "Relationship type changed", TriggerCategory.RELATIONSHIP_TARGET, TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review the evidential meaning of the new relationship type and approve a new relationship version.",
        "The semantics of the component-dataset claim changed.",
    ),
    "relationship_target": (
        "Relationship target changed", TriggerCategory.RELATIONSHIP_TARGET, TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.INVALID,
        "Create/review a new relationship version for the new target and preserve the prior assertion history.",
        "The dataset or component targeted by the claim changed.",
    ),
    "relationship_evidence": (
        "Relationship evidence changed", TriggerCategory.RELATIONSHIP_TARGET, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Re-run relationship review using the new evidence set.",
        "The recorded basis for accepting/rejecting the relationship changed.",
    ),
    "candidate_set": (
        "Competing candidate set changed", TriggerCategory.REVIEW, TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.MULTIPLE_CANDIDATES,
        "Present all minimum-condition candidates for review; do not silently select a replacement record.",
        "A new competing candidate prevents deterministic relationship selection without review.",
    ),
    "package_title": (
        "Package title changed", TriggerCategory.EDITORIAL, TriggerSeverity.INFO,
        LifecycleStewardshipState.ACCEPTABLE,
        "Refresh descriptive metadata; no relationship reassessment is required solely for this editorial change.",
        "Editorial descriptive change only; component-dataset semantics are unchanged.",
    ),
}


def relationship_source_snapshot(package: FairAcousticPackage) -> dict[str, Any]:
    relationship = package.relationships[0] if package.relationships else {}
    access_status = str(package.access_context.get("external_uri_status") or "NOT_TESTED").upper()
    packaged_measurement = package.measurement_reference in package.assets
    if packaged_measurement:
        resource_status = "PACKAGED"
    elif package.dataset_uri and access_status in {"UNREACHABLE", "BROKEN"}:
        resource_status = "UNREACHABLE"
    elif package.dataset_uri:
        resource_status = access_status
    else:
        resource_status = "MISSING"
    return {
        "ifc_checksum": package.checksums.get(package.geometry_reference) or package.metadata.get("source_ifc_sha256"),
        "ifc_schema": package.metadata.get("geometry_ifc_schema"),
        "ifc_global_id": package.ifc_global_id,
        "ifc_entity_type": package.metadata.get("geometry_ifc_class"),
        "material_summary": package.metadata.get("geometry_material_layers") or package.metadata.get("geometry_materials"),
        "thickness_m": package.metadata.get("geometry_total_thickness_m"),
        "component_type": package.metadata.get("geometry_type_assignment") or package.metadata.get("geometry_component_type") or package.metadata.get("geometry_semantic_classification"),
        "measurement_checksum": package.checksums.get(package.measurement_reference),
        "measurement_version": package.measurement_context.get("measurement_version") or package.metadata.get("measurement_version") or package.version,
        "measurement_uri": package.dataset_uri,
        "resource_status": resource_status,
        "provenance": package.provenance,
        "license": package.license,
        "access_rights": package.access_context.get("access_rights"),
        "metadata_profile_version": package.metadata_profile_version,
        "relationship_type": relationship.get("relationship_type"),
        "relationship_target": {
            "component": relationship.get("subject_ifc_global_id"),
            "dataset": relationship.get("object_measurement_id"),
        },
        "relationship_evidence": relationship.get("evidence", []),
        "candidate_set": package.metadata.get("relationship_candidate_ids") or [],
        "package_title": package.metadata.get("title"),
    }


def detect_reassessment_triggers(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[ReassessmentTrigger]:
    if not previous:
        return []
    triggers: list[ReassessmentTrigger] = []
    for key, current_value in current.items():
        old_value = previous.get(key)
        if old_value == current_value:
            continue
        rule = _TRIGGER_RULES.get(key)
        if not rule:
            continue
        trigger_type, category, severity, resulting_state, action, consequence = rule
        triggers.append(
            ReassessmentTrigger(
                trigger_type=trigger_type,
                category=category,
                old_value=old_value,
                new_value=current_value,
                affected_entity="component-dataset relationship",
                severity=severity,
                reassessment_required=severity != TriggerSeverity.INFO,
                resulting_state=resulting_state,
                recommended_action=action,
                assessment_consequence=consequence,
            )
        )
    return triggers


def capture_reassessment_triggers(package: FairAcousticPackage) -> list[ReassessmentTrigger]:
    current = relationship_source_snapshot(package)
    previous = package.metadata.get("last_relationship_snapshot")
    triggers = detect_reassessment_triggers(previous, current)
    if triggers:
        package.reassessment_triggers.extend(item.to_dict() for item in triggers)
    package.metadata["last_relationship_snapshot"] = current
    return triggers
