from __future__ import annotations

from .models import FairAcousticPackage, FairAssessmentResult, FairDimensionResult, FairStatus


def _dimension(checks: dict[str, bool]) -> FairDimensionResult:
    total = len(checks)
    passed_count = sum(bool(value) for value in checks.values())
    return FairDimensionResult(
        passed=all(checks.values()),
        checks=checks,
        score=passed_count / total if total else 0.0,
        reasons=[name for name, passed in checks.items() if not passed],
    )


def assess_fair(package: FairAcousticPackage) -> FairAssessmentResult:
    measurement_exists = package.measurement_reference in package.assets
    metadata_exists = package.metadata_reference in package.assets or bool(package.metadata_reference)

    findable = _dimension({
        "persistent_identifier": bool(package.identifier),
        "searchable_metadata": bool(package.metadata),
        "ifc_global_id": bool(package.ifc_global_id),
    })

    accessible = _dimension({
        "dataset_uri": bool(package.dataset_uri),
        "measurement_exists": measurement_exists,
        "metadata_accessible": metadata_exists,
    })

    interoperable = _dimension({
        "ifc_linked": bool(package.geometry_reference and package.ifc_global_id),
        "rdf_linked": package.metadata_reference.endswith((".ttl", ".rdf", ".jsonld")),
        "standard_representations": package.geometry_reference.endswith(".ifc") and measurement_exists,
    })

    reusable = _dimension({
        "provenance": bool(package.provenance),
        "version": bool(package.version),
        "quality_information": bool(package.quality_information),
        "reuse_license": bool(package.license),
        "measurement_context": bool(package.measurement_context),
    })

    blocking_states: list[str] = []
    if not findable.passed:
        blocking_states.append(FairStatus.NOT_FINDABLE.value)
    if not accessible.passed:
        blocking_states.append(FairStatus.NOT_ACCESSIBLE.value)
    if not interoperable.passed:
        blocking_states.append(FairStatus.NOT_INTEROPERABLE.value)
    if not reusable.passed:
        blocking_states.append(FairStatus.NOT_REUSABLE.value)

    if not blocking_states:
        status = FairStatus.FAIR_READY
    elif findable.score == 0:
        status = FairStatus.NOT_FINDABLE
    elif accessible.score == 0:
        status = FairStatus.NOT_ACCESSIBLE
    elif interoperable.score == 0:
        status = FairStatus.NOT_INTEROPERABLE
    elif reusable.score == 0:
        status = FairStatus.NOT_REUSABLE
    else:
        status = FairStatus.PARTIALLY_FAIR

    return FairAssessmentResult(
        findable=findable,
        accessible=accessible,
        interoperable=interoperable,
        reusable=reusable,
        fair_status=status,
        blocking_states=blocking_states,
    )


def apply_assessment(package: FairAcousticPackage) -> FairAssessmentResult:
    result = assess_fair(package)
    package.fair_status = result.fair_status
    package.findable = result.findable.passed
    package.accessible = result.accessible.passed
    package.interoperable = result.interoperable.passed
    package.reusable = result.reusable.passed
    return result
