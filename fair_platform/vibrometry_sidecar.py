"""Build and verify the three-input SLDV/IFC JSON-LD sidecar.

The thesis workflow deliberately keeps the source TXT/CSV payload intact.  It
does not create an HDF5 derivative: the sidecar joins the measurement payload,
declared laboratory context, and IFC component context.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rdflib import Graph


PROFILE_ID = "https://w3id.org/vibro-ifc/profile/0.1"
PROFILE_VERSION = "0.1.0"
CONTEXT = {
    "@vocab": "https://w3id.org/vibro-ifc/vocab/",
    "dct": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "schema": "https://schema.org/",
}


def sha256_uri(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _normalise_sha256(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def build_sidecar(
    measurement_name: str,
    measurement_payload: bytes,
    lab_context: dict[str, Any],
    ifc_context: dict[str, Any],
    *,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Create portable JSON-LD without inventing any laboratory facts."""
    if Path(measurement_name).suffix.lower() not in {".txt", ".csv"}:
        raise ValueError("The SLDV measurement payload must be a TXT or CSV file.")
    required_ifc = ("global_id", "ifc_schema", "source_sha256", "ifc_class")
    missing_ifc = [field for field in required_ifc if not ifc_context.get(field)]
    if missing_ifc:
        raise ValueError("IFC context is missing: " + ", ".join(missing_ifc))

    identifier = record_id or Path(measurement_name).stem
    node_id = f"urn:vibro-ifc:record:{identifier}"
    return {
        "@context": CONTEXT,
        "@id": node_id,
        "@type": ["VibrometryMeasurementRecord", "schema:Dataset"],
        "dct:conformsTo": PROFILE_ID,
        "profileVersion": PROFILE_VERSION,
        "recordIdentifier": identifier,
        "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "measurementPayload": {
            "@id": f"{node_id}#payload",
            "@type": "MeasurementPayload",
            "fileName": measurement_name,
            "mediaType": "text/csv" if measurement_name.lower().endswith(".csv") else "text/plain",
            "byteSize": len(measurement_payload),
            "sha256": sha256_uri(measurement_payload),
        },
        "labContext": {key: value for key, value in lab_context.items() if value not in (None, "", [], {})},
        "ifcLinkRecord": {
            "@id": f"{node_id}#ifc-link",
            "@type": "IfcComponentLink",
            "ifcFileName": ifc_context.get("source_file"),
            "ifcSha256": _normalise_sha256(str(ifc_context["source_sha256"])),
            "ifcSchema": ifc_context["ifc_schema"],
            "ifcGlobalId": ifc_context["global_id"],
            "ifcEntityType": ifc_context["ifc_class"],
            "componentName": ifc_context.get("name"),
        },
    }


def validate_sidecar(
    sidecar: dict[str, Any], measurement_payload: bytes, ifc_payload: bytes, resolved_ifc: dict[str, Any]
) -> list[dict[str, str]]:
    """Perform cross-layer checks which cannot be expressed in SHACL alone."""
    issues: list[dict[str, str]] = []
    payload = sidecar.get("measurementPayload", {})
    link = sidecar.get("ifcLinkRecord", {})
    if payload.get("sha256") != sha256_uri(measurement_payload):
        issues.append({"code": "MEASUREMENT_HASH_MISMATCH", "message": "Measurement bytes do not match the JSON-LD sidecar."})
    if link.get("ifcSha256") != sha256_uri(ifc_payload):
        issues.append({"code": "IFC_HASH_MISMATCH", "message": "IFC bytes do not match the JSON-LD sidecar."})
    if not resolved_ifc.get("resolved"):
        issues.append({"code": "IFC_GLOBALID_UNRESOLVED", "message": "The declared IFC GlobalId does not resolve in the supplied IFC model."})
    elif link.get("ifcGlobalId") != resolved_ifc.get("global_id"):
        issues.append({"code": "IFC_GLOBALID_MISMATCH", "message": "The resolved IFC GlobalId differs from the JSON-LD sidecar."})
    elif link.get("ifcEntityType") != resolved_ifc.get("ifc_class"):
        issues.append({"code": "IFC_CLASS_MISMATCH", "message": "The resolved IFC entity type differs from the JSON-LD sidecar."})
    return issues


def jsonld_is_parseable(sidecar: dict[str, Any]) -> bool:
    graph = Graph()
    graph.parse(data=__import__("json").dumps(sidecar), format="json-ld")
    return len(graph) > 0
