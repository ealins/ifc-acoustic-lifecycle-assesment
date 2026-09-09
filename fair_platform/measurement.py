from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re

import pandas as pd

try:
    from defusedxml import ElementTree as SafeET
except ImportError:  # pragma: no cover - dependency is declared for deployed environments
    import xml.etree.ElementTree as SafeET

from .research_object import MeasurementOrigin


_SIGNAL_PATTERNS = {
    "frequency": re.compile(r"freq|hz", re.I),
    "sound_reduction": re.compile(r"\brw\b|sound.?reduction|insulation", re.I),
    "vibration": re.compile(r"accel|velocity|vibration|displacement", re.I),
    "mode_shape": re.compile(r"mode|eigen", re.I),
    "uncertainty": re.compile(r"uncert|sigma|std|confidence", re.I),
    "absorption": re.compile(r"absorp|alpha|impedance", re.I),
    "impulse_response": re.compile(r"impulse|reverber|rt60|edt", re.I),
    "transfer_function": re.compile(r"transfer|frf|phase|amplitude", re.I),
}


def _signals(labels: list[str]) -> list[str]:
    joined = " ".join(str(item) for item in labels)
    return [name for name, pattern in _SIGNAL_PATTERNS.items() if pattern.search(joined)]


def _normalize_origin(value: str | MeasurementOrigin | None) -> MeasurementOrigin:
    if isinstance(value, MeasurementOrigin):
        return value
    text = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "measurement": MeasurementOrigin.RAW_MEASUREMENT,
        "raw": MeasurementOrigin.RAW_MEASUREMENT,
        "processed": MeasurementOrigin.PROCESSED_MEASUREMENT,
        "derived": MeasurementOrigin.DERIVED_RESULT,
        "reference": MeasurementOrigin.REFERENCE_VALUE,
        "manufacturer": MeasurementOrigin.MANUFACTURER_VALUE,
        "prediction": MeasurementOrigin.PREDICTED_VALUE,
        "predicted": MeasurementOrigin.PREDICTED_VALUE,
        "simulation": MeasurementOrigin.SIMULATION_RESULT,
    }
    if text in aliases:
        return aliases[text]
    try:
        return MeasurementOrigin(text)
    except ValueError:
        return MeasurementOrigin.UNKNOWN


def _base(filename: str, payload: bytes, declared_origin: str | MeasurementOrigin | None = None) -> dict:
    suffix = Path(filename).suffix.lower()
    origin = _normalize_origin(declared_origin)
    return {
        "source_filename": filename,
        "extension": suffix,
        "size_bytes": len(payload),
        "valid": True,
        "format": suffix.lstrip(".") or "binary",
        "summary": "",
        "details": {},
        "semantic_signals": [],
        "origin_classification": origin.value,
        "origin_basis": "user-declared" if origin != MeasurementOrigin.UNKNOWN else "not declared",
        "warnings": [],
    }


def _leaf_values(root, limit: int = 60) -> list[dict]:
    rows: list[dict] = []
    for node in root.iter():
        if list(node):
            continue
        text = (node.text or "").strip()
        if not text:
            continue
        tag = str(node.tag).split("}")[-1]
        value: object = text
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            pass
        rows.append({"field": tag, "value": value, "attributes": dict(node.attrib)})
        if len(rows) >= limit:
            break
    return rows


def _inspect_xml(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    root = SafeET.fromstring(payload)
    elements = list(root.iter())
    tags = sorted({str(node.tag).split("}")[-1] for node in elements})
    attributes = sorted({key for node in elements for key in node.attrib.keys()})
    values = _leaf_values(root)
    result["details"] = {
        "root_element": str(root.tag).split("}")[-1],
        "element_count": len(elements),
        "unique_tags": tags[:80],
        "attribute_names": attributes[:80],
        "parsed_values": values,
    }
    result["semantic_signals"] = _signals(tags + attributes)
    result["summary"] = f"XML dataset with root '{result['details']['root_element']}' and {len(elements)} element(s)"
    return result


def _inspect_csv(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    frame = pd.read_csv(BytesIO(payload), nrows=5000)
    columns = [str(column) for column in frame.columns]
    numeric = [str(column) for column in frame.select_dtypes(include="number").columns]
    result["details"] = {
        "sampled_rows": int(len(frame)),
        "columns": columns,
        "numeric_columns": numeric,
        "preview": frame.head(8).where(pd.notnull(frame), None).to_dict(orient="records"),
    }
    result["semantic_signals"] = _signals(columns)
    result["summary"] = f"CSV dataset with {len(columns)} column(s); inspected {len(frame)} row(s)"
    return result


def _inspect_json(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    obj = json.loads(payload.decode("utf-8"))
    if isinstance(obj, dict):
        keys = [str(key) for key in obj.keys()]
        record_count = len(obj)
        structure = "object"
    elif isinstance(obj, list):
        keys = sorted({str(key) for item in obj[:100] if isinstance(item, dict) for key in item.keys()})
        record_count = len(obj)
        structure = "array"
    else:
        keys = []
        record_count = 1
        structure = type(obj).__name__
    result["details"] = {"structure": structure, "record_count": record_count, "keys": keys[:100]}
    result["semantic_signals"] = _signals(keys)
    result["summary"] = f"JSON {structure} with {record_count} top-level record(s)"
    return result


def _inspect_hdf5(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover
        result["valid"] = False
        result["warnings"].append(f"h5py unavailable: {exc}")
        result["summary"] = "HDF5 file packaged, but structural inspection is unavailable"
        return result
    datasets: list[dict] = []
    groups: list[str] = []
    with h5py.File(BytesIO(payload), "r") as handle:
        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                datasets.append({"path": name, "shape": list(obj.shape), "dtype": str(obj.dtype)})
            elif isinstance(obj, h5py.Group):
                groups.append(name)
        handle.visititems(visitor)
    labels = [item["path"] for item in datasets] + groups
    result["details"] = {"dataset_count": len(datasets), "group_count": len(groups), "datasets": datasets[:100], "groups": groups[:100]}
    result["semantic_signals"] = _signals(labels)
    result["summary"] = f"HDF5 dataset with {len(datasets)} dataset(s) in {len(groups)} group(s)"
    return result


def _inspect_vtk(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    text = payload.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = lines[:4]
    dataset_type = None
    counts: dict[str, int] = {}
    labels: list[str] = []
    for line in lines[:5000]:
        parts = line.split()
        if not parts:
            continue
        key = parts[0].upper()
        if key == "DATASET" and len(parts) > 1:
            dataset_type = parts[1]
            labels.append(parts[1])
        elif key in {"POINTS", "CELLS", "POLYGONS", "LINES", "VERTICES", "POINT_DATA", "CELL_DATA"} and len(parts) > 1:
            try:
                counts[key.lower()] = int(parts[1])
            except ValueError:
                pass
        elif key in {"SCALARS", "VECTORS", "TENSORS", "FIELD"} and len(parts) > 1:
            labels.append(parts[1])
    result["details"] = {"header": header, "dataset_type": dataset_type, "counts": counts, "data_arrays": labels[:100]}
    result["semantic_signals"] = _signals(labels)
    result["summary"] = f"VTK dataset {dataset_type or 'unknown type'} with structural counts {counts or '{}'}"
    return result


def _inspect_text(filename: str, payload: bytes, declared_origin=None) -> dict:
    result = _base(filename, payload, declared_origin)
    text = payload.decode("utf-8", errors="replace")
    lines = text.splitlines()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]{2,}", " ".join(lines[:200]))
    result["details"] = {"line_count": len(lines), "sample": lines[:20]}
    result["semantic_signals"] = _signals(tokens)
    result["summary"] = f"Text/data file with {len(lines)} line(s)"
    return result


def inspect_measurement(filename: str, payload: bytes, declared_origin: str | MeasurementOrigin | None = None) -> dict:
    """Inspect a supported acoustic asset without inventing scientific semantics.

    Origin is explicit user/repository metadata. Structural signal detection is a hint only
    and never upgrades an unknown-origin record into a measured or predicted record.
    """
    if not payload:
        result = _base(filename, payload, declared_origin)
        result.update({"valid": False, "format": "unknown", "summary": "Empty acoustic data payload"})
        result["warnings"].append("Acoustic data payload is empty")
        return result
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".xml":
            return _inspect_xml(filename, payload, declared_origin)
        if suffix == ".csv":
            return _inspect_csv(filename, payload, declared_origin)
        if suffix == ".json":
            return _inspect_json(filename, payload, declared_origin)
        if suffix in {".h5", ".hdf5"}:
            return _inspect_hdf5(filename, payload, declared_origin)
        if suffix == ".vtk":
            return _inspect_vtk(filename, payload, declared_origin)
        if suffix in {".txt", ".dat", ".ttl", ".rdf"}:
            return _inspect_text(filename, payload, declared_origin)
        result = _base(filename, payload, declared_origin)
        result["summary"] = "Binary acoustic data asset preserved without format-specific parsing"
        result["warnings"].append("No format-specific inspector is registered for this extension")
        return result
    except Exception as exc:
        result = _base(filename, payload, declared_origin)
        result["valid"] = False
        result["summary"] = f"Acoustic data inspection failed for {suffix or 'unknown format'}"
        result["warnings"].append(str(exc))
        return result
