"""Lifecycle Bridge - IFC-VaBDat Bi-directional Validation"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from association_lifecycle import (
    WallEvidence, RecordEvidence, semantic_assessment, REVIEW_STATUSES, now_iso
)


class ChangeType(Enum):
    IFC_EVIDENCE_CHANGE = "ifc_evidence_change"
    ACOUSTIC_CONTENT_CHANGE = "acoustic_content_change"
    METADATA_CHANGE = "metadata_change"
    AVAILABILITY_CHANGE = "availability_change"
    SEMANTIC_STATUS_CHANGE = "semantic_status_change"
    NO_CHANGE = "no_change"


class ReviewPriority(Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class EvidenceSnapshot:
    timestamp: str
    evidence_type: str
    fingerprint: str
    content: Dict
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ChangeEvent:
    change_type: ChangeType
    previous_fingerprint: Optional[str]
    current_fingerprint: str
    field_name: Optional[str] = None
    previous_value: Optional[str] = None
    current_value: Optional[str] = None
    detected_at: str = field(default_factory=now_iso)
    
    def to_dict(self):
        return {
            "change_type": self.change_type.value,
            "previous_fingerprint": self.previous_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "field_name": self.field_name,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "detected_at": self.detected_at,
        }


@dataclass
class ValidationDecision:
    should_create_revision: bool
    reason: str
    changes_detected: List[ChangeEvent]
    proposed_status: str
    review_priority: Optional[ReviewPriority] = None
    rationale: str = ""
    timestamp: str = field(default_factory=now_iso)
    
    def to_dict(self):
        return {
            "should_create_revision": self.should_create_revision,
            "reason": self.reason,
            "changes_detected": [c.to_dict() for c in self.changes_detected],
            "proposed_status": self.proposed_status,
            "review_priority": self.review_priority.value if self.review_priority else None,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }
