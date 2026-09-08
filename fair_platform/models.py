from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FairStatus(str, Enum):
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
    package_id: str
    geometry_reference: str
    measurement_reference: str
    metadata_reference: str
    provenance: dict[str, Any]
    version: str
    identifier: str
    creator: Optional[str] = None
    created: str = field(default_factory=utc_now)
    license: Optional[str] = None
    measurement_context: dict[str, Any] = field(default_factory=dict)
    quality_information: dict[str, Any] = field(default_factory=dict)
    ifc_global_id: Optional[str] = None
    dataset_uri: Optional[str] = None
    mapping_series_uri: Optional[str] = None
    latest_mapping_assertion_uri: Optional[str] = None
    fair_status: FairStatus = FairStatus.PARTIALLY_FAIR
    lifecycle_status: str = "UNASSESSED"
    findable: bool = False
    accessible: bool = False
    interoperable: bool = False
    reusable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    fair_assessment: dict[str, Any] = field(default_factory=dict)
    stewardship_history: list[dict[str, Any]] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    assets: dict[str, bytes] = field(default_factory=dict, repr=False)

    @property
    def lifecycle_display_status(self) -> str:
        return "STALE" if self.lifecycle_status == "SEMANTICALLY_STALE" else self.lifecycle_status

    @property
    def title(self) -> str:
        return str(self.metadata.get("title") or self.metadata.get("measurement_identifier") or self.package_id)

    def to_dict(self, include_assets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["fair_status"] = self.fair_status.value
        data["lifecycle_display_status"] = self.lifecycle_display_status
        if not include_assets:
            data.pop("assets", None)
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FairAcousticPackage":
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in payload.items() if key in allowed and key != "assets"}
        values["fair_status"] = FairStatus(values.get("fair_status", FairStatus.PARTIALLY_FAIR.value))
        return cls(**values)
