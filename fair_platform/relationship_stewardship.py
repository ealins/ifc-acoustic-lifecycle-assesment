from __future__ import annotations

from .export import finalize_package
from .models import FairAcousticPackage, utc_now
from .stewardship import FairStewardshipService, StewardshipOutcome
from .triggers import capture_reassessment_triggers


LIFECYCLE_STATE_DEFINITIONS = {
    "ACCEPTABLE": "Current evidence supports the declared relationship and no material source change requires reassessment.",
    "SEMANTICALLY_STALE": "The reference may still resolve, but source changes weaken the original rationale or require reassessment.",
    "BROKEN": "A required packaged asset or required external resource is unavailable or corrupted.",
    "AMBIGUOUS": "Evidence is incomplete or contradictory and no defensible automated decision can be made.",
    "MULTIPLE_CANDIDATES": "More than one candidate satisfies minimum matching criteria and additional evidence/review is required.",
    "UNMATCHED": "No candidate measurement record satisfies minimum relationship criteria.",
    "INVALID": "Available evidence directly contradicts the declared relationship.",
    "MANUAL_REVIEW": "The issue depends on domain expertise or evidence that cannot be assessed automatically.",
}


class RelationshipStewardshipService:
    """Adds relationship trigger/review evidence around the preserved lifecycle engines.

    The existing FairStewardshipService and its underlying lifecycle engines remain
    authoritative for the lifecycle decision. This adapter records which qualified
    relationship was reviewed and why reassessment was triggered.
    """

    def assess(self, package: FairAcousticPackage) -> StewardshipOutcome:
        triggers = capture_reassessment_triggers(package)
        outcome = FairStewardshipService().assess(package)
        if package.relationships:
            relationship = package.relationships[0]
            relationship.setdefault("trigger_history", [])
            relationship["trigger_history"].extend(item.to_dict() for item in triggers)
            relationship.setdefault("decision_history", [])
            relationship["decision_history"].append({
                "decision_at": utc_now(),
                "lifecycle_status": outcome.engine_status,
                "display_status": outcome.status,
                "mapping_series_uri": outcome.mapping_series_uri,
                "mapping_assertion_uri": outcome.assertion_uri,
                "created_immutable_revision": outcome.created_revision,
                "trigger_ids": [item.trigger_id for item in triggers],
                "decision_source": "existing lifecycle engine via RelationshipStewardshipService adapter",
            })
            relationship["status"] = outcome.engine_status
            relationship["last_reviewed_at"] = utc_now()
        finalize_package(package)
        return outcome
