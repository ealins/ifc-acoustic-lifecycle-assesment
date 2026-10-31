"""Tests for building records from new inputs (vibro_ifc/build_service.py)."""
import os
from pathlib import Path

import pytest

pytest.importorskip("ifcopenshell")
from vibro_ifc import build_service as bs, engine as sv

DATA = Path(os.environ.get("VIBRO_TEST_DATA", "data/ldv"))


def test_rejects_missing_txt():
    with pytest.raises(bs.BuildError, match="TXT"):
        bs.build_from_uploads("wall.ifc", b"x", {})


def test_unreadable_ifc_gives_a_message():
    with pytest.raises(bs.BuildError):
        bs.build_from_uploads("wall.ifc", b"not an ifc", {"a.txt": b"x"})


@pytest.mark.skipif(not (DATA / "Zublin_wall_clean.ifc").is_file(), reason="wall IFC and TXT files not present")
def test_build_from_real_files(tmp_path):
    txt = {p.name: p.read_bytes() for p in sorted(DATA.glob("*.txt"))}
    result = bs.build_from_uploads("Zublin_wall_clean.ifc", (DATA / "Zublin_wall_clean.ifc").read_bytes(), txt, workdir=tmp_path)
    assert len(result["records"]) == len(txt) and not result["excluded"]
    graph = sv.load_record(result["records"][0])
    assert {r["status"] for r in sv.data_checks(graph, result["data_dir"])} == {"match"}
    assert sv.summary(graph)["registration"] == "not established"
    assert len(bs.package_zip(result)) > 1000
