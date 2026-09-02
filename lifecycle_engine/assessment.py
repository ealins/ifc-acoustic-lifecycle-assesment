"""
Semantic assessment engine for IFC-external record associations.

Implements the core logic for determining whether an IFC wall evidence
can be reliably mapped to an external acoustic record (VaBDat, bSDD, etc.).

3-tier assessment:
1. Technical Resolution: Is the record URI resolvable?
2. Structural Compatibility: Do IFC evidence and record align on construction family/thickness?
3. Semantic Status: Is the association acceptable, ambiguous, or invalid?
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple
from datetime import datetime
import hashlib
import json


class SemanticStatus(Enum):
    """Semantic validity of IFC-record association."""
    ACCEPTABLE = "acceptable"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    UNMATCHED = "unmatched"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    BROKEN = "broken"
    SEMANTICALLY_STALE = "semantically_stale"


class TechnicalResolutionStatus(Enum):
    """Technical availability of external records."""
    RESOLVED = "resolved"
    BROKEN = "broken"
    TIMEOUT = "timeout"
    ACCESS_DENIED = "access_denied"


@dataclass
class IFCEvidence:
    """IFC wall evidence snapshot."""
    global_id: str
    name: str
    construction_family: str
    total_thickness_m: Optional[float]
    material_evidence: list
    model_version: str


@dataclass
class RecordEvidence:
    """External record evidence snapshot (acoustic, thermal, etc.)."""
    uri: str
    identifier: str
    assembly: str
    construction_family: str
    total_thickness_m: Optional[float]
    record_version: str
    available: bool = True


@dataclass
class AssessmentResult:
    """Outcome of semantic assessment."""
    ifc_global_id: str
    record_id: str
    semantic_status: SemanticStatus
    technical_status: TechnicalResolutionStatus
    reason: str
    confidence: float  # 0.0–1.0
    thickness_match: Optional[bool]
    family_match: Optional[bool]
    assessment_timestamp: str


def stable_hash(obj: Dict) -> str:
    """Compute SHA-256 hash over dict with stable key ordering."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def now_iso() -> str:
    """Return current timestamp in ISO 8601 format."""
    return datetime.utcnow().isoformat() + "Z"


def assess_association(
    ifc_evidence: IFCEvidence,
    record_evidence: RecordEvidence,
    thickness_tolerance_m: float = 0.02,
) -> AssessmentResult:
    """
    Perform 3-tier semantic assessment of IFC-record association.
    
    Returns AssessmentResult with status (ACCEPTABLE/AMBIGUOUS/INVALID),
    confidence score, and detailed reasoning.
    """
    
    # Tier 1: Technical Resolution
    if not record_evidence.available:
        return AssessmentResult(
            ifc_global_id=ifc_evidence.global_id,
            record_id=record_evidence.identifier,
            semantic_status=SemanticStatus.BROKEN,
            technical_status=TechnicalResolutionStatus.BROKEN,
            reason="External record is unavailable (broken link or deleted).",
            confidence=0.0,
            thickness_match=None,
            family_match=None,
            assessment_timestamp=now_iso(),
        )
    
    # Tier 2: Structural Compatibility
    family_match = (
        ifc_evidence.construction_family.lower() 
        == record_evidence.construction_family.lower()
    )
    thickness_match = False
    if (ifc_evidence.total_thickness_m is not None 
        and record_evidence.total_thickness_m is not None):
        thickness_diff = abs(
            ifc_evidence.total_thickness_m - record_evidence.total_thickness_m
        )
        thickness_match = thickness_diff <= thickness_tolerance_m
    
    # Tier 3: Semantic Status determination
    if family_match and thickness_match:
        semantic_status = SemanticStatus.ACCEPTABLE
        reason = (
            f"Family and thickness aligned. IFC: {ifc_evidence.construction_family} "
            f"{ifc_evidence.total_thickness_m}m, Record: {record_evidence.construction_family} "
            f"{record_evidence.total_thickness_m}m."
        )
        confidence = 0.95
    elif family_match:
        semantic_status = SemanticStatus.AMBIGUOUS
        reason = (
            f"Family matched ({ifc_evidence.construction_family}), "
            f"but thickness diverged. IFC: {ifc_evidence.total_thickness_m}m, "
            f"Record: {record_evidence.total_thickness_m}m."
        )
        confidence = 0.70
    elif thickness_match:
        semantic_status = SemanticStatus.AMBIGUOUS
        reason = (
            f"Thickness aligned ({ifc_evidence.total_thickness_m}m), "
            f"but family diverged. IFC: {ifc_evidence.construction_family}, "
            f"Record: {record_evidence.construction_family}."
        )
        confidence = 0.65
    else:
        semantic_status = SemanticStatus.INVALID
        reason = (
            f"Both family and thickness diverged. IFC: {ifc_evidence.construction_family} "
            f"{ifc_evidence.total_thickness_m}m, Record: {record_evidence.construction_family} "
            f"{record_evidence.total_thickness_m}m. Association requires human review."
        )
        confidence = 0.20
    
    return AssessmentResult(
        ifc_global_id=ifc_evidence.global_id,
        record_id=record_evidence.identifier,
        semantic_status=semantic_status,
        technical_status=TechnicalResolutionStatus.RESOLVED,
        reason=reason,
        confidence=confidence,
        thickness_match=thickness_match,
        family_match=family_match,
        assessment_timestamp=now_iso(),
    )


def batch_assess(
    ifc_list: list,
    record_list: list,
    thickness_tolerance_m: float = 0.02,
) -> list:
    """Assess all IFC-record pairs and return results."""
    results = []
    for ifc in ifc_list:
        for record in record_list:
            result = assess_association(ifc, record, thickness_tolerance_m)
            results.append(result)
    return results
