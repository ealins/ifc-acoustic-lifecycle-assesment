from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .metadata_profile import PROFILE_FIELDS, PROFILE_ID, PROFILE_VERSION, MetadataFieldDefinition, RequirementLevel
from .models import FairAcousticPackage, utc_now
from .research_object import MeasurementOrigin, RelationshipType


class MetadataFieldStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class MetadataCompletenessStatus(str, Enum):
    COMPLETE_FOR_PROTOTYPE = "COMPLETE_FOR_PROTOTYPE"
    PARTIALLY_COMPLETE = "PARTIALLY_COMPLETE"
    INSUFFICIENT_FOR_INTERPRETATION = "INSUFFICIENT_FOR_INTERPRETATION"
    INSUFFICIENT_FOR_REUSE = "INSUFFICIENT_FOR_REUSE"
    VALIDATION_INCOMPLETE = "VALIDATION_INCOMPLETE"


@dataclass
class MetadataFieldAssessment:
    field_name: str
    label: str
    category: str
    requirement_level: str
    applicable: bool
    status: MetadataFieldStatus
    value: Any
    source: str
    acquisition: str
    validation_rule: str
    recommendation: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class MetadataCompletenessAssessment:
    package_id: str
    fields: list[MetadataFieldAssessment]
    profile_id: str = PROFILE_ID
    profile_version: str = PROFILE_VERSION
    assessment_id: str = field(default_factory=lambda: f"MCA-{uuid4().hex[:10].upper()}")
    assessed_at: str = field(default_factory=utc_now)
    limitations: list[str] = field(default_factory=lambda: [
        "Metadata completeness is not FAIR certification.",
        "Metadata completeness is not evidence that acoustic values are scientifically valid or suitable for a new design case.",
        "NOT_VERIFIED means the metadata value or external condition was recorded but not independently verified by this prototype.",
        "A local package identifier can satisfy prototype identity while the FAIR-support evaluator separately distinguishes it from a registered/resolvable persistent identifier.",
    ])

    @property
    def active_required(self) -> list[MetadataFieldAssessment]:
        return [
            item for item in self.fields
            if item.applicable and item.requirement_level in {
                RequirementLevel.PROTOTYPE_REQUIRED.value,
                RequirementLevel.CONDITIONALLY_REQUIRED.value,
            }
        ]

    @property
    def overall(self) -> MetadataCompletenessStatus:
        required_failures = [
            item for item in self.active_required
            if item.status in {MetadataFieldStatus.MISSING, MetadataFieldStatus.INVALID}
        ]
        definitions = {definition.field_name: definition for definition in PROFILE_FIELDS}
        if any(definitions[item.field_name].interpretation_critical for item in required_failures if item.field_name in definitions):
            return MetadataCompletenessStatus.INSUFFICIENT_FOR_INTERPRETATION
        if any(definitions[item.field_name].reuse_critical for item in required_failures if item.field_name in definitions):
            return MetadataCompletenessStatus.INSUFFICIENT_FOR_REUSE
        if required_failures:
            return MetadataCompletenessStatus.PARTIALLY_COMPLETE
        if any(item.status == MetadataFieldStatus.MANUAL_REVIEW for item in self.active_required):
            return MetadataCompletenessStatus.VALIDATION_INCOMPLETE
        if any(item.status == MetadataFieldStatus.NOT_VERIFIED for item in self.active_required):
            return MetadataCompletenessStatus.VALIDATION_INCOMPLETE
        recommended = [item for item in self.fields if item.applicable and item.requirement_level == RequirementLevel.RECOMMENDED.value]
        if any(item.status in {MetadataFieldStatus.MISSING, MetadataFieldStatus.INVALID, MetadataFieldStatus.NOT_VERIFIED} for item in recommended):
            return MetadataCompletenessStatus.PARTIALLY_COMPLETE
        return MetadataCompletenessStatus.COMPLETE_FOR_PROTOTYPE

    def summary(self) -> dict[str, int]:
        active = [item for item in self.fields if item.applicable]
        required = self.active_required
        recommended = [item for item in active if item.requirement_level == RequirementLevel.RECOMMENDED.value]
        return {
            "metadata_fields_completed": sum(item.status == MetadataFieldStatus.PRESENT for item in active),
            "required_fields_total": len(required),
            "required_fields_satisfied": sum(item.status == MetadataFieldStatus.PRESENT for item in required),
            "conditional_fields_active": sum(item.requirement_level == RequirementLevel.CONDITIONALLY_REQUIRED.value for item in required),
            "recommended_fields_total": len(recommended),
            "recommended_fields_present": sum(item.status == MetadataFieldStatus.PRESENT for item in recommended),
            "invalid_values": sum(item.status == MetadataFieldStatus.INVALID for item in active),
            "unverified_values": sum(item.status == MetadataFieldStatus.NOT_VERIFIED for item in active),
            "manual_review_fields": sum(item.status == MetadataFieldStatus.MANUAL_REVIEW for item in active),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "package_id": self.package_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "assessed_at": self.assessed_at,
            "overall": self.overall.value,
            "summary": self.summary(),
            "fields": [item.to_dict() for item in self.fields],
            "limitations": self.limitations,
        }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _uri(value: Any) -> bool:
    if not _present(value):
        return False
    parsed = urlparse(str(value).strip())
    return parsed.scheme in {"http", "https", "urn", "doi"}


def _asset_record_for_measurement(package: FairAcousticPackage) -> dict[str, Any]:
    return next(
        (
            item for item in package.asset_records
            if item.get("path") == package.measurement_reference
            or item.get("role") == "primary-acoustic-dataset"
        ),
        {},
    )


def _resolve(package: FairAcousticPackage, path: str) -> Any:
    # Prototype identity and PID persistence are deliberately separate concerns.
    if path == "identifier":
        return package.identifier or package.package_id
    if path == "checksums.__measurement__":
        return package.checksums.get(package.measurement_reference)
    if path == "asset_records.__measurement__.size_bytes":
        return _asset_record_for_measurement(package).get("size_bytes")
    current: Any = package
    for token in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(token)
            continue
        if isinstance(current, (list, tuple)):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return None
            continue
        current = getattr(current, token, None)
    return current


def _origin(package: FairAcousticPackage) -> str:
    return str(
        package.measurement_context.get("origin_classification")
        or (package.metadata.get("measurement_inspection") or {}).get("origin_classification")
        or MeasurementOrigin.UNKNOWN_ORIGIN.value
    )


def _condition_applies(code: str, package: FairAcousticPackage) -> bool:
    if not code:
        return True
    origin = _origin(package)
    measurement_origins = {MeasurementOrigin.RAW_MEASUREMENT.value, MeasurementOrigin.PROCESSED_MEASUREMENT.value}
    if code == "measurement_origin":
        return origin in measurement_origins
    if code == "processed_or_derived":
        return origin in {MeasurementOrigin.PROCESSED_MEASUREMENT.value, MeasurementOrigin.DERIVED_RESULT.value}
    if code == "derived_origin":
        return origin == MeasurementOrigin.DERIVED_RESULT.value
    if code == "simulation_origin":
        return origin in {MeasurementOrigin.SIMULATION_RESULT.value, MeasurementOrigin.PREDICTED_VALUE.value}
    if code == "manufacturer_origin":
        return origin == MeasurementOrigin.MANUFACTURER_VALUE.value
    if code == "external_dataset":
        return bool(package.dataset_uri) or not bool(package.assets.get(package.measurement_reference))
    if code == "numeric_quantity":
        return _present(package.measurement_context.get("measured_quantity"))
    if code == "frequency_dependent":
        text = " ".join(
            str(value or "") for value in (
                package.measurement_context.get("measurement_type"),
                package.measurement_context.get("measured_quantity"),
                package.measurement_context.get("data_structure"),
            )
        ).lower()
        return any(term in text for term in ("frequency", "spectrum", "octave", "transfer", "impedance", "response"))
    if code == "restricted_access":
        return str(package.access_context.get("access_rights") or "").lower() in {"restricted", "access-controlled", "controlled"}
    if code == "embargoed_access":
        return str(package.access_context.get("access_rights") or "").lower() == "embargoed"
    if code == "access_checked":
        status = str(package.access_context.get("external_uri_status") or "").upper()
        return status in {"REACHABLE", "UNREACHABLE", "ACCESS_CONTROLLED"}
    return True


def _status_for(field_def: MetadataFieldDefinition, value: Any, package: FairAcousticPackage) -> tuple[MetadataFieldStatus, str]:
    if not _condition_applies(field_def.condition_code, package):
        return MetadataFieldStatus.NOT_APPLICABLE, "Conditional requirement is not active for the declared dataset/access context."
    if not _present(value):
        return MetadataFieldStatus.MISSING, "No value is recorded."

    if field_def.field_name in {"dataset_external_uri", "access_url", "landing_page"} and not _uri(value):
        return MetadataFieldStatus.INVALID, "Recorded value is not a syntactically valid supported URI."
    if field_def.field_name == "metadata_profile_version" and str(value) != PROFILE_VERSION:
        return MetadataFieldStatus.INVALID, f"Package records profile version {value!r}; active prototype profile is {PROFILE_VERSION!r}."
    if field_def.field_name == "dataset_origin":
        allowed = {item.value for item in MeasurementOrigin}
        if str(value) not in allowed or str(value) in {MeasurementOrigin.UNKNOWN_ORIGIN.value, "unknown"}:
            return MetadataFieldStatus.INVALID, "Dataset origin is missing/unknown or outside the controlled vocabulary."
    if field_def.field_name == "relationship_type":
        allowed = {item.value for item in RelationshipType}
        if str(value) not in allowed or str(value) == RelationshipType.UNKNOWN.value:
            return MetadataFieldStatus.INVALID, "Relationship type is missing/unknown or outside the controlled vocabulary."
        origin = _origin(package)
        if str(value) == RelationshipType.MEASURED_ON.value and origin not in {
            MeasurementOrigin.RAW_MEASUREMENT.value,
            MeasurementOrigin.PROCESSED_MEASUREMENT.value,
        }:
            return MetadataFieldStatus.INVALID, "MEASURED_ON is reserved for measurement-origin datasets; use a weaker/appropriate relationship type for catalog, reference, manufacturer, prediction, or simulation data."
    if field_def.field_name == "access_status":
        status = str(value).upper()
        if status in {"NOT_TESTED", "UNKNOWN", "NOT_VERIFIED"}:
            return MetadataFieldStatus.NOT_VERIFIED, "External URI/access status is recorded but was not verified."
        if status not in {"REACHABLE", "UNREACHABLE", "ACCESS_CONTROLLED"}:
            return MetadataFieldStatus.INVALID, "Access status is outside the controlled prototype values."
    if field_def.field_name == "domain_review_status" and str(value).upper() in {"UNKNOWN", "NOT_REVIEWED", "PENDING"}:
        return MetadataFieldStatus.MANUAL_REVIEW, "No completed acoustic-domain expert review is recorded."
    return MetadataFieldStatus.PRESENT, "Value is present and passed the prototype field-level check."


def assess_metadata_completeness(package: FairAcousticPackage) -> MetadataCompletenessAssessment:
    field_results: list[MetadataFieldAssessment] = []
    for definition in PROFILE_FIELDS:
        applicable = _condition_applies(definition.condition_code, package)
        value = _resolve(package, definition.path)
        status, note = _status_for(definition, value, package)
        recommendation = ""
        if status == MetadataFieldStatus.MISSING:
            recommendation = f"Provide {definition.label.lower()} when the profile requirement applies."
        elif status == MetadataFieldStatus.INVALID:
            recommendation = f"Correct {definition.label.lower()} according to: {definition.validation_rule}"
        elif status == MetadataFieldStatus.NOT_VERIFIED:
            recommendation = "Record explicit verification evidence/timestamp or keep the field visibly NOT_VERIFIED."
        elif status == MetadataFieldStatus.MANUAL_REVIEW:
            recommendation = "Complete and record an actual expert/manual review if this evidence is needed."
        field_results.append(
            MetadataFieldAssessment(
                field_name=definition.field_name,
                label=definition.label,
                category=definition.category.value,
                requirement_level=definition.requirement_level.value,
                applicable=applicable,
                status=status,
                value=value,
                source=definition.source_of_value,
                acquisition=definition.acquisition,
                validation_rule=definition.validation_rule,
                recommendation=recommendation,
                note=note,
            )
        )
    return MetadataCompletenessAssessment(package.package_id, field_results)


def apply_metadata_completeness(package: FairAcousticPackage) -> MetadataCompletenessAssessment:
    assessment = assess_metadata_completeness(package)
    package.metadata_completeness_status = assessment.overall.value
    package.metadata_completeness_assessment = assessment.to_dict()
    return assessment
