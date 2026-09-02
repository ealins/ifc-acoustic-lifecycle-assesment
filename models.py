from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class EvidenceSnapshot:
    side: str
    values: dict[str, Any]
    captured_at: str = field(default_factory=utc_now)


@dataclass
class ChangeEvent:
    category: str
    side: str
    field: str
    old_value: Any
    new_value: Any


@dataclass
class ValidationActivity:
    revision_number: int
    timestamp: str
    activity_id: str
    checks: list[str]


@dataclass
class MappingSeries:
    uri: str
    ifc_global_id: str
    record_id: str


@dataclass
class MappingAssertion:
    revision_number: int
    timestamp: str
    mapping_series_uri: str
    ifc_snapshot: EvidenceSnapshot
    rdf_snapshot: EvidenceSnapshot
    technical_link_state: str
    link_status: str
    data_status: str
    mapping_series_validity: str
    ids_status: str
    bsdd_status: str
    semantic_status: str
    requires_review: bool
    rationale: str
    change_events: list[ChangeEvent] = field(default_factory=list)
    previous_revision: int | None = None
    validation_activity: ValidationActivity | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "revision_number": self.revision_number,
            "timestamp": self.timestamp,
            "mapping_series_uri": self.mapping_series_uri,
            "technical_link_state": self.technical_link_state,
            "link_status": self.link_status,
            "data_status": self.data_status,
            "mapping_series_validity": self.mapping_series_validity,
            "ids_status": self.ids_status,
            "bsdd_status": self.bsdd_status,
            "semantic_status": self.semantic_status,
            "requires_review": self.requires_review,
            "rationale": self.rationale,
            "change_events": [event.__dict__ for event in self.change_events],
        }
