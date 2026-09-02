"""
Test harness for 3-tier validation using demo data.

Tests the complete validation pipeline with association_lifecycle_demo.json
"""

import sys
from pathlib import Path
import json

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from association_lifecycle import WallEvidence, RecordEvidence
from dashboard.backend.validators import TieredValidator, ValidationResult


def test_tier_1_link_validation():
    """Test Tier 1: Link Validation"""
    print("\n" + "="*70)
    print("TEST: Tier 1 - Link Validation")
    print("="*70)
    
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18"
    )
    
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True
    )
    
    validator = TieredValidator()
    checks = validator.validate_tier_1_link(wall, record)
    
    print(f"\nTier 1 Checks: {len(checks)} total")
    for check in checks:
        status = "✅ PASS" if check.passed else "❌ FAIL"
        print(f"  {status} - {check.name}")
        print(f"       {check.description}")
        if check.details:
            print(f"       {check.details}")
    
    passed = sum(1 for c in checks if c.passed)
    print(f"\nResult: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def test_tier_2_mapping_validation():
    """Test Tier 2: Mapping Validation"""
    print("\n" + "="*70)
    print("TEST: Tier 2 - Mapping Validation")
    print("="*70)
    
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18"
    )
    
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True
    )
    
    validator = TieredValidator()
    checks = validator.validate_tier_2_mapping(wall, record)
    
    print(f"\nTier 2 Checks: {len(checks)} total")
    for check in checks:
        status = "✅ PASS" if check.passed else "❌ FAIL"
        print(f"  {status} - {check.name}")
        print(f"       {check.description}")
        if check.details:
            print(f"       {check.details}")
    
    passed = sum(1 for c in checks if c.passed)
    print(f"\nResult: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def test_tier_3_lifecycle_validation():
    """Test Tier 3: Lifecycle Validation"""
    print("\n" + "="*70)
    print("TEST: Tier 3 - Lifecycle Validation")
    print("="*70)
    
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18"
    )
    
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True
    )
    
    validator = TieredValidator(thickness_tolerance_m=0.02)
    checks, status, requires_review, rationale = validator.validate_tier_3_lifecycle(
        wall, record, previous_status=None
    )
    
    print(f"\nTier 3 Checks: {len(checks)} total")
    for check in checks:
        status_icon = "✅ PASS" if check.passed else "❌ FAIL"
        print(f"  {status_icon} - {check.name}")
        print(f"       {check.description}")
        if check.details:
            print(f"       {check.details}")
    
    print(f"\nOverall Status: {status.value}")
    print(f"Requires Review: {requires_review}")
    print(f"Rationale: {rationale}")
    
    passed = sum(1 for c in checks if c.passed)
    return passed == len(checks)


def test_full_validation():
    """Test complete 3-tier validation"""
    print("\n" + "="*70)
    print("TEST: Full 3-Tier Validation Pipeline")
    print("="*70)
    
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18"
    )
    
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True
    )
    
    validator = TieredValidator(thickness_tolerance_m=0.02)
    result = validator.validate_all(wall, record, previous_status=None)
    
    print(f"\nValidation Complete!")
    print(f"Total Checks: {len(result.all_checks)}")
    print(f"  Tier 1 (Link): {len(result.tier_1_link)} checks")
    print(f"  Tier 2 (Mapping): {len(result.tier_2_mapping)} checks")
    print(f"  Tier 3 (Lifecycle): {len(result.tier_3_lifecycle)} checks")
    
    print(f"\nResults:")
    print(f"  Passed: {result.passed_count}")
    print(f"  Failed: {result.failed_count}")
    print(f"  Pass Rate: {(result.passed_count/len(result.all_checks)*100):.1f}%")
    
    print(f"\nOverall Status: {result.overall_status.value}")
    print(f"Requires Review: {result.requires_review}")
    print(f"Rationale: {result.rationale}")
    print(f"Timestamp: {result.assessment_timestamp}")
    
    return True


def test_json_export():
    """Test JSON export functionality"""
    print("\n" + "="*70)
    print("TEST: JSON Export")
    print("="*70)
    
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18"
    )
    
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True
    )
    
    validator = TieredValidator()
    result = validator.validate_all(wall, record, previous_status=None)
    
    result_dict = result.to_dict()
    json_str = json.dumps(result_dict, indent=2)
    
    print(f"\nJSON Export Size: {len(json_str)} bytes")
    print(f"\nJSON Structure (first 500 chars):")
    print(json_str[:500] + "...")
    
    # Validate JSON can be parsed
    parsed = json.loads(json_str)
    print(f"\n✅ JSON is valid and contains {len(parsed)} top-level keys")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "#"*70)
    print("# IFC-VaBDat 3-Tier Validation Test Harness")
    print("#"*70)
    
    tests = [
        ("Tier 1: Link Validation", test_tier_1_link_validation),
        ("Tier 2: Mapping Validation", test_tier_2_mapping_validation),
        ("Tier 3: Lifecycle Validation", test_tier_3_lifecycle_validation),
        ("Full Validation Pipeline", test_full_validation),
        ("JSON Export", test_json_export),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "#"*70)
    print("# Test Summary")
    print("#"*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())

