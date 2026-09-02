"""Orchestrates lifecycle evaluation."""

from datetime import datetime
import json
from typing import Dict, Optional

from lifecycle_engine.assessment import (
    assess_association, IFCEvidence, RecordEvidence, SemanticStatus,
)
from lifecycle_engine.change_detector import detect_changes, ChangeCategory
from lifecycle_engine.models import now_iso, stable_hash


def run_lifecycle_evaluation(
    ifc_wall: Dict,
    acoustic_record: Dict,
    previous_assessment: Optional[Dict] = None,
    domain: str = "acoustic",
) -> Dict:
    """Run complete lifecycle evaluation."""
    
    # Create evidence objects
    ifc_ev = IFCEvidence(
        global_id=ifc_wall.get("global_id"),
        name=ifc_wall.get("name", ""),
        construction_family=ifc_wall.get("construction_family", "generic"),
        total_thickness_m=ifc_wall.get("total_thickness_m"),
        material_evidence=ifc_wall.get("material_evidence", []),
        model_version=ifc_wall.get("model_version", "unknown"),
    )
    
    record_ev = RecordEvidence(
        uri=acoustic_record.get("uri", ""),
        identifier=acoustic_record.get("identifier", ""),
        assembly=acoustic_record.get("assembly", ""),
        construction_family=acoustic_record.get("construction_family", "generic"),
        total_thickness_m=acoustic_record.get("total_thickness_m"),
        record_version=acoustic_record.get("record_version", "unknown"),
        available=acoustic_record.get("available", True),
    )
    
    # Assess
    if not record_ev.available:
        assessment = assess_association(ifc_ev, record_ev)
        assessment.semantic_status = SemanticStatus.BROKEN
    else:
        assessment = assess_association(ifc_ev, record_ev)
    
    # Build snapshot
    current = {
        "ifc_global_id": ifc_ev.global_id,
        "record_id": record_ev.identifier,
        "assessment_timestamp": now_iso(),
        "semantic_status": assessment.semantic_status.value,
        "technical_status": assessment.technical_status.value,
        "confidence": assessment.confidence,
        "reason": assessment.reason,
        "ifc": {
            "global_id": ifc_ev.global_id,
            "name": ifc_ev.name,
            "construction_family": ifc_ev.construction_family,
            "total_thickness_m": ifc_ev.total_thickness_m,
        },
        "record": {
            "identifier": record_ev.identifier,
            "construction_family": record_ev.construction_family,
            "total_thickness_m": record_ev.total_thickness_m,
            "rw": acoustic_record.get("rw"),
        },
        "resource": {
            "available": record_ev.available,
        }
    }
    
    # Changes
    change_report = None
    action = "created_revision"
    
    if previous_assessment:
        change_report = detect_changes(previous_assessment, current)
        if (
            not change_report.has_meaningful_changes
            and change_report.overall_category == ChangeCategory.NO_CHANGE
        ):
            action = "no_change_no_revision"
    
    result = {
        "timestamp": now_iso(),
        "assessment": current,
        "change_report": change_report.to_dict() if change_report else None,
        "revision_action": action,
        "requires_review": assessment.semantic_status in [
            SemanticStatus.AMBIGUOUS, SemanticStatus.INVALID, SemanticStatus.BROKEN,
        ] or assessment.confidence < 0.7,
    }
    
    return result
