"""
Test harness for 3-tier validation using demo data.

Tests the complete validation pipeline with association_lifecycle_demo.json.
The functions are valid pytest tests and can also be run as a standalone harness.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from association_lifecycle import RecordEvidence, WallEvidence
from dashboard.backend.validators import TieredValidator


def _evidence():
    wall = WallEvidence(
        global_id="2qL6OSUnz6ZAzEOn1HxeD2",
        name="Wall_001",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        material_evidence=["Brick", "Mortar", "Insulation"],
        model_version="bau1-2026-02-18",
    )
    record = RecordEvidence(
        uri="https://example.org/hft-acoustic/record/vabdat-310",
        identifier="vabdat-310",
        assembly="Exterior Wall Assembly",
        construction_family="Masonry Wall",
        total_thickness_m=0.185,
        record_version="prototype-v2",
        available=True,
    )
    return wall, record


def _print_checks(title, checks):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"  {status} - {check.name}")
        print(f"       {check.description}")
        if check.details:
            print(f"       {check.details}")


def test_tier_1_link_validation():
    """Test Tier 1: Link Validation."""
    wall, record = _evidence()
    checks = TieredValidator().validate_tier_1_link(wall, record)
    _print_checks("TEST: Tier 1 - Link Validation", checks)
    assert checks, "Tier 1 returned no validation checks"
    assert all(check.passed for check in checks)


def test_tier_2_mapping_validation():
    """Test Tier 2: Mapping Validation."""
    wall, record = _evidence()
    checks = TieredValidator().validate_tier_2_mapping(wall, record)
    _print_checks("TEST: Tier 2 - Mapping Validation", checks)
    assert checks, "Tier 2 returned no validation checks"
    assert all(check.passed for check in checks)


def test_tier_3_lifecycle_validation():
    """Test Tier 3: Lifecycle Validation."""
    wall, record = _evidence()
    checks, status, requires_review, rationale = TieredValidator(
        thickness_tolerance_m=0.02
    ).validate_tier_3_lifecycle(wall, record, previous_status=None)
    _print_checks("TEST: Tier 3 - Lifecycle Validation", checks)
    print(f"Overall Status: {status.value}")
    print(f"Requires Review: {requires_review}")
    print(f"Rationale: {rationale}")
    assert checks, "Tier 3 returned no validation checks"
    assert all(check.passed for check in checks)


def test_full_validation():
    """Test complete 3-tier validation."""
    wall, record = _evidence()
    result = TieredValidator(thickness_tolerance_m=0.02).validate_all(
        wall, record, previous_status=None
    )
    print("\n" + "=" * 70)
    print("TEST: Full 3-Tier Validation Pipeline")
    print("=" * 70)
    print(f"Total Checks: {len(result.all_checks)}")
    print(f"Passed: {result.passed_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Overall Status: {result.overall_status.value}")
    print(f"Requires Review: {result.requires_review}")
    print(f"Rationale: {result.rationale}")
    assert result.all_checks, "Full validation returned no checks"
    assert result.failed_count == 0
    assert result.passed_count == len(result.all_checks)


def test_json_export():
    """Test JSON export functionality."""
    wall, record = _evidence()
    result = TieredValidator().validate_all(wall, record, previous_status=None)
    result_dict = result.to_dict()
    json_str = json.dumps(result_dict, indent=2)
    parsed = json.loads(json_str)
    print(f"JSON Export Size: {len(json_str)} bytes")
    assert isinstance(parsed, dict)
    assert parsed
    assert parsed.get("overall_status") == result.overall_status.value


def main():
    """Run all tests as a standalone demonstration harness."""
    print("\n" + "#" * 70)
    print("# IFC-VaBDat 3-Tier Validation Test Harness")
    print("#" * 70)
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
            test_func()
            results[test_name] = True
        except Exception as exc:
            print(f"\nERROR: {exc}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    print("\n" + "#" * 70)
    print("# Test Summary")
    print("#" * 70)
    passed = sum(1 for value in results.values() if value)
    total = len(results)
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{status} - {test_name}")
    print(f"\nTotal: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
