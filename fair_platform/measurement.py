from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pandas as pd


_SIGNAL_PATTERNS = {
    "frequency": re.compile(r"freq|hz", re.I),
    "sound_reduction": re.compile(r"\brw\b|sound.?reduction|insulation", re.I),
    "vibration": re.compile(r"accel|velocity|vibration|displacement", re.I),
    "mode_shape": re.compile(r"mode|eigen", re.I),
    "uncertainty": re.compile(r"uncert|sigma|std|confidence", re.I),
}


def _signals(labels: list[str]) -> list[str]:
    joined = " ".join(str(item) for item in labels)
    return [name for name, pattern in _SIGNAL_PATTERNS.items() if pattern.search(joined)]


def _base(filename: str, payload: bytes) -> dict:
    suffix = Path(filename).suffix.lower()
    return {
        "source_filename": filename,
        "extension": suffix,
        "size_bytes": len(payload),
        "valid": True,
        "format": suffix.lstrip(".") or "binary",
        "summary": "",
        "details": {},
        "semantic_signals": [],
        "warnings": [],
    }


def _inspect_xml(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
    root = ET.fromstring(payload)
    elements = list(root.iter())
    tags = sorted({str(node.tag).split("}")[-1] for node in elements})
    attributes = sorted({key for node in elements for key in node.attrib.keys()})
    result["details"] = {
        "root_element": str(root.tag).split("}")[-1],
        "element_count": len(elements),
        "unique_tags": tags[:80],
        "attribute_names": attributes[:80],
    }
    result["semantic_signals"] = _signals(tags + attributes)
    result["summary"] = f"XML dataset with root '{result['details']['root_element']}' and {len(elements)} element(s)"
    return result


def _inspect_csv(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
    frame = pd.read_csv(BytesIO(payload), nrows=5000)
    columns = [str(column) for column in frame.columns]
    numeric = [str(column) for column in frame.select_dtypes(include="number").columns]
    result["details"] = {
        "sampled_rows": int(len(frame)),
        "columns": columns,
        "numeric_columns": numeric,
        "preview": frame.head(5).where(pd.notnull(frame), None).to_dict(orient="records"),
    }
    result["semantic_signals"] = _signals(columns)
    result["summary"] = f"CSV dataset with {len(columns)} column(s); inspected {len(frame)} row(s)"
    return result


def _inspect_json(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
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


def _inspect_hdf5(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - dependency is installed in the app image
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


def _inspect_vtk(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
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


def _inspect_text(filename: str, payload: bytes) -> dict:
    result = _base(filename, payload)
    text = payload.decode("utf-8", errors="replace")
    lines = text.splitlines()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]{2,}", " ".join(lines[:200]))
    result["details"] = {"line_count": len(lines), "sample": lines[:20]}
    result["semantic_signals"] = _signals(tokens)
    result["summary"] = f"Text/data file with {len(lines)} line(s)"
    return result


def inspect_measurement(filename: str, payload: bytes) -> dict:
    """Return a serializable structural inspection of an external measurement dataset.

    The inspector does not invent acoustic semantics. It exposes the structure that can be
    verified locally and records detected signal names as hints for researchers.
    """
    if not payload:
        return {
            "source_filename": filename,
            "extension": Path(filename).suffix.lower(),
            "size_bytes": 0,
            "valid": False,
            "format": "unknown",
            "summary": "Empty measurement payload",
            "details": {},
            "semantic_signals": [],
            "warnings": ["Measurement payload is empty"],
        }

    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".xml":
            return _inspect_xml(filename, payload)
        if suffix == ".csv":
            return _inspect_csv(filename, payload)
        if suffix == ".json":
            return _inspect_json(filename, payload)
        if suffix in {".h5", ".hdf5"}:
            return _inspect_hdf5(filename, payload)
        if suffix == ".vtk":
            return _inspect_vtk(filename, payload)
        if suffix in {".txt", ".dat", ".ttl", ".rdf"}:
            return _inspect_text(filename, payload)
        result = _base(filename, payload)
        result["summary"] = "Binary measurement asset preserved without format-specific parsing"
        result["warnings"].append("No format-specific inspector is registered for this extension")
        return result
    except Exception as exc:
        result = _base(filename, payload)
        result["valid"] = False
        result["summary"] = f"Measurement inspection failed for {suffix or 'unknown format'}"
        result["warnings"].append(str(exc))
        return result
