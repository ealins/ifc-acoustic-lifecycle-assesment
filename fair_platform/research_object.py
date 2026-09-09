from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from .models import utc_now


PROFILE_ID = "https://example.org/fair-acoustic/profile/acoustic-component-ro/0.1"
PROFILE_LABEL = "Prototype Acoustic Component Research-Object Profile"


class MeasurementOrigin(str, Enum):
    RAW_MEASUREMENT = "raw_measurement"
    PROCESSED_MEASUREMENT = "processed_measurement"
    DERIVED_RESULT = "derived_result"
    REFERENCE_VALUE = "reference_value"
    MANUFACTURER_VALUE = "manufacturer_value"
    PREDICTED_VALUE = "predicted_value"
    SIMULATION_RESULT = "simulation_result"
    UNKNOWN = "unknown"


class RelationshipType(str, Enum):
    MEASURED_ON = "measuredOn"
    CHARACTERIZES = "characterizes"
    DERIVED_FROM_MEASUREMENT_OF = "derivedFromMeasurementOf"
    APPLICABLE_TO_EQUIVALENT_ASSEMBLY = "applicableToEquivalentAssembly"
    PREDICTED_FOR = "predictedFor"
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
    trigger_id: str = field(default_factory=lambda: f"TRG-{uuid4().hex[:10].upper()}")
    detected_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["severity"] = self.severity.value
        data["resulting_state"] = self.resulting_state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReassessmentTrigger":
        payload = dict(data)
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
    last_reviewed_at: str | None = None
    last_reviewed_by: str | None = None
    relationship_version: str = "1.0.0"
    source_component_version: str | None = None
    source_measurement_version: str | None = None
    status: LifecycleStewardshipState = LifecycleStewardshipState.UNASSESSED
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
            "last_reviewed_at": self.last_reviewed_at,
            "last_reviewed_by": self.last_reviewed_by,
            "relationship_version": self.relationship_version,
            "source_component_version": self.source_component_version,
            "source_measurement_version": self.source_measurement_version,
            "status": self.status.value,
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
    if not relationship.evidence:
        return "Relationship claim has no structured evidence yet."
    return "Relationship strength is described by the recorded evidence items; no numerical confidence score is asserted."
