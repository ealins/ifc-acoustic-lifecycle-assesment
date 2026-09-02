"""Test key lifecycle scenarios."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifecycle_engine.evaluation_runner import run_lifecycle_evaluation


def test_ambiguous_then_identical():
    """Test: AMBIGUOUS initial, then identical rerun."""
    print("\n=== TEST 1: Ambiguous Association ===")
    
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
        "total_thickness_m": 0.100,  # Mismatch!
        "rw": 44.1,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-001",
        "year": 2024,
        "available": True,
    }
    
    # First run
    result1 = run_lifecycle_evaluation(wall, record)
    print(f"Status: {result1['assessment']['semantic_status']}")
    print(f"Action: {result1['revision_action']}")
    assert result1['assessment']['semantic_status'] == 'ambiguous'
    assert result1['revision_action'] == 'created_revision'
    
    # Identical rerun
    print("\n=== TEST 2: Identical Rerun (No Revision) ===")
    result2 = run_lifecycle_evaluation(wall, record, previous_assessment=result1['assessment'])
    print(f"Status: {result2['assessment']['semantic_status']}")
    print(f"Action: {result2['revision_action']}")
    print(f"Changes: {result2['change_report']['overall_category'] if result2['change_report'] else 'none'}")
    assert result2['revision_action'] == 'no_change_no_revision'
    
    return result1['assessment']


def test_acoustic_change():
    """Test: Acoustic content change."""
    print("\n=== TEST 3: Acoustic Content Change ===")
    
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
        "rw": 45.0,  # Changed
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-001",
        "year": 2024,
        "available": True,
    }
    
    prev_assessment = {
        "ifc_global_id": "wall-001",
        "record_id": "rec-001",
        "semantic_status": "ambiguous",
        "confidence": 0.65,
    }
    
    result = run_lifecycle_evaluation(wall, record, previous_assessment=prev_assessment)
    print(f"Action: {result['revision_action']}")
    print(f"Meaningful Changes: {result.get('change_report', {}).get('has_meaningful_changes', 'N/A')}")
    assert result['revision_action'] == 'created_revision'
    print("✓ PASS: Acoustic change triggers revision")


def test_resource_broken():
    """Test: Resource unavailable."""
    print("\n=== TEST 4: Resource Unavailable (BROKEN) ===")
    
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
        "available": False,  # Unavailable
    }
    
    result = run_lifecycle_evaluation(wall, record)
    print(f"Status: {result['assessment']['semantic_status']}")
    print(f"Technical Status: {result['assessment']['technical_status']}")
    assert result['assessment']['semantic_status'] == 'broken'
    print("✓ PASS: Unavailable resource → BROKEN status")


def test_invalid_family():
    """Test: Invalid - family mismatch."""
    print("\n=== TEST 5: Invalid Association (Family Mismatch) ===")
    
    wall = {
        "global_id": "wall-002",
        "name": "Concrete",
        "construction_family": "concrete",  # Different
        "total_thickness_m": 0.285,
        "material_evidence": ["Concrete"],
        "model_version": "v1",
    }
    
    record = {
        "uri": "https://example.org/rec/002",
        "identifier": "rec-002",
        "assembly": "M75",
        "construction_family": "metal_frame",  # Different
        "total_thickness_m": 0.275,
        "rw": 50.0,
        "unit": "dB",
        "source": "VaBDat",
        "report_reference": "VAB-002",
        "year": 2024,
        "available": True,
    }
    
    result = run_lifecycle_evaluation(wall, record)
    print(f"Status: {result['assessment']['semantic_status']}")
    print(f"Reason: {result['assessment']['reason']}")
    assert result['assessment']['semantic_status'] == 'invalid'
    print("✓ PASS: Family contradiction → INVALID status")


def run_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("GeoBIM LIFECYCLE ENGINE - RIGOROUS CHANGE DETECTION TESTS")
    print("="*70)
    
    try:
        test_ambiguous_then_identical()
        test_acoustic_change()
        test_resource_broken()
        test_invalid_family()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
