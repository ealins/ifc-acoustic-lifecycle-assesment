"""
Flask API Server for GeoBIM Semantic Lifecycle Engine
Exposes /api/analyze endpoint for IFC-external performance-record association assessment.
"""

import json
import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask.json.provider import DefaultJSONProvider

from lifecycle_engine.assessment import (
    IFCEvidence,
    RecordEvidence,
    assess_association,
    batch_assess,
)

# --- App Setup ---
app = Flask(__name__)
CORS(app)


class _EnumJSONProvider(DefaultJSONProvider):
    """JSON provider that serialises Enum members to their .value."""

    @staticmethod
    def default(o):
        from enum import Enum
        if isinstance(o, Enum):
            return o.value
        return DefaultJSONProvider.default(o)


app.json_provider_class = _EnumJSONProvider
app.json = _EnumJSONProvider(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lifecycle_api")


# --- Helpers ---
def _parse_ifc_evidence(data: Dict[str, Any]) -> IFCEvidence:
    """Parse JSON dict into IFCEvidence dataclass.

    Expected keys:
        global_id (str): IFC GlobalId of the wall element.
        name (str): IFC element Name.
        construction_family (str): Construction family label (e.g. "loadbearing", "curtain").
        total_thickness_m (float, optional): Total wall thickness in metres.
        material_evidence (list): Material layers extracted from IFC.
        model_version (str): IFC model version / schema identifier.
    """
    return IFCEvidence(
        global_id=data.get("global_id", ""),
        name=data.get("name", ""),
        construction_family=data.get("construction_family", ""),
        total_thickness_m=data.get("total_thickness_m"),
        material_evidence=data.get("material_evidence", []),
        model_version=data.get("model_version", ""),
    )


def _parse_record_evidence(data: Dict[str, Any]) -> RecordEvidence:
    """Parse JSON dict into RecordEvidence dataclass.

    Expected keys:
        uri (str): URI of the external record.
        identifier (str): Human-readable record identifier.
        assembly (str): Assembly description.
        construction_family (str): Construction family label.
        total_thickness_m (float, optional): Total thickness in metres.
        record_version (str): Version / edition of the record.
        available (bool, optional): Whether the record is resolvable. Defaults to True.
    """
    return RecordEvidence(
        uri=data.get("uri", ""),
        identifier=data.get("identifier", ""),
        assembly=data.get("assembly", ""),
        construction_family=data.get("construction_family", ""),
        total_thickness_m=data.get("total_thickness_m"),
        record_version=data.get("record_version", ""),
        available=data.get("available", True),
    )


# --- Routes ---
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "lifecycle-assessment-api"}), 200


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Assess IFC-external performance-record associations.

    Request JSON body (single mode):
    {
        "ifc_evidence": { "global_id": "...", "name": "...", ... },
        "record_evidence": { "uri": "...", "identifier": "...", ... }
    }

    Or batch mode (cross-product of every IFC × every record):
    {
        "batch": true,
        "ifc": [ { "global_id": "...", ... }, ... ],
        "records": [ { "uri": "...", ... }, ... ]
    }
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON in request body"}), 400

    if not payload:
        return jsonify({"error": "Empty request body"}), 400

    # Batch mode
    if payload.get("batch", False):
        ifc_raw = payload.get("ifc", [])
        records_raw = payload.get("records", [])

        if not ifc_raw or not records_raw:
            return jsonify({
                "error": "Batch mode requires both 'ifc' and 'records' arrays"
            }), 400

        ifc_list = [_parse_ifc_evidence(item) for item in ifc_raw]
        record_list = [_parse_record_evidence(item) for item in records_raw]

        results = batch_assess(ifc_list, record_list)
        return jsonify({
            "status": "ok",
            "count": len(results),
            "results": [asdict(r) for r in results],
        }), 200

    # Single assessment mode
    ifc_data = payload.get("ifc_evidence")
    rec_data = payload.get("record_evidence")

    if not ifc_data or not rec_data:
        return jsonify({
            "error": "Missing 'ifc_evidence' or 'record_evidence' in request body"
        }), 400

    ifc_ev = _parse_ifc_evidence(ifc_data)
    rec_ev = _parse_record_evidence(rec_data)

    result = assess_association(ifc_ev, rec_ev)
    return jsonify({
        "status": "ok",
        "result": asdict(result),
    }), 200


# --- Error Handlers ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error")
    return jsonify({"error": "Internal server error"}), 500


# --- Entry Point ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info(f"Starting Lifecycle Assessment API on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
