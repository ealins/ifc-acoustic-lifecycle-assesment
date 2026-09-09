from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FairStatus(str, Enum):
    """Legacy FAIR labels retained for backward compatibility.

    New user-facing evaluation uses fair_support_status and does not claim certification.
    """

    FAIR_READY = "FAIR_READY"
    PARTIALLY_FAIR = "PARTIALLY_FAIR"
    NOT_FINDABLE = "NOT_FINDABLE"
    NOT_ACCESSIBLE = "NOT_ACCESSIBLE"
    NOT_INTEROPERABLE = "NOT_INTEROPERABLE"
    NOT_REUSABLE = "NOT_REUSABLE"


@dataclass
class FairCriterionResult:
    key: str
    label: str
    passed: bool
    evidence: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FairDimensionResult:
    name: str
    criteria: list[FairCriterionResult]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.criteria)

    @property
    def checks(self) -> dict[str, bool]:
        return {item.key: item.passed for item in self.criteria}

    @property
    def score(self) -> float:
        return sum(item.passed for item in self.criteria) / len(self.criteria) if self.criteria else 0.0

    @property
    def reasons(self) -> list[str]:
        return [item.key for item in self.criteria if not item.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "checks": self.checks,
            "criteria": [item.to_dict() for item in self.criteria],
        }


@dataclass
class FairAssessmentResult:
    findable: FairDimensionResult
    accessible: FairDimensionResult
    interoperable: FairDimensionResult
    reusable: FairDimensionResult
    fair_status: FairStatus
    blocking_states: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return round(sum(d.score for d in self.dimensions) / 4, 3)

    @property
    def dimensions(self) -> list[FairDimensionResult]:
        return [self.findable, self.accessible, self.interoperable, self.reusable]

    def to_dict(self) -> dict[str, Any]:
        return {
            "findable": self.findable.to_dict(),
            "accessible": self.accessible.to_dict(),
            "interoperable": self.interoperable.to_dict(),
            "reusable": self.reusable.to_dict(),
            "fair_status": self.fair_status.value,
            "blocking_states": self.blocking_states,
            "score": self.score,
        }


@dataclass
class FairAcousticPackage:
    """Backward-compatible storage model for an acoustic component research object.

    The in-memory model is authoritative. ``ro-crate-metadata.json`` is the
    principal portable representation, ``metadata.ttl`` represents domain and
    provenance relationships, and ``manifest.json`` remains an application
    compatibility manifest. The ZIP is an exchange serialization, not the domain
    model itself.
    """

    package_id: str
    geometry_reference: str
    measurement_reference: str
    metadata_reference: str
    provenance: dict[str, Any]
    version: str
    identifier: str
    creator: Optional[str] = None
    created: str = field(default_factory=utc_now)
    modified: Optional[str] = None
    license: Optional[str] = None
    measurement_context: dict[str, Any] = field(default_factory=dict)
    quality_information: dict[str, Any] = field(default_factory=dict)
    research_context: dict[str, Any] = field(default_factory=dict)
    simulation_context: dict[str, Any] = field(default_factory=dict)
    access_context: dict[str, Any] = field(default_factory=dict)
    ifc_global_id: Optional[str] = None
    dataset_uri: Optional[str] = None
    mapping_series_uri: Optional[str] = None
    latest_mapping_assertion_uri: Optional[str] = None
    research_object_profile: str = "https://example.org/fair-acoustic/profile/acoustic-component-ro/0.2"
    metadata_profile: str = "https://example.org/fair-acoustic/profile/acoustic-component-metadata/0.2"
    metadata_profile_version: str = "0.2"
    acoustic_datasets: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    asset_records: list[dict[str, Any]] = field(default_factory=list)
    metadata_completeness_status: str = "VALIDATION_INCOMPLETE"
    fair_support_status: str = "ASSESSMENT_INCOMPLETE"
    scientific_suitability_status: str = "NOT_ASSESSED"
    fair_status: FairStatus = FairStatus.PARTIALLY_FAIR
    lifecycle_status: str = "UNASSESSED"
    findable: bool = False
    accessible: bool = False
    interoperable: bool = False
    reusable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    metadata_completeness_assessment: dict[str, Any] = field(default_factory=dict)
    fair_assessment: dict[str, Any] = field(default_factory=dict)
    fair_support_assessment: dict[str, Any] = field(default_factory=dict)
    stewardship_history: list[dict[str, Any]] = field(default_factory=list)
    reassessment_triggers: list[dict[str, Any]] = field(default_factory=list)
    validation_report: dict[str, Any] = field(default_factory=dict)
    checksums: dict[str, str] = field(default_factory=dict)
    assets: dict[str, bytes] = field(default_factory=dict, repr=False)

    @property
    def lifecycle_display_status(self) -> str:
        return "STALE" if self.lifecycle_status == "SEMANTICALLY_STALE" else self.lifecycle_status

    @property
    def title(self) -> str:
        return str(self.metadata.get("title") or self.metadata.get("measurement_identifier") or self.package_id)

    @property
    def object_type(self) -> str:
        return "AcousticComponentResearchObject"

    @property
    def independent_outcomes(self) -> dict[str, str]:
        return {
            "metadata_completeness": self.metadata_completeness_status,
            "fair_support": self.fair_support_status,
            "relationship_lifecycle": self.lifecycle_display_status,
            "acoustic_scientific_suitability": self.scientific_suitability_status,
        }

    def to_dict(self, include_assets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["fair_status"] = self.fair_status.value
        data["lifecycle_display_status"] = self.lifecycle_display_status
        data["object_type"] = self.object_type
        data["independent_outcomes"] = self.independent_outcomes
        if not include_assets:
            data.pop("assets", None)
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FairAcousticPackage":
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in payload.items() if key in allowed and key != "assets"}
        values["fair_status"] = FairStatus(values.get("fair_status", FairStatus.PARTIALLY_FAIR.value))
        return cls(**values)


@dataclass
class AcousticComponentResearchObject(FairAcousticPackage):
    """Preferred domain name for new metadata-centered research-object workflows."""

    pass


# Compatibility aliases used in thesis text and older integrations.
AcousticComponentPackage = AcousticComponentResearchObject
FairAcousticComponentPackage = AcousticComponentResearchObject
