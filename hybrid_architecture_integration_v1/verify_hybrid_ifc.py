from __future__ import annotations

import argparse
import json
from pathlib import Path


def nominal_value_text(value) -> str:
    if value is None:
        return ""
    wrapped = getattr(value, "wrappedValue", None)
    return str(wrapped if wrapped is not None else value)


def main() -> None:
    p = argparse.ArgumentParser(description="Inspect and verify the hybrid IFC link architecture.")
    p.add_argument("--ifc", type=Path, required=True)
    p.add_argument("--global-id", required=True)
    args = p.parse_args()

    try:
        import ifcopenshell
    except ImportError as e:
        raise RuntimeError("IfcOpenShell is required. Run in the thesis .venv.") from e

    model = ifcopenshell.open(str(args.ifc))
    wall = model.by_guid(args.global_id)
    if wall is None:
        raise RuntimeError(f"IFC element {args.global_id} not found")

    native = []
    hft = None
    for rel in model.get_inverse(wall):
        try:
            if rel.is_a() == "IfcRelAssociatesDocument":
                doc = getattr(rel, "RelatingDocument", None)
                if doc is not None and doc.is_a() == "IfcDocumentReference":
                    native.append({
                        "relation_step_id": rel.id(),
                        "document_step_id": doc.id(),
                        "location": str(getattr(doc, "Location", "") or ""),
                        "identification": str(getattr(doc, "Identification", "") or ""),
                        "name": str(getattr(doc, "Name", "") or ""),
                    })
            elif rel.is_a() == "IfcRelDefinesByProperties":
                pset = getattr(rel, "RelatingPropertyDefinition", None)
                if pset is not None and pset.is_a() == "IfcPropertySet" and str(getattr(pset, "Name", "") or "") == "HFT_AcousticLink":
                    props = {}
                    for prop in getattr(pset, "HasProperties", None) or []:
                        props[str(getattr(prop, "Name", "") or "")] = nominal_value_text(getattr(prop, "NominalValue", None))
                    hft = {"pset_step_id": pset.id(), "properties": props}
        except Exception:
            pass

    duplicate_custom_record_uri = bool(hft and "AcousticRecordURI" in hft["properties"])
    mutable_status_in_ifc = bool(hft and any(k in hft["properties"] for k in ("MappingStatus", "MappingBasis")))
    result = {
        "wall": {"global_id": str(wall.GlobalId), "name": str(getattr(wall, "Name", "") or ""), "step_id": wall.id()},
        "native_document_references": native,
        "hft_semantic_anchor": hft,
        "checks": {
            "exactly_one_native_document_reference": len(native) == 1,
            "native_location_present": len(native) == 1 and bool(native[0]["location"]),
            "hft_anchor_present": hft is not None,
            "mapping_series_uri_present": bool(hft and hft["properties"].get("MappingSeriesURI")),
            "no_duplicate_acoustic_record_uri_in_hft": not duplicate_custom_record_uri,
            "no_mutable_mapping_status_in_hft": not mutable_status_in_ifc,
        },
    }
    result["checks"]["overall_pass"] = all(result["checks"].values())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
