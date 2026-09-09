from __future__ import annotations

from typing import Any

from .models import FairAcousticPackage
from .research_object import (
    LifecycleStewardshipState,
    ReassessmentTrigger,
    TriggerCategory,
    TriggerSeverity,
)


_TRIGGER_RULES: dict[str, tuple[str, TriggerCategory, TriggerSeverity, LifecycleStewardshipState, str]] = {
    "ifc_checksum": (
        "IFC file checksum changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Re-resolve the selected IFC component and review relationship evidence affected by the model change.",
    ),
    "ifc_schema": (
        "IFC schema changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Confirm that component identity and extracted properties remain comparable under the new IFC schema.",
    ),
    "ifc_global_id": (
        "Selected IFC GlobalId changed",
        TriggerCategory.RELATIONSHIP_TARGET,
        TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.INVALID,
        "Treat this as a relationship retargeting event and create/review a new relationship version.",
    ),
    "ifc_entity_type": (
        "IFC entity type changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Review whether the declared measurement relationship remains semantically defensible.",
    ),
    "material_summary": (
        "Material/layer summary changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Reassess material-based relationship evidence and equivalence claims.",
    ),
    "thickness_m": (
        "Component thickness changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Re-evaluate thickness evidence using the documented tolerance and rationale.",
    ),
    "component_type": (
        "Component type assignment changed",
        TriggerCategory.COMPONENT_SEMANTIC,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Review type/assembly evidence for the relationship.",
    ),
    "measurement_checksum": (
        "Measurement content checksum changed",
        TriggerCategory.MEASUREMENT_CONTENT,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.SEMANTICALLY_STALE,
        "Inspect the new acoustic data version and re-approve relationship evidence that depends on content.",
    ),
    "measurement_version": (
        "Measurement version changed",
        TriggerCategory.MEASUREMENT_CONTENT,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review changes between measurement versions and record a stewardship decision.",
    ),
    "measurement_uri": (
        "Measurement URI changed",
        TriggerCategory.RELATIONSHIP_TARGET,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Verify that the new URI identifies the intended dataset rather than a different relationship target.",
    ),
    "provenance": (
        "Provenance changed",
        TriggerCategory.PROVENANCE,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review whether the provenance change alters origin, derivation, or responsible-agent evidence.",
    ),
    "license": (
        "Licence/reuse terms changed",
        TriggerCategory.ACCESS,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.ACCEPTABLE,
        "Refresh FAIR-support assessment; relationship semantics are not automatically invalidated.",
    ),
    "access_rights": (
        "Access rights changed",
        TriggerCategory.ACCESS,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.ACCEPTABLE,
        "Refresh access evidence and FAIR-support assessment; check for broken references separately.",
    ),
    "profile_version": (
        "Research-object profile version changed",
        TriggerCategory.PROFILE,
        TriggerSeverity.REVIEW,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Revalidate the package against the revised profile and review new relationship requirements.",
    ),
    "relationship_type": (
        "Relationship type changed",
        TriggerCategory.RELATIONSHIP_TARGET,
        TriggerSeverity.CRITICAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Review the evidential meaning of the new relationship type and approve a new relationship version.",
    ),
    "relationship_evidence": (
        "Relationship evidence changed",
        TriggerCategory.RELATIONSHIP_TARGET,
        TriggerSeverity.MATERIAL,
        LifecycleStewardshipState.MANUAL_REVIEW,
        "Re-run relationship review using the new evidence set.",
    ),
}


def relationship_source_snapshot(package: FairAcousticPackage) -> dict[str, Any]:
    relationship = package.relationships[0] if package.relationships else {}
    return {
        "ifc_checksum": package.checksums.get(package.geometry_reference) or package.metadata.get("source_ifc_sha256"),
        "ifc_schema": package.metadata.get("geometry_ifc_schema"),
        "ifc_global_id": package.ifc_global_id,
        "ifc_entity_type": package.metadata.get("geometry_ifc_class"),
        "material_summary": package.metadata.get("geometry_material_layers") or package.metadata.get("geometry_materials"),
        "thickness_m": package.metadata.get("geometry_total_thickness_m"),
        "component_type": package.metadata.get("geometry_component_type") or package.metadata.get("geometry_semantic_classification"),
        "measurement_checksum": package.checksums.get(package.measurement_reference),
        "measurement_version": package.measurement_context.get("measurement_version") or package.metadata.get("measurement_version") or package.version,
        "measurement_uri": package.dataset_uri,
        "provenance": package.provenance,
        "license": package.license,
        "access_rights": package.access_context.get("access_rights"),
        "profile_version": package.research_object_profile,
        "relationship_type": relationship.get("relationship_type"),
        "relationship_evidence": relationship.get("evidence", []),
    }


def detect_reassessment_triggers(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> list[ReassessmentTrigger]:
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
        trigger_type, category, severity, resulting_state, action = rule
        triggers.append(
            ReassessmentTrigger(
                trigger_type=trigger_type,
                category=category,
                old_value=old_value,
                new_value=current_value,
                affected_entity="geometry-measurement relationship",
                severity=severity,
                reassessment_required=severity != TriggerSeverity.INFO,
                resulting_state=resulting_state,
                recommended_action=action,
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
