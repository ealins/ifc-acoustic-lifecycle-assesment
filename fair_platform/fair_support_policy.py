from __future__ import annotations

from .fair_support import FairCriterionStatus, FairSupportOverall, assess_fair_support
from .models import FairAcousticPackage


BLOCKING_PRIORITIES = {"prototype required"}
READINESS_PRIORITIES = {"prototype required", "conditionally required", "recommended"}


def determine_overall(criteria) -> FairSupportOverall:
    """Map transparent criterion states to a non-certifying prototype-readiness label.

    Optional manual-review criteria remain visible in the report but do not make
    READY_FOR_PROTOTYPE_REUSE unreachable. Scientific suitability is represented
    separately and is never inferred from this result.
    """
    blocking = [item for item in criteria if item.priority in BLOCKING_PRIORITIES]
    if any(item.status == FairCriterionStatus.FAIL for item in blocking):
        return FairSupportOverall.INSUFFICIENT_METADATA
    if any(item.status in {FairCriterionStatus.NOT_VERIFIED, FairCriterionStatus.MANUAL_REVIEW} for item in blocking):
        return FairSupportOverall.ASSESSMENT_INCOMPLETE

    relevant = [
        item for item in criteria
        if item.priority in READINESS_PRIORITIES and item.status != FairCriterionStatus.NOT_APPLICABLE
    ]
    if any(item.status in {FairCriterionStatus.FAIL, FairCriterionStatus.PARTIAL} for item in relevant):
        return FairSupportOverall.PARTIALLY_READY
    if any(item.status in {FairCriterionStatus.NOT_VERIFIED, FairCriterionStatus.MANUAL_REVIEW} for item in relevant):
        return FairSupportOverall.PARTIALLY_READY
    return FairSupportOverall.READY_FOR_PROTOTYPE_REUSE


def apply_fair_support_profile(package: FairAcousticPackage):
    result = assess_fair_support(package)
    payload = result.to_dict()
    overall = determine_overall(result.criteria)
    payload["overall"] = overall.value
    payload["policy_note"] = (
        "Overall status is a prototype reuse-readiness label, not FAIR certification. "
        "Optional manual-review criteria remain visible without implying acoustic scientific suitability."
    )
    package.fair_support_status = overall.value
    package.fair_support_assessment = payload
    return result
