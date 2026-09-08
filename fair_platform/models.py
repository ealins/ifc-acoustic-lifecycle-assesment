from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
class FairDimensionResult:
    passed: bool
    checks: dict[str, bool]
    score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        return round(
            (
                self.findable.score
                + self.accessible.score
                + self.interoperable.score
                + self.reusable.score
            ) / 4,
            3,
        )

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
    assets: dict[str, bytes] = field(default_factory=dict, repr=False)

    def to_dict(self, include_assets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["fair_status"] = self.fair_status.value
        if not include_assets:
            data.pop("assets", None)
        return data
