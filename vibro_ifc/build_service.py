"""Build v0.6 records from new inputs: one IFC, one or more Polytec TXT files, and the lab facts.

Wraps the toolkit builder (vibro_ifc/builder/build.py).  Nothing in the inputs is
modified.  A TXT file that cannot be read is excluded and listed with the reason.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

BUILDER_DIR = Path(__file__).resolve().parent / "builder"
DEFAULT_TEMPLATE = BUILDER_DIR / "template_base.jsonld"


class BuildError(Exception):
    """The builder stopped with a reason the user can act on."""


def _load_builder():
    if str(BUILDER_DIR) not in sys.path:
        sys.path.insert(0, str(BUILDER_DIR))
    spec = importlib.util.spec_from_file_location("ldv_build", BUILDER_DIR / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_from_uploads(
    ifc_name: str,
    ifc_bytes: bytes,
    txt_files: dict[str, bytes],
    template_bytes: bytes | None = None,
    *,
    default_freq_hz: float = 1000.0,
    default_channel: str = "Z",
    face_name: str = "RF_A",
    workdir: Path | None = None,
) -> dict[str, Any]:
    """Write the inputs to a work folder, run the builder, and return what it made."""
    if not txt_files:
        raise BuildError("Add at least one TXT measurement file.")
    root = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="vibro_build_"))
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(exist_ok=True)
    safe_ifc = Path(ifc_name).name
    (root / "data" / safe_ifc).write_bytes(ifc_bytes)
    for name, payload in txt_files.items():
        (root / "data" / Path(name).name).write_bytes(payload)
    (root / "templates" / "template.jsonld").write_bytes(template_bytes if template_bytes is not None else DEFAULT_TEMPLATE.read_bytes())
    project = {
        "name": Path(safe_ifc).stem,
        "ifc": f"data/{safe_ifc}",
        "target": {"mode": "auto", "class": "IfcWall", "guid": None},
        "data": {"dir": "data", "glob": "*.txt", "default_freq_hz": default_freq_hz, "default_channel": default_channel},
        "template": "templates/template.jsonld",
        "frame": {"source": "auto", "face_name": face_name, "matrix": None, "face": None},
        "out": {"metadata": "metadata", "view": "view", "view_name": face_name},
    }
    (root / "project.json").write_text(json.dumps(project, indent=2), encoding="utf-8")

    log = io.StringIO()
    builder = _load_builder()
    try:
        with contextlib.redirect_stdout(log):
            manifest = builder.main([str(root / "project.json")])
    except SystemExit:
        lines = [ln for ln in log.getvalue().splitlines() if ln.startswith("ERROR")]
        raise BuildError((lines[-1].split(":", 1)[-1].strip() if lines else log.getvalue().strip()) or "The builder stopped without a message.") from None
    except Exception as exc:  # unreadable IFC, geometry failure, template mismatch
        raise BuildError(f"The IFC or a file could not be processed ({exc}).") from exc

    records = sorted((root / "metadata" / "points").glob("point_*.jsonld"))
    return {
        "root": root,
        "records_dir": root / "metadata" / "points",
        "data_dir": root / "data",
        "records": records,
        "excluded": manifest.get("excluded", {}),
        "log": log.getvalue(),
        "frame": manifest.get("frame", {}),
        "view_config": next((root / "view").glob("view_config_*.json"), None),
    }


def package_zip(result: dict[str, Any]) -> bytes:
    """Zip the generated files (records, index, spectra cache, view config, manifest, project)."""
    root: Path = result["root"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in ("metadata", "view"):
            for path in sorted((root / folder).rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
        for name in ("build_manifest.json", "project.json"):
            if (root / name).is_file():
                archive.write(root / name, name)
    return buffer.getvalue()
