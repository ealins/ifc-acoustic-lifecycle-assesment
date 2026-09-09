"""Test key lifecycle scenarios."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifecycle_engine.evaluation_runner import run_lifecycle_evaluation


def test_ambiguous_then_identical():
    """AMBIGUOUS initial assessment, then identical rerun creates no revision."""
    wall = {
        "global_id": "wall-001",
        "name": "Metal Frame",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.285,
        "material_evidence": ["Stud 75mm", "Batt 100mm"],
        "model_version": "v1",
    }
    record = {
        "uri": "https://example.org/rec/001",
        "identifier": "rec-001",
        "assembly": "M75_B100",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.100,
        "rw": 44.1,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-001",
        "year": 2024,
        "available": True,
    }

    result1 = run_lifecycle_evaluation(wall, record)
    assert result1["assessment"]["semantic_status"] == "ambiguous"
    assert result1["revision_action"] == "created_revision"

    result2 = run_lifecycle_evaluation(
        wall,
        record,
        previous_assessment=result1["assessment"],
    )
    assert result2["revision_action"] == "no_change_no_revision"


def test_acoustic_change():
    """A changed acoustic value creates a new revision."""
    wall = {
        "global_id": "wall-001",
        "name": "Metal Frame",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.285,
        "material_evidence": ["Stud 75mm"],
        "model_version": "v1",
    }
    record = {
        "uri": "https://example.org/rec/001",
        "identifier": "rec-001",
        "assembly": "M75",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.100,
        "rw": 45.0,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-001",
        "year": 2024,
        "available": True,
    }
    previous = {
        "ifc_global_id": "wall-001",
        "record_id": "rec-001",
        "semantic_status": "ambiguous",
        "confidence": 0.65,
    }
    result = run_lifecycle_evaluation(wall, record, previous_assessment=previous)
    assert result["revision_action"] == "created_revision"


def test_resource_broken():
    """Unavailable external resource produces BROKEN."""
    wall = {
        "global_id": "wall-001",
        "name": "Metal Frame",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.285,
        "material_evidence": ["Stud"],
        "model_version": "v1",
    }
    record = {
        "uri": "https://example.org/rec/001",
        "identifier": "rec-001",
        "assembly": "M75",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.100,
        "rw": 44.1,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-001",
        "year": 2024,
        "available": False,
    }
    result = run_lifecycle_evaluation(wall, record)
    assert result["assessment"]["semantic_status"] == "broken"


def test_family_mismatch_with_aligned_thickness_is_ambiguous():
    """A single contradictory criterion is AMBIGUOUS, not INVALID.

    The lifecycle engine defines INVALID only when both construction family and
    thickness diverge. Here the 10 mm thickness difference is within the default
    20 mm tolerance, so only the family criterion conflicts.
    """
    wall = {
        "global_id": "wall-002",
        "name": "Concrete",
        "construction_family": "concrete",
        "total_thickness_m": 0.285,
        "material_evidence": ["Concrete"],
        "model_version": "v1",
    }
    record = {
        "uri": "https://example.org/rec/002",
        "identifier": "rec-002",
        "assembly": "M75",
        "construction_family": "metal_frame",
        "total_thickness_m": 0.275,
        "rw": 50.0,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-002",
        "year": 2024,
        "available": True,
    }
    result = run_lifecycle_evaluation(wall, record)
    assert result["assessment"]["semantic_status"] == "ambiguous"


def run_tests():
    tests = [
        test_ambiguous_then_identical,
        test_acoustic_change,
        test_resource_broken,
        test_family_mismatch_with_aligned_thickness_is_ambiguous,
    ]
    try:
        for test in tests:
            test()
        print("ALL LIFECYCLE SCENARIO TESTS PASSED")
        return True
    except Exception as exc:
        print(f"TEST FAILED: {exc}")
        return False


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
