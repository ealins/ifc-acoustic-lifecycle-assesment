from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from rdflib import Graph

from .models import FairAcousticPackage, utc_now
from .research_object import MeasurementOrigin


ASSESSMENT_PROFILE = "Prototype Acoustic Component FAIR-Support Profile"
ASSESSMENT_PROFILE_VERSION = "0.1"


class FairCriterionStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class FairSupportOverall(str, Enum):
    READY_FOR_PROTOTYPE_REUSE = "READY_FOR_PROTOTYPE_REUSE"
    PARTIALLY_READY = "PARTIALLY_READY"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"
    ASSESSMENT_INCOMPLETE = "ASSESSMENT_INCOMPLETE"


@dataclass
class FairSupportCriterionResult:
    criterion_id: str
    fair_dimension: str
    label: str
    requirement: str
    priority: str
    status: FairCriterionStatus
    evidence: str
    evidence_source: str
    missing_information: str = ""
    recommendation: str = ""
    assessment_method: str = "automated metadata check"
    machine_checkable: bool = True
    manual_review_required: bool = False

    @property
    def passed(self) -> bool:
        return self.status == FairCriterionStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["passed"] = self.passed
        return data


@dataclass
class FairSupportAssessment:
    assessed_package_id: str
    criteria: list[FairSupportCriterionResult]
    assessor: str = "prototype automated evaluator"
    assessment_profile: str = ASSESSMENT_PROFILE
    profile_version: str = ASSESSMENT_PROFILE_VERSION
    assessment_date: str = field(default_factory=utc_now)
    assessment_id: str = field(default_factory=lambda: f"FSA-{uuid4().hex[:10].upper()}")
    limitations: list[str] = field(default_factory=lambda: [
        "This is a bounded prototype FAIR-support assessment, not a FAIR certification.",
        "URI reachability is only reported when an explicit access check result is supplied.",
        "Metadata completeness is not evidence of acoustic scientific validity or suitability.",
    ])

    @property
    def dimensions(self) -> dict[str, list[FairSupportCriterionResult]]:
        result: dict[str, list[FairSupportCriterionResult]] = {}
        for item in self.criteria:
            result.setdefault(item.fair_dimension, []).append(item)
        return result

    @property
    def overall(self) -> FairSupportOverall:
        required = [item for item in self.criteria if item.priority == "prototype required"]
        if any(item.status == FairCriterionStatus.FAIL for item in required):
            return FairSupportOverall.INSUFFICIENT_METADATA
        if any(item.status in {FairCriterionStatus.NOT_VERIFIED, FairCriterionStatus.MANUAL_REVIEW} for item in required):
            return FairSupportOverall.ASSESSMENT_INCOMPLETE
        if any(item.status in {FairCriterionStatus.PARTIAL, FairCriterionStatus.FAIL} for item in self.criteria):
            return FairSupportOverall.PARTIALLY_READY
        if any(item.status in {FairCriterionStatus.NOT_VERIFIED, FairCriterionStatus.MANUAL_REVIEW} for item in self.criteria):
            return FairSupportOverall.PARTIALLY_READY
        return FairSupportOverall.READY_FOR_PROTOTYPE_REUSE

    def dimension_score(self, name: str) -> float:
        items = [item for item in self.criteria if item.fair_dimension == name and item.status != FairCriterionStatus.NOT_APPLICABLE]
        if not items:
            return 0.0
        values = {
            FairCriterionStatus.PASS: 1.0,
            FairCriterionStatus.PARTIAL: 0.5,
            FairCriterionStatus.NOT_VERIFIED: 0.25,
            FairCriterionStatus.MANUAL_REVIEW: 0.25,
            FairCriterionStatus.FAIL: 0.0,
        }
        return round(sum(values.get(item.status, 0.0) for item in items) / len(items), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "assessed_package_id": self.assessed_package_id,
            "assessment_profile": self.assessment_profile,
            "profile_version": self.profile_version,
            "assessment_date": self.assessment_date,
            "assessor": self.assessor,
            "overall": self.overall.value,
            "dimensions": {
                name: {
                    "score": self.dimension_score(name),
                    "criteria": [item.to_dict() for item in items],
                }
                for name, items in self.dimensions.items()
            },
            "criteria": [item.to_dict() for item in self.criteria],
            "limitations": self.limitations,
        }


def _text(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return bool(str(value).strip())


def _uri_syntax(value: str | None) -> bool:
    if not _text(value):
        return False
    parsed = urlparse(str(value).strip())
    return parsed.scheme in {"http", "https", "urn", "doi"}


def _pid_kind(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "missing"
    if text.startswith("doi:") or "doi.org/" in text:
        return "DOI"
    if "example.org" in text:
        return "prototype URI"
    if text.startswith("urn:uuid:"):
        return "local/global UUID URN"
    if text.startswith("urn:"):
        return "URN"
    if text.startswith(("http://", "https://")):
        return "HTTP(S) identifier"
    return "local identifier"


def _jsonld_parseable(package: FairAcousticPackage) -> bool:
    payload = package.assets.get("ro-crate-metadata.json")
    if not payload:
        return False
    try:
        data = json.loads(payload.decode("utf-8"))
        return isinstance(data, dict) and "@context" in data and "@graph" in data
    except Exception:
        return False


def _turtle_parseable(package: FairAcousticPackage) -> bool:
    payload = package.assets.get(package.metadata_reference)
    if not payload:
        return False
    try:
        Graph().parse(data=payload.decode("utf-8"), format="turtle")
        return True
    except Exception:
        return False


def _criterion(
    cid: str,
    dimension: str,
    label: str,
    requirement: str,
    status: FairCriterionStatus,
    evidence: str,
    source: str,
    *,
    priority: str = "prototype required",
    missing: str = "",
    recommendation: str = "",
    method: str = "automated metadata check",
    machine: bool = True,
    manual: bool = False,
) -> FairSupportCriterionResult:
    return FairSupportCriterionResult(
        cid, dimension, label, requirement, priority, status, evidence, source,
        missing, recommendation, method, machine, manual,
    )


def assess_fair_support(package: FairAcousticPackage) -> FairSupportAssessment:
    criteria: list[FairSupportCriterionResult] = []
    relationship = package.relationships[0] if package.relationships else {}
    inspection = package.metadata.get("measurement_inspection") or {}
    origin = str(inspection.get("origin_classification") or package.measurement_context.get("origin_classification") or MeasurementOrigin.UNKNOWN.value)
    asset_paths = set(package.assets)
    pid_kind = _pid_kind(package.identifier)

    # FINDABLE
    criteria.extend([
        _criterion("F1", "Findable", "Package identifier", "The research object has a unique explicit identifier.", FairCriterionStatus.PASS if _text(package.identifier) else FairCriterionStatus.FAIL, f"{pid_kind}: {package.identifier or 'missing'}", "domain model: identifier", recommendation="Provide an explicit package identifier."),
        _criterion("F2", "Findable", "Identifier persistence is distinguished", "The implementation must distinguish prototype/local identifiers from registered persistent identifiers.", FairCriterionStatus.PASS if pid_kind in {"DOI", "URN", "HTTP(S) identifier"} else FairCriterionStatus.PARTIAL if _text(package.identifier) else FairCriterionStatus.FAIL, pid_kind, "identifier classification", priority="recommended", recommendation="Use a repository-issued PID for published research objects; this prototype does not mint DOIs."),
        _criterion("F3", "Findable", "Package metadata identify the object", "Title and package identifier are explicit.", FairCriterionStatus.PASS if _text(package.title) and _text(package.identifier) else FairCriterionStatus.FAIL, f"title={package.title!r}; identifier={package.identifier!r}", "domain model"),
        _criterion("F4", "Findable", "Measurement dataset identifier", "The primary acoustic dataset is explicitly identified.", FairCriterionStatus.PASS if _text(package.metadata.get("measurement_identifier")) else FairCriterionStatus.FAIL, str(package.metadata.get("measurement_identifier") or "missing"), "metadata.measurement_identifier", recommendation="Provide a measurement dataset identifier distinct from the package identifier."),
        _criterion("F5", "Findable", "Selected IFC component identity", "The selected IFC component is identified by GlobalId where applicable.", FairCriterionStatus.PASS if _text(package.ifc_global_id) else FairCriterionStatus.FAIL, package.ifc_global_id or "missing", "ifc_global_id"),
        _criterion("F6", "Findable", "Assets indexed", "Packaged assets are enumerated by the research-object metadata/manifest.", FairCriterionStatus.PASS if package.asset_records or asset_paths else FairCriterionStatus.FAIL, f"{len(asset_paths)} packaged path(s)", "assets + manifest"),
        _criterion("F7", "Findable", "Local catalog identity", "The object has a package ID usable by the prototype catalog.", FairCriterionStatus.PASS if _text(package.package_id) else FairCriterionStatus.FAIL, package.package_id or "missing", "package_id"),
        _criterion("F8", "Findable", "Version", "The research object version is explicit.", FairCriterionStatus.PASS if _text(package.version) else FairCriterionStatus.FAIL, package.version or "missing", "version"),
        _criterion("F9", "Findable", "Descriptive metadata", "Title plus description or keywords support catalog discovery.", FairCriterionStatus.PASS if _text(package.title) and (_text(package.metadata.get("description")) or _text(package.metadata.get("keywords"))) else FairCriterionStatus.PARTIAL, "title/description/keywords reviewed", "metadata", priority="recommended", recommendation="Add a concise description and keywords for human and catalog discovery."),
    ])

    # ACCESSIBLE
    packaged_primary = bool(package.assets.get(package.geometry_reference)) and bool(package.assets.get(package.measurement_reference))
    uri_present = _text(package.dataset_uri)
    uri_valid = _uri_syntax(package.dataset_uri)
    access_status = str(package.access_context.get("external_uri_status") or "NOT_TESTED").upper()
    if not uri_present:
        reachability_status = FairCriterionStatus.NOT_APPLICABLE
        reachability_evidence = "No external measurement URI declared; primary asset is packaged."
    elif access_status in {"REACHABLE", "PASS", "AVAILABLE"}:
        reachability_status = FairCriterionStatus.PASS
        reachability_evidence = access_status
    elif access_status in {"UNREACHABLE", "FAILED", "BROKEN"}:
        reachability_status = FairCriterionStatus.FAIL
        reachability_evidence = access_status
    else:
        reachability_status = FairCriterionStatus.NOT_VERIFIED
        reachability_evidence = "URI present but reachability was not tested."
    criteria.extend([
        _criterion("A1", "Accessible", "Packaged primary assets retrievable", "IFC and primary acoustic data are retrievable from the archive when packaged.", FairCriterionStatus.PASS if packaged_primary else FairCriterionStatus.FAIL, f"geometry={package.geometry_reference in asset_paths}; measurement={package.measurement_reference in asset_paths}", "assets"),
        _criterion("A2", "Accessible", "External URI syntax", "External asset references use an explicit syntactically valid URI.", FairCriterionStatus.PASS if uri_valid else FairCriterionStatus.NOT_APPLICABLE if not uri_present else FairCriterionStatus.FAIL, package.dataset_uri or "not applicable", "dataset_uri", priority="conditionally required"),
        _criterion("A3", "Accessible", "External URI reachability", "Reachability is reported as verified, failed, or not tested rather than inferred from URI presence.", reachability_status, reachability_evidence, "access_context.external_uri_status", priority="conditionally required", recommendation="Record a timestamped access check when evaluating an external resource."),
        _criterion("A4", "Accessible", "Access rights", "Access/reuse conditions are documented.", FairCriterionStatus.PASS if _text(package.access_context.get("access_rights")) else FairCriterionStatus.PARTIAL if _text(package.license) else FairCriterionStatus.FAIL, str(package.access_context.get("access_rights") or package.license or "missing"), "access_context/license", recommendation="Document whether assets are open, restricted, embargoed, metadata-only, or require authentication."),
        _criterion("A5", "Accessible", "Metadata retained in package", "Portable metadata remain available with the research object.", FairCriterionStatus.PASS if "ro-crate-metadata.json" in asset_paths and package.metadata_reference in asset_paths else FairCriterionStatus.FAIL, f"ro-crate={'ro-crate-metadata.json' in asset_paths}; turtle={package.metadata_reference in asset_paths}", "assets"),
        _criterion("A6", "Accessible", "Access method explicit", "The package states whether data are packaged and/or externally referenced.", FairCriterionStatus.PASS if packaged_primary or uri_present else FairCriterionStatus.FAIL, "packaged" if packaged_primary else package.dataset_uri or "missing", "assets/dataset_uri"),
    ])

    # INTEROPERABLE
    schema = package.metadata.get("geometry_ifc_schema")
    media_type = package.metadata.get("measurement_media_type")
    units = package.measurement_context.get("unit") or package.measurement_context.get("units")
    measured_quantity = package.measurement_context.get("measured_quantity") or package.measurement_context.get("measurement_type")
    criteria.extend([
        _criterion("I1", "Interoperable", "IFC format and schema declared", "IFC is explicit and schema/version is recorded when extractable.", FairCriterionStatus.PASS if package.geometry_reference.lower().endswith(".ifc") and _text(schema) else FairCriterionStatus.PARTIAL if package.geometry_reference.lower().endswith(".ifc") else FairCriterionStatus.FAIL, f"format=IFC; schema={schema or 'not extracted'}", "geometry metadata", recommendation="Persist the actual IFC schema identifier extracted from the model."),
        _criterion("I2", "Interoperable", "Measurement media type and structure", "The acoustic data media type and inspected structure are declared.", FairCriterionStatus.PASS if _text(media_type) and _text(inspection.get("format")) else FairCriterionStatus.PARTIAL, f"media={media_type}; format={inspection.get('format')}", "measurement inspection"),
        _criterion("I3", "Interoperable", "RO-Crate JSON-LD parseable", "Portable package metadata are JSON-LD/RO-Crate style and parse structurally.", FairCriterionStatus.PASS if _jsonld_parseable(package) else FairCriterionStatus.FAIL, "ro-crate-metadata.json", "package asset"),
        _criterion("I4", "Interoperable", "Domain RDF/Turtle parseable", "Domain relationship/provenance metadata are machine-readable RDF.", FairCriterionStatus.PASS if _turtle_parseable(package) else FairCriterionStatus.FAIL, package.metadata_reference, "package asset"),
        _criterion("I5", "Interoperable", "Explicit qualified relationship", "Component and acoustic dataset are connected through an identified qualified relationship entity.", FairCriterionStatus.PASS if relationship.get("relationship_id") and relationship.get("relationship_type") else FairCriterionStatus.FAIL, str(relationship.get("relationship_id") or "missing"), "relationships", recommendation="Create a GeometryMeasurementRelationship with type, rationale, evidence, and source versions."),
        _criterion("I6", "Interoperable", "Units documented where relevant", "Units are recorded for numeric acoustic quantities where applicable.", FairCriterionStatus.PASS if _text(units) else FairCriterionStatus.PARTIAL if not _text(measured_quantity) else FairCriterionStatus.FAIL, str(units or "missing/unknown"), "measurement_context", priority="conditionally required", recommendation="Record units for reported acoustic quantities; do not infer units from a label alone."),
        _criterion("I7", "Interoperable", "Vocabularies/profile declared", "Established vocabularies and the prototype profile are declared without presenting custom terms as standards.", FairCriterionStatus.PASS if _text(package.research_object_profile) else FairCriterionStatus.FAIL, package.research_object_profile or "missing", "research_object_profile"),
        _criterion("I8", "Interoperable", "IDS/bSDD references are optional and explicit", "Optional IDS and bSDD references are represented only when actually supplied.", FairCriterionStatus.NOT_APPLICABLE if not (_text(package.metadata.get("ids_specification_reference")) or _text(package.metadata.get("bsdd_concept_uri"))) else FairCriterionStatus.MANUAL_REVIEW, "No IDS/bSDD reference supplied" if not (_text(package.metadata.get("ids_specification_reference")) or _text(package.metadata.get("bsdd_concept_uri"))) else "Reference supplied; semantic validity requires external/manual verification", "metadata", priority="optional", machine=False, manual=True),
    ])

    # REUSABLE
    method = package.measurement_context.get("measurement_method")
    instrument = package.measurement_context.get("instrument")
    quality = package.quality_information
    provenance = package.provenance
    relationship_evidence = relationship.get("evidence") or []
    rationale = relationship.get("rationale")
    intended_reuse = package.research_context.get("intended_reuse")
    citation = package.research_context.get("citation") or package.metadata.get("citation")
    origin_required_context = origin in {MeasurementOrigin.RAW_MEASUREMENT.value, MeasurementOrigin.PROCESSED_MEASUREMENT.value}
    criteria.extend([
        _criterion("R1", "Reusable", "Creator/responsible agent", "A creator or responsible agent is documented.", FairCriterionStatus.PASS if _text(package.creator) or _text(provenance.get("creator")) else FairCriterionStatus.FAIL, str(package.creator or provenance.get("creator") or "missing"), "creator/provenance"),
        _criterion("R2", "Reusable", "Provenance", "Origin/generating or derivation context is documented.", FairCriterionStatus.PASS if _text(provenance) else FairCriterionStatus.FAIL, str(provenance or "missing"), "provenance"),
        _criterion("R3", "Reusable", "Acoustic data origin classified", "The acoustic record is distinguished as raw, processed, derived, reference, manufacturer, predicted, simulation, or unknown.", FairCriterionStatus.PASS if origin != MeasurementOrigin.UNKNOWN.value else FairCriterionStatus.FAIL, origin, "measurement inspection/context", recommendation="Classify origin explicitly; structural file inspection must not invent measurement provenance."),
        _criterion("R4", "Reusable", "Method documented when applicable", "Measurement/simulation method is documented when required by the record origin.", FairCriterionStatus.PASS if _text(method) else FairCriterionStatus.FAIL if origin_required_context else FairCriterionStatus.PARTIAL, str(method or "missing"), "measurement_context", priority="conditionally required"),
        _criterion("R5", "Reusable", "Instrument context documented when applicable", "Instrument/acquisition context is documented for physical measurements where applicable.", FairCriterionStatus.PASS if _text(instrument) else FairCriterionStatus.FAIL if origin_required_context else FairCriterionStatus.NOT_APPLICABLE, str(instrument or "not supplied"), "measurement_context", priority="conditionally required"),
        _criterion("R6", "Reusable", "Versions", "Package and source versions are documented.", FairCriterionStatus.PASS if _text(package.version) and (_text(relationship.get("source_component_version")) or _text(package.metadata.get("model_version"))) and (_text(relationship.get("source_measurement_version")) or _text(package.measurement_context.get("measurement_version"))) else FairCriterionStatus.PARTIAL, f"package={package.version}; component={relationship.get('source_component_version') or package.metadata.get('model_version')}; measurement={relationship.get('source_measurement_version') or package.measurement_context.get('measurement_version')}", "domain model/relationship", recommendation="Record component and measurement source versions separately from the research-object version."),
        _criterion("R7", "Reusable", "Licence/reuse terms", "A licence or reuse statement is documented.", FairCriterionStatus.PASS if _text(package.license) else FairCriterionStatus.FAIL, package.license or "missing", "license", recommendation="Provide a licence or explicit reuse statement for the packaged research object/data."),
        _criterion("R8", "Reusable", "Quality, uncertainty, or limitations", "Available uncertainty/quality/limitation information is documented without claiming scientific validity.", FairCriterionStatus.PASS if _text(quality) or _text(package.research_context.get("limitations")) else FairCriterionStatus.PARTIAL, str(quality or package.research_context.get("limitations") or "missing"), "quality_information/research_context", priority="recommended"),
        _criterion("R9", "Reusable", "Relationship rationale", "The geometry-measurement relationship has an explicit rationale.", FairCriterionStatus.PASS if _text(rationale) else FairCriterionStatus.FAIL, str(rationale or "missing"), "qualified relationship"),
        _criterion("R10", "Reusable", "Relationship evidence", "The relationship has structured evidence items with provenance/status.", FairCriterionStatus.PASS if relationship_evidence else FairCriterionStatus.FAIL, f"{len(relationship_evidence)} evidence item(s)", "qualified relationship", recommendation="Attach at least one structured EvidenceItem; do not replace evidence with a numerical confidence score."),
        _criterion("R11", "Reusable", "Intended reuse", "Intended or permitted reuse is stated.", FairCriterionStatus.PASS if _text(intended_reuse) else FairCriterionStatus.PARTIAL, str(intended_reuse or "not stated"), "research_context", priority="recommended"),
        _criterion("R12", "Reusable", "Citation information", "A preferred citation can be produced or is supplied.", FairCriterionStatus.PASS if _text(citation) else FairCriterionStatus.PARTIAL, str(citation or "not supplied"), "research_context/metadata", priority="recommended"),
        _criterion("R13", "Reusable", "Domain metadata completeness", "Scientific/context metadata completeness is reviewed separately from scientific validity.", FairCriterionStatus.MANUAL_REVIEW, "Automated checks cannot determine domain-scientific sufficiency for every acoustic use case.", "manual review", priority="recommended", method="manual review criterion", machine=False, manual=True),
    ])

    return FairSupportAssessment(package.package_id, criteria)


def apply_fair_support_assessment(package: FairAcousticPackage) -> FairSupportAssessment:
    result = assess_fair_support(package)
    package.fair_support_status = result.overall.value
    package.fair_support_assessment = result.to_dict()
    return result
