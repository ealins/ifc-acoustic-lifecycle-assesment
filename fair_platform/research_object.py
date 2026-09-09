from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from .models import utc_now


PROFILE_ID = "https://example.org/fair-acoustic/profile/acoustic-component-ro/0.2"
PROFILE_LABEL = "Prototype Acoustic Component Research-Object Profile"


class MeasurementOrigin(str, Enum):
    RAW_MEASUREMENT = "raw_measurement"
    PROCESSED_MEASUREMENT = "processed_measurement"
    DERIVED_RESULT = "derived_result"
    SIMULATION_RESULT = "simulation_result"
    MANUFACTURER_VALUE = "manufacturer_value"
    REFERENCE_VALUE = "reference_value"
    CATALOG_RECORD = "catalog_record"
    PREDICTED_VALUE = "predicted_value"
    UNKNOWN_ORIGIN = "unknown_origin"
    # Backward-compatible alias; iteration exposes UNKNOWN_ORIGIN only.
    UNKNOWN = "unknown_origin"


class RelationshipType(str, Enum):
    MEASURED_ON = "measuredOn"
    CHARACTERIZES = "characterizes"
    DERIVED_FROM_MEASUREMENT_OF = "derivedFromMeasurementOf"
    PREDICTED_FOR = "predictedFor"
    APPLICABLE_TO_EQUIVALENT_ASSEMBLY = "applicableToEquivalentAssembly"
    REFERENCES = "references"
    UNKNOWN = "unknownRelationship"


class EvidenceStatus(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class TriggerCategory(str, Enum):
    EDITORIAL = "editorial_change"
    DESCRIPTIVE = "descriptive_change"
    ACCESS = "access_change"
    PROVENANCE = "provenance_change"
    COMPONENT_SEMANTIC = "component_semantic_change"
    MEASUREMENT_CONTENT = "measurement_content_change"
    RELATIONSHIP_TARGET = "relationship_target_change"
    PROFILE = "profile_change"
    REVIEW = "review_change"


class TriggerSeverity(str, Enum):
    INFO = "INFO"
    REVIEW = "REVIEW"
    MATERIAL = "MATERIAL"
    CRITICAL = "CRITICAL"


class LifecycleStewardshipState(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    SEMANTICALLY_STALE = "SEMANTICALLY_STALE"
    BROKEN = "BROKEN"
    AMBIGUOUS = "AMBIGUOUS"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    UNMATCHED = "UNMATCHED"
    INVALID = "INVALID"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    UNASSESSED = "UNASSESSED"


class ScientificSuitabilityState(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass
class EvidenceItem:
    evidence_type: str
    comparison_result: EvidenceStatus
    observed_value: Any = None
    expected_value: Any = None
    source_asset: str | None = None
    source_location: str | None = None
    created_by: str | None = None
    reviewed_by: str | None = None
    reliability: str | None = None
    notes: str | None = None
    evidence_id: str = field(default_factory=lambda: f"EVI-{uuid4().hex[:10].upper()}")
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["comparison_result"] = self.comparison_result.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceItem":
        payload = dict(data)
        payload["comparison_result"] = EvidenceStatus(payload.get("comparison_result", EvidenceStatus.NOT_VERIFIED.value))
        return cls(**payload)


@dataclass
class ReassessmentTrigger:
    trigger_type: str
    category: TriggerCategory
    old_value: Any
    new_value: Any
    affected_entity: str
    severity: TriggerSeverity
    reassessment_required: bool
    resulting_state: LifecycleStewardshipState
    recommended_action: str
    assessment_consequence: str = "Relationship evidence should be reassessed when this trigger is material."
    trigger_id: str = field(default_factory=lambda: f"TRG-{uuid4().hex[:10].upper()}")
    detected_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["severity"] = self.severity.value
        data["resulting_state"] = self.resulting_state.value
        # Explicit aliases make exported trigger evidence align with the thesis terminology.
        data["entity"] = self.affected_entity
        data["timestamp"] = self.detected_at
        data["previous_value"] = self.old_value
        data["current_value"] = self.new_value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReassessmentTrigger":
        payload = dict(data)
        payload.pop("entity", None)
        payload.pop("timestamp", None)
        payload.pop("previous_value", None)
        payload.pop("current_value", None)
        payload["category"] = TriggerCategory(payload["category"])
        payload["severity"] = TriggerSeverity(payload["severity"])
        payload["resulting_state"] = LifecycleStewardshipState(payload["resulting_state"])
        return cls(**payload)


@dataclass
class GeometryMeasurementRelationship:
    subject_component_id: str
    subject_ifc_global_id: str
    subject_ifc_file_id: str
    object_measurement_id: str
    relationship_type: RelationshipType
    scope: str = "component"
    rationale: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    matching_attributes: list[str] = field(default_factory=list)
    excluded_attributes: list[str] = field(default_factory=list)
    confidence_basis: str | None = None
    created_by: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    approval_status: str | None = None
    last_reviewed_at: str | None = None
    last_reviewed_by: str | None = None
    relationship_version: str = "1.0.0"
    source_component_version: str | None = None
    source_measurement_version: str | None = None
    source_ifc_checksum: str | None = None
    source_dataset_checksum: str | None = None
    status: LifecycleStewardshipState = LifecycleStewardshipState.UNASSESSED
    recommended_action: str | None = None
    trigger_history: list[ReassessmentTrigger] = field(default_factory=list)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    supersedes_relationship: str | None = None
    invalidated_by: str | None = None
    notes: str | None = None
    relationship_id: str = field(default_factory=lambda: f"REL-{uuid4().hex[:10].upper()}")
    created_at: str = field(default_factory=utc_now)

    @property
    def requires_manual_review(self) -> bool:
        return self.status == LifecycleStewardshipState.MANUAL_REVIEW or any(
            item.comparison_result in {EvidenceStatus.CONTRADICTS, EvidenceStatus.REQUIRES_REVIEW}
            for item in self.evidence
        )

    def evidence_summary(self) -> dict[str, int]:
        summary = {status.value: 0 for status in EvidenceStatus}
        for item in self.evidence:
            summary[item.comparison_result.value] += 1
        return summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "subject_component_id": self.subject_component_id,
            "subject_ifc_global_id": self.subject_ifc_global_id,
            "subject_ifc_file_id": self.subject_ifc_file_id,
            "object_measurement_id": self.object_measurement_id,
            "relationship_type": self.relationship_type.value,
            "scope": self.scope,
            "rationale": self.rationale,
            "evidence": [item.to_dict() for item in self.evidence],
            "matching_attributes": list(self.matching_attributes),
            "excluded_attributes": list(self.excluded_attributes),
            "confidence_basis": self.confidence_basis,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "approval_status": self.approval_status,
            "last_reviewed_at": self.last_reviewed_at,
            "last_reviewed_by": self.last_reviewed_by,
            "relationship_version": self.relationship_version,
            "source_component_version": self.source_component_version,
            "source_measurement_version": self.source_measurement_version,
            "source_ifc_checksum": self.source_ifc_checksum,
            "source_dataset_checksum": self.source_dataset_checksum,
            "status": self.status.value,
            "recommended_action": self.recommended_action,
            "trigger_history": [item.to_dict() for item in self.trigger_history],
            "decision_history": list(self.decision_history),
            "supersedes_relationship": self.supersedes_relationship,
            "invalidated_by": self.invalidated_by,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeometryMeasurementRelationship":
        payload = dict(data)
        payload["relationship_type"] = RelationshipType(payload.get("relationship_type", RelationshipType.UNKNOWN.value))
        payload["status"] = LifecycleStewardshipState(payload.get("status", LifecycleStewardshipState.UNASSESSED.value))
        payload["evidence"] = [EvidenceItem.from_dict(item) for item in payload.get("evidence", [])]
        payload["trigger_history"] = [ReassessmentTrigger.from_dict(item) for item in payload.get("trigger_history", [])]
        return cls(**payload)


def relationship_type_allowed_for_origin(origin: MeasurementOrigin | str, relationship_type: RelationshipType | str) -> tuple[bool, str]:
    """Return transparent compatibility guidance between dataset origin and relationship type."""
    origin_value = origin.value if isinstance(origin, MeasurementOrigin) else str(origin)
    relationship_value = relationship_type.value if isinstance(relationship_type, RelationshipType) else str(relationship_type)
    measurement_origins = {MeasurementOrigin.RAW_MEASUREMENT.value, MeasurementOrigin.PROCESSED_MEASUREMENT.value}
    if relationship_value == RelationshipType.MEASURED_ON.value and origin_value not in measurement_origins:
        return False, "MEASURED_ON is reserved for direct/processed measurement-origin data with appropriate physical measurement evidence."
    if origin_value == MeasurementOrigin.CATALOG_RECORD.value and relationship_value == RelationshipType.MEASURED_ON.value:
        return False, "A catalog record without direct measurement evidence cannot be labelled MEASURED_ON."
    if origin_value in {MeasurementOrigin.SIMULATION_RESULT.value, MeasurementOrigin.PREDICTED_VALUE.value} and relationship_value not in {
        RelationshipType.PREDICTED_FOR.value,
        RelationshipType.CHARACTERIZES.value,
        RelationshipType.REFERENCES.value,
        RelationshipType.UNKNOWN.value,
    }:
        return False, "Simulation/prediction data should use PREDICTED_FOR, CHARACTERIZES, REFERENCES, or remain explicitly unknown pending review."
    return True, "Relationship type is compatible with the declared dataset-origin classification at the prototype rule level."


def relationship_strength_statement(relationship: GeometryMeasurementRelationship) -> str:
    """Return a transparent qualitative statement; never a pseudo-scientific confidence score."""
    summary = relationship.evidence_summary()
    if summary[EvidenceStatus.CONTRADICTS.value]:
        return "Contradictory evidence is present; expert review is required."
    if relationship.relationship_type == RelationshipType.MEASURED_ON and summary[EvidenceStatus.SUPPORTS.value]:
        return "Direct measurement claim with supporting recorded evidence."
    if relationship.relationship_type == RelationshipType.APPLICABLE_TO_EQUIVALENT_ASSEMBLY:
        return "Transfer-by-equivalence claim; applicability depends on the recorded matching attributes and exclusions."
    if relationship.relationship_type == RelationshipType.PREDICTED_FOR:
        return "Prediction claim; this is not equivalent to a physical measurement on the IFC component."
    if relationship.relationship_type == RelationshipType.REFERENCES:
        return "Reference relationship; the source may inform the component but is not asserted as a direct measurement."
    if not relationship.evidence:
        return "Relationship claim has no structured evidence yet."
    return "Relationship strength is described by the recorded evidence items; no numerical confidence score is asserted."
