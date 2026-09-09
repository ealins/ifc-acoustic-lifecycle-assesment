from __future__ import annotations

from .fair_support import FairCriterionStatus, FairSupportOverall, assess_fair_support
from .models import FairAcousticPackage


BLOCKING_PRIORITIES = {"prototype required"}
READINESS_PRIORITIES = {"prototype required", "conditionally required", "recommended"}


def _criterion(criteria, criterion_id: str):
    return next((item for item in criteria if item.criterion_id == criterion_id), None)


def normalize_criterion_evidence(package: FairAcousticPackage, criteria) -> None:
    """Apply profile policy where legacy evaluator assumptions were intentionally stricter/different."""
    # A generated local package ID is valid local identity, but it is not a DOI or
    # proof of globally resolvable persistence. F2 retains that distinction.
    f1 = _criterion(criteria, "F1")
    if f1 and package.package_id:
        f1.status = FairCriterionStatus.PASS
        f1.evidence = f"Local research-object identifier: {package.package_id}"
        f1.evidence_source = "package_id"
        f1.recommendation = "For publication, additionally provide a repository-issued persistent identifier if available."

    # Descriptive title must be explicitly supplied; display fallbacks are not
    # allowed to make descriptive metadata appear complete.
    f3 = _criterion(criteria, "F3")
    explicit_title = str(package.metadata.get("title") or "").strip()
    if f3:
        f3.status = FairCriterionStatus.PASS if explicit_title and package.package_id else FairCriterionStatus.FAIL
        f3.evidence = f"explicit_title={explicit_title or 'missing'}; local_id={package.package_id or 'missing'}"
        f3.evidence_source = "metadata.title + package_id"
        if not explicit_title:
            f3.recommendation = "Add a descriptive research-object title; the UI/package-ID fallback is not descriptive metadata."

    # The manual scientific/domain sufficiency reminder is visible but optional;
    # it cannot prevent metadata/package readiness because scientific suitability
    # is explicitly assessed on a separate axis.
    r13 = _criterion(criteria, "R13")
    if r13:
        r13.priority = "optional"


def determine_overall(criteria) -> FairSupportOverall:
    """Map transparent criterion states to a non-certifying prototype-readiness label."""
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
    normalize_criterion_evidence(package, result.criteria)
    overall = determine_overall(result.criteria)
    payload = result.to_dict()
    payload["overall"] = overall.value
    payload["policy_note"] = (
        "Overall status is a prototype reuse-readiness label, not FAIR certification. "
        "Optional manual-review criteria remain visible without implying acoustic scientific suitability."
    )
    package.fair_support_status = overall.value
    package.fair_support_assessment = payload
    return result
