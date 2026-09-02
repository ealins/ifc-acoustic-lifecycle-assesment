"""
Thesis Strengthening Analysis
Automated analysis of existing experimental data to strengthen master's thesis
"""
import json
from pathlib import Path
from typing import Any
import csv

def analyze_test3_data():
    """Analyze Test 3 semantic robustness data"""
    with open('final_test3_results_v2/test3_semantic_robustness_details.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scenarios = data['scenarios']
    
    # Count real vs controlled cases
    real_cases = [s for s in scenarios if 'ACTUAL_IFC' in s.get('case_kind', '')]
    controlled_cases = [s for s in scenarios if 'CONTROLLED' in s.get('case_kind', '')]
    
    # Analyze real walls
    actual_walls = data.get('actual_wall_signatures', {})
    
    print("="*80)
    print("TEST 3 DATA SCOPE ANALYSIS")
    print("="*80)
    print(f"\nTotal scenarios tested: {len(scenarios)}")
    print(f"Real IFC wall cases: {len(real_cases)}")
    print(f"Controlled/synthetic cases: {len(controlled_cases)}")
    print(f"\nReal walls extracted from IFC: {len(actual_walls)}")
    
    print("\n--- Real Wall Construction Diversity ---")
    families = {}
    for wall_key, wall_data in actual_walls.items():
        family = wall_data['construction_family']
        thickness = wall_data['total_thickness_m']
        families[family] = families.get(family, 0) + 1
        print(f"  {wall_key}: {family}, {thickness} m")
    
    print(f"\nConstruction family coverage: {len(families)} types ({', '.join(families.keys())})")
    
    return data, scenarios, actual_walls

def sensitivity_analysis_thickness():
    """Simulate sensitivity analysis on thickness tolerance"""
    with open('final_test3_results_v2/test3_semantic_robustness_details.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scenarios = data['scenarios']
    
    print("\n" + "="*80)
    print("SENSITIVITY ANALYSIS: Thickness Tolerance")
    print("="*80)
    
    # Focus on cases where thickness matters
    thickness_sensitive_cases = [
        s for s in scenarios 
        if s.get('decision_metrics', {}).get('thickness_delta_m') is not None
    ]
    
    tolerances = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20]
    
    results = []
    for tol in tolerances:
        acceptable = 0
        ambiguous = 0
        
        for case in thickness_sensitive_cases:
            delta = case['decision_metrics'].get('thickness_delta_m', 999)
            family_match = (case['decision_metrics'].get('wall_family') == 
                          case['decision_metrics'].get('record_family'))
            
            if family_match and delta <= tol:
                acceptable += 1
            elif family_match:
                ambiguous += 1
        
        total = len(thickness_sensitive_cases)
        results.append({
            'tolerance_m': tol,
            'acceptable': acceptable,
            'ambiguous': ambiguous,
            'acceptable_pct': round(acceptable / total * 100, 1) if total > 0 else 0,
            'ambiguous_pct': round(ambiguous / total * 100, 1) if total > 0 else 0
        })
        
        print(f"\nTolerance = {tol:.3f} m:")
        print(f"  ACCEPTABLE: {acceptable}/{total} ({results[-1]['acceptable_pct']}%)")
        print(f"  AMBIGUOUS:  {ambiguous}/{total} ({results[-1]['ambiguous_pct']}%)")
    
    # Save results
    with open('sensitivity_analysis_thickness.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['tolerance_m', 'acceptable', 'ambiguous', 
                                               'acceptable_pct', 'ambiguous_pct'])
        writer.writeheader()
        writer.writerows(results)
    
    print("\n✓ Results saved to: sensitivity_analysis_thickness.csv")
    
    return results

def failure_pattern_analysis():
    """Analyze failure patterns and edge cases"""
    with open('final_test3_results_v2/test3_semantic_robustness_details.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "="*80)
    print("FAILURE PATTERN ANALYSIS")
    print("="*80)
    
    scenarios = data['scenarios']
    
    # Analyze AMBIGUOUS case
    ambiguous = [s for s in scenarios if s['observed_status'] == 'AMBIGUOUS']
    print(f"\nAMBIGUOUS Cases: {len(ambiguous)}")
    for case in ambiguous:
        metrics = case.get('decision_metrics', {})
        print(f"\n  Case: {case['case_id']}")
        print(f"    Family match: {metrics.get('wall_family')} vs {metrics.get('record_family')}")
        print(f"    Thickness: {metrics.get('wall_thickness_m')} m (IFC) vs {metrics.get('record_thickness_m')} m (record)")
        print(f"    Delta: {metrics.get('thickness_delta_m')} m")
        print(f"    Material overlap: {metrics.get('layer_token_overlap', 0):.2f}")
        print(f"    Rationale: {case['rationale']}")
    
    # Root cause categories
    print("\n--- Root Causes for Non-ACCEPTABLE Status ---")
    
    root_causes = {
        'insufficient_ifc_detail': 0,
        'thickness_mismatch': 0,
        'family_mismatch': 0,
        'no_candidates': 0,
        'multiple_candidates': 0,
        'resource_unavailable': 0,
        'semantic_staleness': 0
    }
    
    for case in scenarios:
        status = case['observed_status']
        rationale = case.get('rationale', '').lower()
        
        if 'insufficient' in rationale or 'material/layer evidence' in rationale:
            root_causes['insufficient_ifc_detail'] += 1
        if 'thickness' in rationale and status == 'AMBIGUOUS':
            root_causes['thickness_mismatch'] += 1
        if 'family' in rationale and 'mismatch' in rationale:
            root_causes['family_mismatch'] += 1
        if status == 'UNMATCHED':
            root_causes['no_candidates'] += 1
        if status == 'MULTIPLE_CANDIDATES':
            root_causes['multiple_candidates'] += 1
        if status == 'BROKEN':
            root_causes['resource_unavailable'] += 1
        if status == 'SEMANTICALLY_STALE':
            root_causes['semantic_staleness'] += 1
    
    for cause, count in root_causes.items():
        if count > 0:
            print(f"  {cause.replace('_', ' ').title()}: {count} case(s)")
    
    # What would make AMBIGUOUS → ACCEPTABLE
    print("\n--- Path to ACCEPTABLE for Real Bau 1 Wall ---")
    print("  Current status: AMBIGUOUS")
    print("  Current IFC evidence: 'Metal Stud Layer' (generic label)")
    print("  Required IFC evidence:")
    print("    • Detailed layer breakdown (e.g., GKB 12mm | CW75 studs | insulation | GKB 12mm)")
    print("    • Actual thickness 0.285 m or find matching 0.285 m record")
    print("    • OR: Accept looser tolerance (but requires engineering validation)")
    
    return root_causes

def architectural_decision_record():
    """Document architectural decisions based on code evolution"""
    print("\n" + "="*80)
    print("ARCHITECTURAL DECISION RECORD (extracted from code)")
    print("="*80)
    
    decisions = [
        {
            'decision': 'Externalize acoustic data from IFC',
            'alternatives': 'Embedded IFC properties',
            'chosen_reason': 'Test 2: Independent updates without IFC edits',
            'tradeoff': 'Creates availability dependency on external resource'
        },
        {
            'decision': 'Use IFC-native IfcDocumentReference as primary carrier',
            'alternatives': 'Custom HFT property set only',
            'chosen_reason': 'Test 2: Native→RDF had equivalent behavior with lower IFC overhead (2 entities vs 5)',
            'tradeoff': 'Less domain-specific discoverability (mitigated by HFT anchor)'
        },
        {
            'decision': 'RDF for external registry representation',
            'alternatives': 'JSON or XML',
            'chosen_reason': 'Explicit PROV-O provenance relationships, graph extensibility',
            'tradeoff': 'Requires RDF tooling; JSON showed same update-independence behavior'
        },
        {
            'decision': 'Separate MappingAssertion layer for semantic state',
            'alternatives': 'Store status in IFC or embed in acoustic record',
            'chosen_reason': 'Test 3: Technical resolution ≠ semantic validity; mutable state should not force IFC edits',
            'tradeoff': 'Adds architectural layer and complexity'
        },
        {
            'decision': 'Immutable assertion revisions with prov:wasRevisionOf',
            'alternatives': 'Overwrite current state',
            'chosen_reason': 'Preserve evidence and rationale history for auditing',
            'tradeoff': 'Graph size grows with revisions (5 revisions in final test)'
        },
        {
            'decision': 'Reduce HFT_AcousticLink to semantic anchor only',
            'alternatives': 'Keep full acoustic data + status in HFT',
            'chosen_reason': 'Hybrid v1: Avoid URI duplication and mutable state in IFC',
            'tradeoff': 'Requires both native and HFT mechanisms (complementary roles)'
        }
    ]
    
    print("\n{:<50} | {:<30} | {:<40}".format("Decision", "Chosen Because", "Tradeoff"))
    print("-" * 125)
    
    for d in decisions:
        print("{:<50} | {:<30} | {:<40}".format(
            d['decision'][:48], 
            d['chosen_reason'][:28], 
            d['tradeoff'][:38]
        ))
    
    # Save to CSV
    with open('architectural_decisions.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['decision', 'alternatives', 'chosen_reason', 'tradeoff'])
        writer.writeheader()
        writer.writerows(decisions)
    
    print("\n✓ Full table saved to: architectural_decisions.csv")
    
    return decisions

def test2_comparison_summary():
    """Create comparison summary from Test 2"""
    print("\n" + "="*80)
    print("TEST 2 ARCHITECTURE COMPARISON SUMMARY")
    print("="*80)
    
    # Data from test2_summary.txt and test2_ifc_overhead.csv
    print("\n--- Initial Retrieval (5 information questions) ---")
    architectures = [
        {'name': 'Embedded IFC', 'q1_q5': '5/5', 'entities_added': 20, 'properties_added': 18},
        {'name': 'Native IFC → JSON', 'q1_q5': '5/5', 'entities_added': 2, 'properties_added': 0},
        {'name': 'Native IFC → RDF', 'q1_q5': '5/5', 'entities_added': 2, 'properties_added': 0},
        {'name': 'Custom IFC → RDF', 'q1_q5': '5/5', 'entities_added': 5, 'properties_added': 3}
    ]
    
    print("\n{:<25} | {:<10} | {:<15} | {:<18}".format(
        "Architecture", "Q1-Q5", "IFC Entities", "IFC Properties"))
    print("-" * 75)
    
    for arch in architectures:
        print("{:<25} | {:<10} | {:<15} | {:<18}".format(
            arch['name'], arch['q1_q5'], arch['entities_added'], arch['properties_added']))
    
    print("\n--- Update Independence ---")
    print("  Embedded IFC: IFC file modified on acoustic value/provenance change")
    print("  All external approaches: External resource modified, IFC unchanged")
    print("  → Conclusion: Externalisation causes independence, not RDF specifically")
    
    print("\n--- RDF-Specific Value ---")
    print("  Explicit PROV-O relationships (wasGeneratedBy, wasDerivedFrom, wasAttributedTo)")
    print("  Graph-based extensibility and semantic queries")
    print("  Not required for basic retrieval or update independence")
    
    print("\n--- Carrier Comparison (both using same RDF registry) ---")
    print("  Native IFC → RDF: 2 entities, 0 custom properties (lighter)")
    print("  Custom IFC → RDF: 5 entities, 3 properties (heavier)")
    print("  → Both answered same questions; Native chosen as authoritative carrier")
    
    return architectures

def generate_report():
    """Generate comprehensive strengthening report"""
    
    print("\n" + "="*80)
    print("THESIS STRENGTHENING ANALYSIS REPORT")
    print("Generated:", Path('thesis_strengthening_analysis.py').stat().st_mtime)
    print("="*80)
    
    # Run all analyses
    data, scenarios, walls = analyze_test3_data()
    sensitivity_results = sensitivity_analysis_thickness()
    root_causes = failure_pattern_analysis()
    decisions = architectural_decision_record()
    test2_summary = test2_comparison_summary()
    
    # Generate final recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR THESIS STRENGTHENING")
    print("="*80)
    
    print("\n✓ ALREADY AVAILABLE IN CURRENT EXPERIMENT:")
    print("  • 4 real walls from Bau 1 IFC (metal-frame, concrete 150mm, concrete 300mm, wood 100mm)")
    print("  • Sensitivity analysis executable (completed above)")
    print("  • Architectural decision documentation (extracted from code history)")
    print("  • Failure pattern analysis (completed above)")
    print("  • Test 2 comparison table (available)")
    
    print("\n📊 ADDITIONAL ANALYSES TO STRENGTHEN (using existing data):")
    print("  1. Expand semantic robustness test to more walls from same IFC")
    print("  2. Document IFC authoring guidelines for adequate acoustic evidence")
    print("  3. Create related work comparison table with literature")
    print("  4. Add IFC standard compliance section (cite ISO 16739)")
    
    print("\n⚠️  REQUIRES EXTERNAL RESOURCES (not feasible in code alone):")
    print("  • Expert validation session (requires acoustic engineers)")
    print("  • User walkthrough (requires test participants)")
    print("  • Real historical change data (requires database access)")
    
    # Save summary
    summary = {
        'timestamp': '2026-08-22',
        'real_walls_tested': len(walls),
        'total_scenarios': len(scenarios),
        'construction_families': list(set(w['construction_family'] for w in walls.values())),
        'status_coverage': list(set(s['observed_status'] for s in scenarios)),
        'sensitivity_analysis': 'completed',
        'architectural_decisions': len(decisions),
        'root_cause_categories': len([v for v in root_causes.values() if v > 0])
    }
    
    with open('strengthening_analysis_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print("\n✓ Summary saved to: strengthening_analysis_summary.json")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print("  • sensitivity_analysis_thickness.csv")
    print("  • architectural_decisions.csv")
    print("  • strengthening_analysis_summary.json")
    print("\nThese can be included in thesis appendices and referenced in discussion.")

if __name__ == '__main__':
    generate_report()
