"""
Core data models for GeoBIM semantic lifecycle.

These models represent the canonical structures for:
- IFC building element evidence
- External performance record evidence
- Lifecycle snapshots and versioning
- Change events and revisions
- Semantic assessment outcomes
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
import hashlib


def now_iso() -> str:
    """Return current timestamp in ISO 8601 format."""
    return datetime.utcnow().isoformat() + "Z"


def stable_hash(obj: Dict) -> str:
    """
    Compute SHA-256 hash over a dict with stable key ordering.
    Ensures identical hashes for equivalent structures regardless of key order.
    """
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ============================================================================
# Enums: Status and classification
# ============================================================================


class TechnicalResolutionStatus(Enum):
    """Technical availability and reachability of external records."""
    RESOLVED = "resolved"
    BROKEN = "broken"
    TIMEOUT = "timeout"
    ACCESS_DENIED = "access_denied"
    REDIRECTED = "redirected"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    WRONG_CONTENT_TYPE = "wrong_content_type"


class SemanticStatus(Enum):
    """Semantic validity of the IFC-record association."""
    ACCEPTABLE = "acceptable"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    UNMATCHED = "unmatched"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    BROKEN = "broken"
    SEMANTICALLY_STALE = "semantically_stale"


class ChangeCategory(Enum):
    """Categories of meaningful change."""
    IFC_EVIDENCE_CHANGE = "ifc_evidence_change"
    RECORD_CONTENT_CHANGE = "record_content_change"
    PROVENANCE_CHANGE = "provenance_change"
    RESOURCE_AVAILABILITY_CHANGE = "resource_availability_change"
    ASSESSMENT_STATE_CHANGE = "assessment_state_change"
    SEMANTIC_PROFILE_CHANGE = "semantic_profile_change"
    VALIDATION_POLICY_CHANGE = "validation_policy_change"
    NO_CHANGE = "no_change"


class IDSReadinessStatus(Enum):
    """IDS evidence-readiness validation outcome."""
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"


class BsDDAlignmentStatus(Enum):
    """bSDD term alignment classification."""
    ALIGNED = "aligned"
    PARTIAL = "partial"
    UNALIGNED = "unaligned"


class RevisionAction(Enum):
    """Decision on whether to create a new MappingAssertion revision."""
    NO_CHANGE_NO_REVISION = "no_change_no_revision"
    CREATED_REVISION = "created_revision"


class CarrierProfile(Enum):
    """IFC reference carrier strategy."""
    NATIVE_ONLY = "native_only"
    HYBRID_SEMANTIC_ROUTING = "hybrid_semantic_routing"
    EXTERNAL_ONLY = "external_only"
