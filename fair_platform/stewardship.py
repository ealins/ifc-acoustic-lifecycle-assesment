from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import PROV, XSD

from .export import finalize_package
from .models import FairAcousticPackage, utc_now
from .triggers import capture_reassessment_triggers

MAP = Namespace("https://example.org/hft-acoustic/mapping/vocab/")


@dataclass
class StewardshipOutcome:
    status: str
    engine_status: str
    created_revision: bool
    mapping_series_uri: str
    assertion_uri: str | None
    result: dict


def _record_id(package: FairAcousticPackage) -> str:
    return str(package.metadata.get("measurement_identifier") or package.package_id)


def _series_uri(package: FairAcousticPackage) -> str:
    return f"https://example.org/hft-acoustic/mapping-series/{package.ifc_global_id or 'unknown'}-{_record_id(package)}"


def _generic_turtle(history: list[dict]) -> str:
    graph = Graph()
    graph.bind("map", MAP)
    graph.bind("prov", PROV)
    previous_by_series: dict[str, str] = {}
    for entry in history:
        series_uri = entry.get("mapping_series_uri")
        assertion_uri = entry.get("assertion_uri")
        if not series_uri or not assertion_uri:
            continue
        series = URIRef(series_uri)
        assertion = URIRef(assertion_uri)
        graph.add((series, RDF.type, MAP.MappingSeries))
        graph.add((series, MAP.currentAssertion, assertion))
        graph.add((assertion, RDF.type, MAP.MappingAssertion))
        graph.add((assertion, MAP.belongsToSeries, series))
        graph.add((assertion, MAP.revisionNumber, Literal(entry.get("revision", 1), datatype=XSD.integer)))
        graph.add((assertion, MAP.semanticStatus, Literal(entry.get("engine_status", entry.get("status", "")))))
        graph.add((assertion, MAP.assessedAt, Literal(entry.get("timestamp", utc_now()), datatype=XSD.dateTime)))
        previous = previous_by_series.get(series_uri)
        if previous:
            graph.add((assertion, PROV.wasRevisionOf, URIRef(previous)))
        previous_by_series[series_uri] = assertion_uri
    return graph.serialize(format="turtle")


def _restore_engine_assertion(payload: dict):
    from models import ChangeEvent, EvidenceSnapshot, MappingAssertion

    assignment = payload.get("assignment_snapshot")
    return MappingAssertion(
        revision_number=int(payload["revision_number"]),
        timestamp=payload["timestamp"],
        mapping_series_uri=payload["mapping_series_uri"],
        ifc_snapshot=EvidenceSnapshot("IFC", dict(payload.get("ifc_snapshot", {}))),
        rdf_snapshot=EvidenceSnapshot("RDF", dict(payload.get("rdf_snapshot", {}))),
        technical_link_state=payload.get("technical_link_state", ""),
        link_status=payload.get("link_status", ""),
        data_status=payload.get("data_status", ""),
        mapping_series_validity=payload.get("mapping_series_validity", ""),
        ids_status=payload.get("ids_status", ""),
        bsdd_status=payload.get("bsdd_status", ""),
        semantic_status=payload.get("semantic_status", ""),
        requires_review=bool(payload.get("requires_review")),
        rationale=payload.get("rationale", ""),
        assignment_snapshot=EvidenceSnapshot("ASSIGNMENT", dict(assignment)) if assignment else None,
        change_events=[ChangeEvent(**event) for event in payload.get("change_events", [])],
        previous_revision=payload.get("previous_revision"),
        previous_assertion_uri=payload.get("previous_assertion_uri"),
        supersedes_series_uri=payload.get("supersedes_series_uri"),
        series_transition=payload.get("series_transition", "INITIAL_SERIES"),
        validation_profile=payload.get("validation_profile", ""),
    )


def _engine_inputs(package: FairAcousticPackage) -> tuple[dict, dict, dict, dict]:
    from engine import expected_mapping_series_uri

    record_id = _record_id(package)
    materials = package.metadata.get("geometry_materials", []) or []
    ifc = {
        "GlobalId": package.ifc_global_id or "",
        "element_type": package.metadata.get("geometry_ifc_class", "IfcWall"),
        "wall_name": package.metadata.get("geometry_name", "IFC component"),
        "construction_family": package.metadata.get("geometry_construction_family", ""),
        "thickness_m": package.metadata.get("geometry_total_thickness_m"),
        "materials": " / ".join(str(item) for item in materials),
        "native_record_uri": package.dataset_uri or "",
        "pset_record_uri": package.dataset_uri or "",
        "pset_mapping_series_uri": "",
        "mapping_series_uri": "",
        "association_type": "FairAcousticPackage",
        "semantic_profile": "FAIR-Acoustic-1.0",
    }
    rdf = {
        "record_uri": package.dataset_uri or "",
        "record_id": record_id,
        "construction_family": package.measurement_context.get("construction_family", ""),
        "thickness_m": package.measurement_context.get("total_thickness_m"),
        "Rw": package.measurement_context.get("rw_db"),
        "unit": package.measurement_context.get("unit", "dB"),
        "assembly": package.measurement_context.get("assembly", ""),
        "source_organisation": package.provenance.get("institution", ""),
        "report_reference": package.measurement_context.get("report_reference", ""),
        "provenance_note": package.provenance.get("note") or package.creator or "",
        "record_available": bool(package.assets.get(package.measurement_reference)),
        "spectrum_adaptation_C": package.measurement_context.get("spectrum_adaptation_C"),
        "spectrum_adaptation_Ctr": package.measurement_context.get("spectrum_adaptation_Ctr"),
        "measurement_method": package.measurement_context.get("measurement_method", ""),
        "frequency_data": json.dumps(package.measurement_context.get("frequency_data", [])),
        "layer_data": json.dumps(package.measurement_context.get("layer_data", [])),
    }
    ifc["mapping_series_uri"] = expected_mapping_series_uri(ifc, rdf)
    ifc["pset_mapping_series_uri"] = ifc["mapping_series_uri"]
    settings = {
        "validation_profile": "FAIR_STEWARDSHIP_LEGACY_RW_V1",
        "thickness_tolerance_m": float(package.metadata.get("thickness_tolerance_m", 0.02)),
        "use_semantic_staleness": True,
        "require_mapping_series": True,
        "semantic_override_status": "",
        "semantic_override_note": "",
    }
    assignment = {
        "assignment_id": f"fair-package-{package.package_id}",
        "protocol_id": "fair-package-link-v1",
        "wall_global_id": package.ifc_global_id or "",
        "record_id": record_id,
        "record_uri": package.dataset_uri or "",
        "mapping_series_uri": ifc["mapping_series_uri"],
        "assignment_method": "explicit acoustic research-object relationship",
    }
    return ifc, rdf, settings, assignment


def _capture_profile_trigger_evidence(package: FairAcousticPackage) -> list[dict]:
    """Capture profile-level reassessment triggers before the preserved engine runs.

    Trigger records are evidence for reassessment. They do not override the lifecycle
    engine's semantic decision; the engine remains authoritative for status.
    """
    triggers = capture_reassessment_triggers(package)
    payload = [item.to_dict() for item in triggers]
    if payload and package.relationships:
        relationship = package.relationships[0]
        history = list(relationship.get("trigger_history") or [])
        history.extend(payload)
        relationship["trigger_history"] = history
        relationship["last_triggered_at"] = payload[-1]["detected_at"]
    return payload


def _stable_generic_result(payload: dict) -> dict:
    """Remove volatile run metadata from the generic stewardship fingerprint."""
    stable = dict(payload)
    stable.pop("assessment_timestamp", None)
    return stable


class FairStewardshipService:
    """Adapter that keeps the existing lifecycle engines authoritative for stewardship decisions."""

    def assess(self, package: FairAcousticPackage) -> StewardshipOutcome:
        trigger_evidence = _capture_profile_trigger_evidence(package)
        profile = str(package.measurement_context.get("stewardship_profile", "GENERIC_ACOUSTIC_MEASUREMENT"))
        outcome = self._assess_rw(package) if profile == "AIRBORNE_SOUND_INSULATION_RW" else self._assess_generic(package)
        if trigger_evidence:
            outcome.result["research_object_reassessment_triggers"] = trigger_evidence
            if package.stewardship_history:
                package.stewardship_history[-1]["research_object_reassessment_triggers"] = trigger_evidence
            finalize_package(package)
        return outcome

    def _assess_rw(self, package: FairAcousticPackage) -> StewardshipOutcome:
        from engine import build_rdf_turtle, evaluate_lifecycle

        ifc, rdf, settings, assignment = _engine_inputs(package)
        engine_history = [entry for entry in package.stewardship_history if entry.get("mode") == "legacy_rw"]
        assertions = [_restore_engine_assertion(entry["assertion"]) for entry in engine_history if entry.get("assertion")]
        previous = engine_history[-1].get("state") if engine_history else None
        assertion, payload, events = evaluate_lifecycle(ifc, rdf, settings, previous, assertions, assignment)
        engine_status = payload["semantic"]["semantic_status"]
        package.lifecycle_status = engine_status
        package.mapping_series_uri = payload["transition"]["current_series_uri"]
        created = assertion is not None
        assertion_uri = assertion.assertion_uri if assertion else (assertions[-1].assertion_uri if assertions else None)
        if assertion:
            assertions.append(assertion)
            package.stewardship_history.append({
                "mode": "legacy_rw",
                "timestamp": assertion.timestamp,
                "mapping_series_uri": assertion.mapping_series_uri,
                "assertion_uri": assertion.assertion_uri,
                "revision": assertion.revision_number,
                "status": "STALE" if engine_status == "SEMANTICALLY_STALE" else engine_status,
                "engine_status": engine_status,
                "assertion": assertion.as_dict(),
                "state": payload["state"],
                "result": payload,
                "change_events": [event.__dict__ for event in events],
            })
        package.latest_mapping_assertion_uri = assertion_uri
        package.metadata["stewardship_rdf_turtle"] = build_rdf_turtle(assertions) if assertions else ""
        finalize_package(package)
        return StewardshipOutcome(package.lifecycle_display_status, engine_status, created, package.mapping_series_uri or "", assertion_uri, payload)

    def _assess_generic(self, package: FairAcousticPackage) -> StewardshipOutcome:
        from dashboard.backend.validators import RecordEvidence, TieredValidator, WallEvidence

        record_id = _record_id(package)
        series_uri = _series_uri(package)
        wall = WallEvidence(
            global_id=package.ifc_global_id or "",
            name=package.metadata.get("geometry_name", "IFC component"),
            construction_family=package.metadata.get("geometry_construction_family", ""),
            total_thickness_m=package.metadata.get("geometry_total_thickness_m"),
            material_evidence=package.metadata.get("geometry_materials", []) or [],
            model_version=package.metadata.get("model_version", package.version),
        )
        record = RecordEvidence(
            uri=package.dataset_uri or "",
            identifier=record_id,
            assembly=package.measurement_context.get("assembly", ""),
            construction_family=package.measurement_context.get("construction_family", ""),
            total_thickness_m=package.measurement_context.get("total_thickness_m"),
            record_version=package.measurement_context.get("measurement_version") or package.version,
            available=bool(package.assets.get(package.measurement_reference)),
        )
        previous_status = package.stewardship_history[-1].get("engine_status") if package.stewardship_history else None
        result = TieredValidator(float(package.metadata.get("thickness_tolerance_m", 0.02))).validate_all(wall, record, previous_status)
        engine_status = result.overall_status.value
        payload = result.to_dict()
        fingerprint_payload = {
            "wall": wall.__dict__,
            "record": record.__dict__,
            "result": _stable_generic_result(payload),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        last = package.stewardship_history[-1] if package.stewardship_history else None
        created = not last or last.get("fingerprint") != fingerprint
        same_series = [entry for entry in package.stewardship_history if entry.get("mapping_series_uri") == series_uri]
        revision = len(same_series) + 1
        assertion_uri = f"{series_uri}/assertion/{revision}" if created else (last.get("assertion_uri") if last else None)
        package.mapping_series_uri = series_uri
        package.latest_mapping_assertion_uri = assertion_uri
        package.lifecycle_status = engine_status
        if created:
            package.stewardship_history.append({
                "mode": "generic",
                "timestamp": result.assessment_timestamp,
                "mapping_series_uri": series_uri,
                "assertion_uri": assertion_uri,
                "revision": revision,
                "status": package.lifecycle_display_status,
                "engine_status": engine_status,
                "result": payload,
                "fingerprint": fingerprint,
            })
        package.metadata["stewardship_rdf_turtle"] = _generic_turtle(package.stewardship_history)
        finalize_package(package)
        return StewardshipOutcome(package.lifecycle_display_status, engine_status, created, series_uri, assertion_uri, payload)
