"""Conservative inspection of original SLDV TXT/CSV payloads.

This module borrows the useful file-derived checks from the Library's
build_scan_record.py without hard-coding its one specimen's 6,381-row,
20--6,400 Hz axis. It never rewrites or converts the source payload.
"""
from __future__ import annotations

import csv
import io
import math
import re
from pathlib import Path
from typing import Any

_POINT_RE = re.compile(
    r"Point Index:\\s*(\\d+)\\s*\\[\\s*x\\s*=\\s*([-+0-9.eE]+)"
    r"\\s*y\\s*=\\s*([-+0-9.eE]+)\\s*z\\s*=\\s*([-+0-9.eE]+)\\s*\\]"
)


def _number(value: str) -> float | None:
    try:
        result = float(value.strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def inspect_sldv_payload(filename: str, payload: bytes) -> dict[str, Any]:
    """Return derived diagnostics only; never modify the supplied bytes.

    For tab-delimited SLDV TXT, identifies a point header when present and
    discovers numeric rows after it. For CSV, discovers numeric data rows
    without assuming a fixed column layout. A frequency axis is reported only
    when the first field is numeric across the discovered rows.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".csv"}:
        return {
            "supported": False,
            "filename": filename,
            "reason": "Only original .txt and .csv measurement payloads are supported by the thesis profile.",
        }

    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    point = None
    for line in lines[:12]:
        match = _POINT_RE.search(line)
        if match:
            point = {
                "index": int(match.group(1)),
                "x": float(match.group(2)),
                "y": float(match.group(3)),
                "z": float(match.group(4)),
                "coordinate_frame": "source-declared; IFC registration not inferred",
            }
            break

    delimiter = "," if suffix == ".csv" else "\\t"
    if suffix == ".csv":
        raw_rows = list(csv.reader(io.StringIO(text)))
    else:
        raw_rows = [line.split("\\t") for line in lines]

    numeric_rows: list[list[float]] = []
    for row in raw_rows:
        cleaned = [cell.strip() for cell in row]
        if not cleaned or not any(cleaned):
            continue
        values = [_number(cell) for cell in cleaned]
        if values and all(value is not None for value in values):
            numeric_rows.append([float(value) for value in values])

    widths = sorted({len(row) for row in numeric_rows})
    rectangular = len(widths) <= 1
    first_column = [row[0] for row in numeric_rows if row]
    axis = None
    if len(first_column) >= 2:
        deltas = [b - a for a, b in zip(first_column, first_column[1:])]
        positive = all(delta > 0 for delta in deltas)
        mean_delta = sum(deltas) / len(deltas)
        uniform = positive and all(
            math.isclose(delta, mean_delta, rel_tol=1e-5, abs_tol=1e-9)
            for delta in deltas
        )
        axis = {
            "first_column_interpreted_as": "candidate numeric axis (not semantically confirmed)",
            "start": first_column[0],
            "end": first_column[-1],
            "step_if_uniform": mean_delta if uniform else None,
            "strictly_increasing": positive,
            "uniform_spacing": uniform,
        }

    warnings: list[str] = []
    if not numeric_rows:
        warnings.append("No fully numeric rows were detected; inspect the file layout manually.")
    if not rectangular:
        warnings.append("Numeric rows have different column counts.")
    if point is None and suffix == ".txt":
        warnings.append("No SLDV Point Index/x/y/z header was detected; this is not treated as a failure.")
    if axis:
        warnings.append("The first numeric column is reported as a candidate axis only; confirm its meaning from the acquisition format.")

    return {
        "supported": True,
        "filename": filename,
        "media_type": "text/csv" if suffix == ".csv" else "text/plain",
        "byte_size": len(payload),
        "encoding_used_for_inspection": "UTF-8 with replacement fallback",
        "line_count": len(lines),
        "numeric_row_count": len(numeric_rows),
        "numeric_column_count": widths[0] if rectangular and widths else None,
        "numeric_rows_rectangular": rectangular,
        "point_header": point,
        "candidate_axis": axis,
        "source_preserved": True,
        "warnings": warnings,
    }
