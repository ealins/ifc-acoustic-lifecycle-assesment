"""
GeoBIM Semantic Lifecycle Engine

Core research prototype for IFC-external performance-record association lifecycle governance.
Implements assessment and change detection for acoustic domain.
"""

__version__ = "1.0.0"
__author__ = "Thesis Research - GeoBIM Lab"

from .assessment import (
    IFCEvidence,
    RecordEvidence,
    AssessmentResult,
    SemanticStatus,
    TechnicalResolutionStatus,
    assess_association,
    batch_assess,
)
from .change_detector import (
    ChangeEvent,
    ChangeReport,
    ChangeCategory,
    detect_changes,
)
from .ifc_extractor import (
    extract_walls_from_ifc,
    sample_walls_from_ifc,
)

__all__ = [
    "IFCEvidence",
    "RecordEvidence",
    "AssessmentResult",
    "SemanticStatus",
    "TechnicalResolutionStatus",
    "assess_association",
    "batch_assess",
    "ChangeEvent",
    "ChangeReport",
    "ChangeCategory",
    "detect_changes",
    "extract_walls_from_ifc",
    "sample_walls_from_ifc",
]
