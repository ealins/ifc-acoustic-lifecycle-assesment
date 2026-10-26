from fair_platform.vibrometry_sidecar import build_sidecar, jsonld_is_parseable, sha256_uri, validate_sidecar


def _ifc_context():
    return {"global_id": "0abc", "ifc_schema": "IFC4", "source_sha256": "sha256:placeholder", "ifc_class": "IfcWall", "source_file": "wall.ifc"}


def test_sidecar_keeps_three_sources_and_is_jsonld():
    data = b"point,velocity\n1,0.03\n"
    sidecar = build_sidecar("scan.csv", data, {"method": "SLDV", "unit": "m/s"}, _ifc_context(), record_id="scan-01")
    assert sidecar["measurementPayload"]["fileName"] == "scan.csv"
    assert sidecar["labContext"]["method"] == "SLDV"
    assert sidecar["ifcLinkRecord"]["ifcGlobalId"] == "0abc"
    assert jsonld_is_parseable(sidecar)


def test_cross_layer_checks_detect_changed_payload_and_ifc():
    sidecar = build_sidecar("scan.txt", b"one", {"method": "SLDV"}, _ifc_context())
    issues = validate_sidecar(sidecar, b"two", b"ifc", {"resolved": False})
    assert {issue["code"] for issue in issues} == {"MEASUREMENT_HASH_MISMATCH", "IFC_HASH_MISMATCH", "IFC_GLOBALID_UNRESOLVED"}


def test_cross_layer_checks_accept_matching_sources():
    measurement, ifc = b"one", b"ifc"
    context = _ifc_context()
    context["source_sha256"] = sha256_uri(ifc)
    sidecar = build_sidecar("scan.txt", measurement, {"method": "SLDV"}, context)
    assert validate_sidecar(sidecar, measurement, ifc, {"resolved": True, "global_id": "0abc", "ifc_class": "IfcWall"}) == []
