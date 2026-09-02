"""
Validation layer for IFC-VaBDat bi-directional lifecycle.

Provides 3-tier validation (Link/Mapping/Lifecycle) wrapping existing 
association_lifecycle.py functions.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import sys
from pathlib import Path

# Import from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from association_lifecycle import (
    WallEvidence,
    RecordEvidence,
    semantic_assessment,
    structural_check,
    STATUS_URI,
    REVIEW_STATUSES,
)


class ValidationTier(Enum):
    """Three tiers of validation."""
    LINK = "link"
    MAPPING = "mapping"
    LIFECYCLE = "lifecycle"


class ValidationStatus(Enum):
    """Validation result status."""
    ACCEPTABLE = "ACCEPTABLE"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    UNMATCHED = "UNMATCHED"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    BROKEN = "BROKEN"
    SEMANTICALLY_STALE = "SEMANTICALLY_STALE"


@dataclass
class ValidationCheck:
    """A single validation check result."""
    name: str
    passed: bool
    tier: ValidationTier
    description: str
    details: Optional[str] = None
    status_uri: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result across all tiers."""
    tier_1_link: list = field(default_factory=list)
    tier_2_mapping: list = field(default_factory=list)
    tier_3_lifecycle: list = field(default_factory=list)
    overall_status: ValidationStatus = ValidationStatus.ACCEPTABLE
    requires_review: bool = False
    rationale: str = ""
    assessment_timestamp: str = ""

    @property
    def all_checks(self) -> list:
        """Get all checks across tiers."""
        return self.tier_1_link + self.tier_2_mapping + self.tier_3_lifecycle

    @property
    def passed_count(self) -> int:
        """Count of passed checks."""
        return sum(1 for check in self.all_checks if check.passed)

    @property
    def failed_count(self) -> int:
        """Count of failed checks."""
        return len(self.all_checks) - self.passed_count

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier_1_link": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "description": c.description,
                    "details": c.details,
                }
                for c in self.tier_1_link
            ],
            "tier_2_mapping": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "description": c.description,
                    "details": c.details,
                }
                for c in self.tier_2_mapping
            ],
            "tier_3_lifecycle": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "description": c.description,
                    "details": c.details,
                }
                for c in self.tier_3_lifecycle
            ],
            "overall_status": self.overall_status.value,
            "requires_review": self.requires_review,
            "rationale": self.rationale,
            "assessment_timestamp": self.assessment_timestamp,
            "summary": {
                "total_checks": len(self.all_checks),
                "passed": self.passed_count,
                "failed": self.failed_count,
            },
        }


class TieredValidator:
    """3-tier validation orchestrator."""

    def __init__(self, thickness_tolerance_m: float = 0.02):
        """
        Initialize validator.

        Args:
            thickness_tolerance_m: Thickness tolerance in meters (default 0.02m = 2cm)
        """
        self.thickness_tolerance_m = thickness_tolerance_m

    def validate_tier_1_link(self, wall: WallEvidence, record: RecordEvidence) -> list:
        """
        Tier 1: Link Validation - verify basic entity existence and identifiers.

        Checks:
        - Wall global ID is not empty
        - Wall name is not empty
        - Record URI is valid
        - Record identifier is not empty
        - Record version is not empty
        """
        checks = []

        # Check 1: Wall global ID
        check_wall_id = ValidationCheck(
            name="Wall Global ID Present",
            passed=bool(wall.global_id and wall.global_id.strip()),
            tier=ValidationTier.LINK,
            description="Wall must have a valid global ID from IFC model",
            details=f"Global ID: {wall.global_id}" if wall.global_id else "No global ID provided",
        )
        checks.append(check_wall_id)

        # Check 2: Wall name
        check_wall_name = ValidationCheck(
            name="Wall Name Present",
            passed=bool(wall.name and wall.name.strip()),
            tier=ValidationTier.LINK,
            description="Wall should have a descriptive name",
            details=f"Name: {wall.name}" if wall.name else "No name provided",
        )
        checks.append(check_wall_name)

        # Check 3: Record URI
        check_record_uri = ValidationCheck(
            name="Record URI Valid",
            passed=bool(record.uri and record.uri.strip() and record.uri.startswith("http")),
            tier=ValidationTier.LINK,
            description="Record must have a valid URI",
            details=f"URI: {record.uri}" if record.uri else "No URI provided",
        )
        checks.append(check_record_uri)

        # Check 4: Record identifier
        check_record_id = ValidationCheck(
            name="Record Identifier Present",
            passed=bool(record.identifier and record.identifier.strip()),
            tier=ValidationTier.LINK,
            description="Record must have a valid identifier",
            details=f"Identifier: {record.identifier}" if record.identifier else "No identifier provided",
        )
        checks.append(check_record_id)

        # Check 5: Record version
        check_record_version = ValidationCheck(
            name="Record Version Present",
            passed=bool(record.record_version and record.record_version.strip()),
            tier=ValidationTier.LINK,
            description="Record must have a version",
            details=f"Version: {record.record_version}" if record.record_version else "No version provided",
        )
        checks.append(check_record_version)

        return checks

    def validate_tier_2_mapping(self, wall: WallEvidence, record: RecordEvidence) -> list:
        """
        Tier 2: Mapping Validation - verify semantic alignment between IFC and bSDD.

        Checks:
        - Construction family matches
        - Material evidence present
        - Record available (not broken link)
        - Assembly information coherent
        """
        checks = []

        # Check 1: Construction family match
        families_match = wall.construction_family == record.construction_family
        check_family = ValidationCheck(
            name="Construction Family Match",
            passed=families_match,
            tier=ValidationTier.MAPPING,
            description="IFC wall family must match bSDD record family",
            details=f"IFC: {wall.construction_family}, bSDD: {record.construction_family}",
        )
        checks.append(check_family)

        # Check 2: Material evidence present
        has_materials = bool(wall.material_evidence and len(wall.material_evidence) > 0)
        check_materials = ValidationCheck(
            name="Material Evidence Present",
            passed=has_materials,
            tier=ValidationTier.MAPPING,
            description="Wall should have material composition evidence",
            details=f"Materials: {', '.join(wall.material_evidence) if wall.material_evidence else 'none'}",
        )
        checks.append(check_materials)

        # Check 3: Record availability
        check_record_avail = ValidationCheck(
            name="Record Available",
            passed=record.available,
            tier=ValidationTier.MAPPING,
            description="External record must be accessible (not broken link)",
            details="Record is " + ("available" if record.available else "unavailable"),
        )
        checks.append(check_record_avail)

        # Check 4: Assembly information
        has_assembly = bool(record.assembly and record.assembly.strip())
        check_assembly = ValidationCheck(
            name="Assembly Information",
            passed=has_assembly,
            tier=ValidationTier.MAPPING,
            description="bSDD record should provide assembly details",
            details=f"Assembly: {record.assembly}" if record.assembly else "No assembly information",
        )
        checks.append(check_assembly)

        return checks

    def validate_tier_3_lifecycle(
        self,
        wall: WallEvidence,
        record: RecordEvidence,
        previous_status: Optional[str] = None,
    ) -> tuple:
        """
        Tier 3: Lifecycle Validation - assess versioning, consistency, and review requirements.

        Uses semantic_assessment from association_lifecycle.py.

        Returns:
            Tuple of (checks list, overall status, requires_review, rationale)
        """
        checks = []

        # Call semantic_assessment to get lifecycle verdict
        assessment_status, assessment_rationale = semantic_assessment(
            wall,
            record,
            previous_status=previous_status,
            thickness_tolerance_m=self.thickness_tolerance_m,
        )

        # Check 1: Model version present
        check_model_version = ValidationCheck(
            name="Model Version Present",
            passed=bool(wall.model_version and wall.model_version.strip()),
            tier=ValidationTier.LIFECYCLE,
            description="IFC model must have version identifier",
            details=f"Version: {wall.model_version}" if wall.model_version else "No version",
        )
        checks.append(check_model_version)

        # Check 2: Record version present
        check_record_ver = ValidationCheck(
            name="Record Version Traceable",
            passed=bool(record.record_version and record.record_version.strip()),
            tier=ValidationTier.LIFECYCLE,
            description="bSDD record must have version for audit trail",
            details=f"Version: {record.record_version}" if record.record_version else "No version",
        )
        checks.append(check_record_ver)

        # Check 3: Semantic assessment result
        assessment_passed = assessment_status == "ACCEPTABLE"
        check_assessment = ValidationCheck(
            name="Semantic Assessment",
            passed=assessment_passed,
            tier=ValidationTier.LIFECYCLE,
            description="Mapping must pass semantic consistency checks",
            details=f"Status: {assessment_status}",
            status_uri=str(STATUS_URI.get(assessment_status, "")),
        )
        checks.append(check_assessment)

        # Determine overall status
        overall_status = ValidationStatus[assessment_status]
        requires_review = assessment_status in REVIEW_STATUSES

        return checks, overall_status, requires_review, assessment_rationale

    def validate_all(
        self,
        wall: WallEvidence,
        record: RecordEvidence,
        previous_status: Optional[str] = None,
    ) -> ValidationResult:
        """
        Run all three tiers of validation and return comprehensive result.

        Args:
            wall: IFC wall evidence
            record: bSDD record evidence
            previous_status: Previous assertion status for lifecycle assessment

        Returns:
            ValidationResult with all tier checks and overall status
        """
        from datetime import datetime, timezone

        result = ValidationResult()
        result.assessment_timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')

        # Tier 1: Link validation
        result.tier_1_link = self.validate_tier_1_link(wall, record)

        # Tier 2: Mapping validation
        result.tier_2_mapping = self.validate_tier_2_mapping(wall, record)

        # Tier 3: Lifecycle validation
        tier_3_checks, overall_status, requires_review, rationale = self.validate_tier_3_lifecycle(
            wall, record, previous_status=previous_status
        )
        result.tier_3_lifecycle = tier_3_checks
        result.overall_status = overall_status
        result.requires_review = requires_review
        result.rationale = rationale

        return result


def structural_check_wrapper(graph_ttl_path: str) -> tuple:
    """
    Wrapper for structural_check from association_lifecycle.py.

    Args:
        graph_ttl_path: Path to TTL graph file

    Returns:
        Tuple of (conforms: bool, errors: list[str])
    """
    try:
        from rdflib import Graph

        g = Graph()
        g.parse(graph_ttl_path, format="turtle")
        errors = structural_check(g)
        return (not errors, errors)
    except Exception as e:
        return (False, [str(e)])

