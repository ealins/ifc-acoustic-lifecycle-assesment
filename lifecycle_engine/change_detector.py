"""Rigorous change detection with field-level analysis and confidence metrics."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Set, Tuple
from datetime import datetime


class ChangeCategory(Enum):
    """Change classification."""
    IFC_EVIDENCE_CHANGE = "ifc_evidence_change"
    ACOUSTIC_CONTENT_CHANGE = "acoustic_content_change"
    PROVENANCE_CHANGE = "provenance_change"
    RESOURCE_AVAILABILITY_CHANGE = "resource_availability_change"
    ASSESSMENT_STATE_CHANGE = "assessment_state_change"
    NO_CHANGE = "no_change"


@dataclass
class ChangeEvent:
    """Detected change."""
    category: ChangeCategory
    field: str
    old_value: Optional[str]
    new_value: Optional[str]
    significance: float
    is_meaningful: bool
    reason: str


@dataclass
class ChangeReport:
    """Comprehensive change analysis."""
    ifc_global_id: str
    record_id: str
    events: List[ChangeEvent]
    overall_category: ChangeCategory
    has_meaningful_changes: bool
    requires_review: bool
    previous_status: Optional[str]
    current_status: Optional[str]
    is_valid_transition: bool
    overall_confidence: float
    
    def to_dict(self):
        return {
            "ifc_global_id": self.ifc_global_id,
            "record_id": self.record_id,
            "events": [
                {
                    "category": e.category.value,
                    "field": e.field,
                    "old": e.old_value,
                    "new": e.new_value,
                    "significance": e.significance,
                    "is_meaningful": e.is_meaningful,
                }
                for e in self.events
            ],
            "overall_category": self.overall_category.value,
            "has_meaningful_changes": self.has_meaningful_changes,
            "requires_review": self.requires_review,
            "overall_confidence": self.overall_confidence,
        }


VALID_TRANSITIONS = {
    "acceptable": {"acceptable", "ambiguous", "invalid", "broken", "semantically_stale"},
    "ambiguous": {"ambiguous", "acceptable", "invalid", "broken"},
    "invalid": {"invalid", "acceptable", "ambiguous", "broken"},
    "broken": {"broken", "acceptable", "ambiguous", "invalid"},
    "semantically_stale": {"semantically_stale", "acceptable", "ambiguous", "broken"},
}


def compute_significance(field: str, old: str, new: str) -> Tuple[float, bool]:
    """Significance 0-1 and if meaningful."""
    if old == new:
        return (0.0, False)
    
    critical = {
        "ifc_global_id", "construction_family", "total_thickness_m",
        "rw", "uri_resolvable", "available",
    }
    if any(c in field for c in critical):
        return (0.9, True)
    
    if "material" in field or "layer" in field:
        return (0.7, True)
    
    if "provenance" in field or "status" in field:
        return (0.65, True)
    
    return (0.3, False)


def detect_changes(prev: Dict, curr: Dict) -> ChangeReport:
    """Rigorous change detection."""
    events = []
    categories = set()
    meaningful = 0
    
    all_keys = set(prev.keys()) | set(curr.keys())
    
    for key in all_keys:
        if key == "assessment_timestamp":
            continue
        
        old_v = str(prev.get(key, ""))
        new_v = str(curr.get(key, ""))
        
        if old_v == new_v:
            continue
        
        sig, is_mean = compute_significance(key, old_v, new_v)
        
        # Category
        if "ifc" in key:
            cat = ChangeCategory.IFC_EVIDENCE_CHANGE
        elif "rw" in key or "acoustic" in key:
            cat = ChangeCategory.ACOUSTIC_CONTENT_CHANGE
        elif "provenance" in key:
            cat = ChangeCategory.PROVENANCE_CHANGE
        elif "available" in key or "resolved" in key:
            cat = ChangeCategory.RESOURCE_AVAILABILITY_CHANGE
        else:
            cat = ChangeCategory.ASSESSMENT_STATE_CHANGE
        
        events.append(ChangeEvent(
            category=cat,
            field=key,
            old_value=old_v[:40],
            new_value=new_v[:40],
            significance=sig,
            is_meaningful=is_mean,
            reason=f"{key} changed",
        ))
        
        categories.add(cat)
        if is_mean:
            meaningful += 1
    
    # Overall
    if not events:
        overall = ChangeCategory.NO_CHANGE
        has_mean = False
    else:
        overall = list(categories)[0] if len(categories) == 1 else ChangeCategory.ASSESSMENT_STATE_CHANGE
        has_mean = meaningful > 0
    
    # Transition validation
    prev_s = prev.get("semantic_status")
    curr_s = curr.get("semantic_status")
    is_valid = True
    if prev_s and curr_s and prev_s != curr_s:
        is_valid = str(curr_s).lower() in VALID_TRANSITIONS.get(str(prev_s).lower(), set())
    
    conf = 0.95 if not events else (0.5 + min(1.0, sum(e.significance for e in events) / len(events)) * 0.45)
    
    requires_review = has_mean or not is_valid or overall in [
        ChangeCategory.IFC_EVIDENCE_CHANGE,
        ChangeCategory.RESOURCE_AVAILABILITY_CHANGE,
    ]
    
    return ChangeReport(
        ifc_global_id=curr.get("ifc_global_id", "unknown"),
        record_id=curr.get("record_id", "unknown"),
        events=events,
        overall_category=overall,
        has_meaningful_changes=has_mean,
        requires_review=requires_review,
        previous_status=prev_s,
        current_status=curr_s,
        is_valid_transition=is_valid,
        overall_confidence=conf,
    )
