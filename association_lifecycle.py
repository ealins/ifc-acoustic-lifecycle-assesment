from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS, SKOS, XSD

MAP = Namespace('https://example.org/hft-acoustic/mapping/vocab/')
STATUS = Namespace('https://example.org/hft-acoustic/mapping/status/')
BASE = 'https://example.org/hft-acoustic/'

STATUS_URI = {
    'ACCEPTABLE': STATUS['acceptable'],
    'AMBIGUOUS': STATUS['ambiguous'],
    'INVALID': STATUS['invalid'],
    'UNMATCHED': STATUS['unmatched'],
    'MULTIPLE_CANDIDATES': STATUS['multiple-candidates'],
    'BROKEN': STATUS['broken'],
    'SEMANTICALLY_STALE': STATUS['semantically-stale'],
}
REVIEW_STATUSES = {'AMBIGUOUS', 'INVALID', 'UNMATCHED', 'MULTIPLE_CANDIDATES', 'BROKEN', 'SEMANTICALLY_STALE'}

@dataclass
class WallEvidence:
    global_id: str
    name: str
    construction_family: str
    total_thickness_m: float | None
    material_evidence: list[str]
    model_version: str

@dataclass
class RecordEvidence:
    uri: str
    identifier: str
    assembly: str
    construction_family: str
    total_thickness_m: float | None
    record_version: str
    available: bool = True


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def safe_id(text: str) -> str:
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in text)


def wall_uri(global_id: str) -> URIRef:
    return URIRef(f'{BASE}ifc/element/{global_id}')


def wall_snapshot_uri(global_id: str, version: str) -> URIRef:
    return URIRef(f'{BASE}ifc/element/{global_id}/snapshot/{safe_id(version)}')


def record_snapshot_uri(record_uri: str, version: str) -> URIRef:
    return URIRef(f'{record_uri}/snapshot/{safe_id(version)}')


def series_uri(global_id: str, record_id: str) -> URIRef:
    return URIRef(f'{BASE}mapping/series/{safe_id(global_id)}--{safe_id(record_id)}')


def assertion_uri(global_id: str, record_id: str, revision: int) -> URIRef:
    return URIRef(f'{BASE}mapping/assertion/{safe_id(global_id)}--{safe_id(record_id)}-r{revision}')


def activity_uri(global_id: str, record_id: str, revision: int) -> URIRef:
    return URIRef(f'{BASE}mapping/activity/{safe_id(global_id)}--{safe_id(record_id)}-validation-r{revision}')


def status_name(g: Graph, assertion: URIRef | None) -> str | None:
    if assertion is None:
        return None
    s = g.value(assertion, MAP.status)
    if s is None:
        return None
    label = g.value(s, SKOS.prefLabel)
    return str(label) if label else str(s).rsplit('/', 1)[-1].upper()


def next_revision(g: Graph, series: URIRef) -> int:
    current = g.value(series, MAP.currentAssertion)
    if current is None:
        return 1
    tail = str(current).rsplit('-r', 1)[-1]
    try:
        return int(tail) + 1
    except Exception:
        return 1 + sum(1 for _ in g.subjects(RDF.type, MAP.MappingAssertion))


def semantic_assessment(w: WallEvidence, r: RecordEvidence, previous_status: str | None = None,
                        thickness_tolerance_m: float = 0.02) -> tuple[str, str]:
    if not r.available:
        return 'BROKEN', 'The IFC-side identifier is retained, but the referenced external acoustic record is unavailable.'
    if not w.construction_family or w.construction_family == 'unknown':
        return 'AMBIGUOUS', 'IFC construction-family evidence is insufficient for a semantic correspondence assessment.'
    if not r.construction_family or r.construction_family == 'unknown':
        return 'AMBIGUOUS', 'External record construction-family evidence is insufficient for a semantic correspondence assessment.'
    if w.construction_family != r.construction_family:
        base = f'Construction-family mismatch: IFC={w.construction_family}, record={r.construction_family}.'
        if previous_status == 'ACCEPTABLE':
            return 'SEMANTICALLY_STALE', 'A previously acceptable association no longer matches the current IFC construction evidence. ' + base
        return 'INVALID', base
    reasons: list[str] = []
    if w.total_thickness_m is not None and r.total_thickness_m is not None:
        delta = abs(w.total_thickness_m - r.total_thickness_m)
        if delta > thickness_tolerance_m:
            reasons.append(f'total-thickness difference {delta:.3f} m exceeds {thickness_tolerance_m:.3f} m tolerance')
    if not w.material_evidence:
        reasons.append('IFC material/layer evidence is incomplete')
    if reasons:
        return 'AMBIGUOUS', '; '.join(reasons) + '.'
    return 'ACCEPTABLE', 'Construction family agrees and the available thickness/material evidence is compatible with the record.'


def add_wall_snapshot(g: Graph, w: WallEvidence) -> URIRef:
    stable = wall_uri(w.global_id)
    snap = wall_snapshot_uri(w.global_id, w.model_version)
    g.add((stable, RDF.type, PROV.Entity))
    g.add((stable, MAP.ifcGlobalId, Literal(w.global_id)))
    g.add((snap, RDF.type, MAP.IFCElementSnapshot))
    g.add((snap, PROV.specializationOf, stable))
    g.add((snap, MAP.ifcGlobalId, Literal(w.global_id)))
    g.add((snap, DCTERMS.title, Literal(w.name)))
    g.add((snap, MAP.ifcModelVersion, Literal(w.model_version)))
    g.add((snap, MAP.constructionFamily, Literal(w.construction_family)))
    if w.total_thickness_m is not None:
        g.add((snap, MAP.totalThickness_m, Literal(w.total_thickness_m, datatype=XSD.decimal)))
    for m in w.material_evidence:
        g.add((snap, MAP.materialEvidence, Literal(m)))
    return snap


def add_record_snapshot(g: Graph, r: RecordEvidence) -> URIRef:
    stable = URIRef(r.uri)
    snap = record_snapshot_uri(r.uri, r.record_version)
    g.add((stable, RDF.type, PROV.Entity))
    g.add((snap, RDF.type, MAP.AcousticRecordSnapshot))
    g.add((snap, PROV.specializationOf, stable))
    g.add((snap, DCTERMS.identifier, Literal(r.identifier)))
    g.add((snap, MAP.recordVersion, Literal(r.record_version)))
    g.add((snap, MAP.recordAssembly, Literal(r.assembly)))
    g.add((snap, MAP.recordConstructionFamily, Literal(r.construction_family)))
    if r.total_thickness_m is not None:
        g.add((snap, MAP.recordTotalThickness_m, Literal(r.total_thickness_m, datatype=XSD.decimal)))
    g.add((snap, MAP.technicalResolution, Literal(r.available, datatype=XSD.boolean)))
    return snap


def create_assertion(g: Graph, w: WallEvidence, r: RecordEvidence, *, trigger: str,
                     agent_uri: str = f'{BASE}agent/thesis-workflow', link_carrier: str = 'IfcDocumentReference',
                     ifc_reference_location: str | None = None, assessed_at: str | None = None,
                     status_override: str | None = None, rationale_override: str | None = None,
                     wall_evidence_hash: str | None = None, record_evidence_hash: str | None = None) -> URIRef:
    series = series_uri(w.global_id, r.identifier)
    previous = g.value(series, MAP.currentAssertion)
    previous_status = status_name(g, previous)
    status, rationale = semantic_assessment(w, r, previous_status=previous_status)
    if status_override is not None:
        if status_override not in STATUS_URI:
            raise ValueError(f'Unknown status_override: {status_override}')
        status = status_override
    if rationale_override is not None:
        rationale = rationale_override
    rev = next_revision(g, series)
    assertion = assertion_uri(w.global_id, r.identifier, rev)
    activity = activity_uri(w.global_id, r.identifier, rev)
    wall_snap = add_wall_snapshot(g, w)
    record_snap = add_record_snapshot(g, r)
    timestamp = assessed_at or now_iso()

    g.add((series, RDF.type, MAP.MappingSeries))
    g.add((series, MAP.ifcElement, wall_uri(w.global_id)))
    g.add((series, MAP.acousticRecord, URIRef(r.uri)))
    if previous is not None:
        g.remove((series, MAP.currentAssertion, previous))
    g.add((series, MAP.currentAssertion, assertion))

    g.add((assertion, RDF.type, MAP.MappingAssertion))
    g.add((assertion, MAP.ifcElement, wall_uri(w.global_id)))
    g.add((assertion, MAP.acousticRecord, URIRef(r.uri)))
    g.add((assertion, MAP.status, STATUS_URI[status]))
    g.add((assertion, MAP.rationale, Literal(rationale)))
    g.add((assertion, MAP.validationBasis, Literal('construction family; total thickness; available IFC material/layer evidence; record availability')))
    g.add((assertion, MAP.ifcModelVersion, Literal(w.model_version)))
    g.add((assertion, MAP.recordVersion, Literal(r.record_version)))
    g.add((assertion, MAP.technicalResolution, Literal(r.available, datatype=XSD.boolean)))
    g.add((assertion, MAP.requiresReview, Literal(status in REVIEW_STATUSES, datatype=XSD.boolean)))
    g.add((assertion, MAP.assessedAt, Literal(timestamp, datatype=XSD.dateTime)))
    g.add((assertion, MAP.linkCarrier, Literal(link_carrier)))
    g.add((assertion, MAP.ifcReferenceLocation, Literal(ifc_reference_location or r.uri, datatype=XSD.anyURI)))
    if wall_evidence_hash:
        g.add((assertion, MAP.wallEvidenceHash, Literal(wall_evidence_hash)))
    if record_evidence_hash:
        g.add((assertion, MAP.recordEvidenceHash, Literal(record_evidence_hash)))
    if previous_status:
        g.add((assertion, MAP.previousStatus, Literal(previous_status)))
    if previous is not None:
        g.add((assertion, PROV.wasRevisionOf, previous))

    g.add((activity, RDF.type, MAP.ValidationActivity))
    g.add((activity, PROV.used, wall_snap))
    g.add((activity, PROV.used, record_snap))
    g.add((activity, PROV.wasAssociatedWith, URIRef(agent_uri)))
    g.add((activity, MAP.trigger, Literal(trigger)))
    g.add((activity, PROV.endedAtTime, Literal(timestamp, datatype=XSD.dateTime)))
    g.add((assertion, PROV.wasGeneratedBy, activity))
    g.add((URIRef(agent_uri), RDF.type, PROV.Agent))
    return assertion


def load_graph(path: Path | None, schema: Path | None = None) -> Graph:
    g = Graph()
    if schema and schema.exists():
        g.parse(schema, format='turtle')
    if path and path.exists():
        g.parse(path, format='turtle')
    return g


def save_graph(g: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(path, format='turtle')


def current_rows(g: Graph) -> list[dict]:
    rows=[]
    for series in g.subjects(RDF.type, MAP.MappingSeries):
        assertion = g.value(series, MAP.currentAssertion)
        if assertion is None: continue
        rows.append({
            'series': str(series),
            'ifc_global_id': str(g.value(assertion, MAP.ifcElement)).rsplit('/',1)[-1],
            'record_uri': str(g.value(assertion, MAP.acousticRecord)),
            'status': status_name(g, assertion),
            'ifc_model_version': str(g.value(assertion, MAP.ifcModelVersion) or ''),
            'record_version': str(g.value(assertion, MAP.recordVersion) or ''),
            'technical_resolution': str(g.value(assertion, MAP.technicalResolution) or ''),
            'requires_review': str(g.value(assertion, MAP.requiresReview) or ''),
            'rationale': str(g.value(assertion, MAP.rationale) or ''),
            'assertion': str(assertion),
        })
    return rows


def history_rows(g: Graph, series: URIRef) -> list[dict]:
    rows=[]
    for assertion in g.subjects(RDF.type, MAP.MappingAssertion):
        if g.value(assertion, MAP.ifcElement) != g.value(series, MAP.ifcElement): continue
        if g.value(assertion, MAP.acousticRecord) != g.value(series, MAP.acousticRecord): continue
        rows.append({
            'assertion': str(assertion),
            'status': status_name(g, assertion),
            'model_version': str(g.value(assertion, MAP.ifcModelVersion) or ''),
            'record_version': str(g.value(assertion, MAP.recordVersion) or ''),
            'assessed_at': str(g.value(assertion, MAP.assessedAt) or ''),
            'rationale': str(g.value(assertion, MAP.rationale) or ''),
            'revision_of': str(g.value(assertion, PROV.wasRevisionOf) or ''),
        })
    rows.sort(key=lambda r: r['assertion'])
    return rows


def structural_check(g: Graph) -> list[str]:
    errors: list[str] = []
    required_assertion = [MAP.ifcElement, MAP.acousticRecord, MAP.status, MAP.rationale,
                          MAP.ifcModelVersion, MAP.recordVersion, MAP.technicalResolution,
                          MAP.requiresReview, MAP.assessedAt, PROV.wasGeneratedBy]
    for a in g.subjects(RDF.type, MAP.MappingAssertion):
        for p in required_assertion:
            if g.value(a, p) is None:
                errors.append(f"{a} missing required property {p}")
    for s in g.subjects(RDF.type, MAP.MappingSeries):
        for p in [MAP.ifcElement, MAP.acousticRecord, MAP.currentAssertion]:
            vals = list(g.objects(s, p))
            if len(vals) != 1:
                errors.append(f"{s} requires exactly one {p}; found {len(vals)}")
    for act in g.subjects(RDF.type, MAP.ValidationActivity):
        if len(list(g.objects(act, PROV.used))) < 2:
            errors.append(f"{act} must use at least two evidence snapshots")
        for p in [PROV.wasAssociatedWith, MAP.trigger, PROV.endedAtTime]:
            if g.value(act, p) is None:
                errors.append(f"{act} missing required property {p}")
    return errors


def build_demo(out: Path, schema: Path) -> None:
    g = load_graph(None, schema)
    wall = WallEvidence(
        global_id='2qL6OSUnz6ZAzEOn1HxeD2',
        name='Walls : Walls_3OGArc01 : Walls_3OGArc01',
        construction_family='metal_frame',
        total_thickness_m=0.285,
        material_evidence=['Metal Stud Layer'],
        model_version='bau1-2026-02-18',
    )
    record = RecordEvidence(
        uri=f'{BASE}record/vabdat-310', identifier='vabdat-310',
        assembly='B_bGP12_frM75||iMW60_bGP12', construction_family='metal_frame',
        total_thickness_m=0.100, record_version='prototype-v1', available=True,
    )
    create_assertion(g, wall, record, trigger='initial-validation', assessed_at='2026-08-19T00:00:00+02:00')

    # Acoustic record revision. The link URI remains stable; the assessed record version changes.
    record2 = RecordEvidence(**{**record.__dict__, 'record_version': 'prototype-v2'})
    create_assertion(g, wall, record2, trigger='acoustic-record-version-update', assessed_at='2026-08-19T00:10:00+02:00')

    # Resource unavailable with unchanged IFC-side Location/URI.
    record_down = RecordEvidence(**{**record2.__dict__, 'available': False})
    create_assertion(g, wall, record_down, trigger='external-resource-unavailable', assessed_at='2026-08-19T00:20:00+02:00')

    # Resource restored; revalidate against the same current versions.
    create_assertion(g, wall, record2, trigger='external-resource-restored', assessed_at='2026-08-19T00:30:00+02:00')

    save_graph(g, out)
    summary = {
        'current': current_rows(g),
        'history': history_rows(g, series_uri(wall.global_id, record.identifier)),
    }
    out.with_suffix('.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Lifecycle manager for IFC-to-external-acoustic mapping assertions.')
    parser.add_argument('--graph', type=Path, help='Association graph TTL file.')
    parser.add_argument('--schema', type=Path, default=Path(__file__).with_name('association_model_schema.ttl'))
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_demo = sub.add_parser('demo', help='Generate a versioned demonstration graph from the Bau 1 / VaBDat pilot association.')
    p_demo.add_argument('--out', type=Path, default=Path('association_lifecycle_demo.ttl'))

    sub.add_parser('current', help='Show current mapping assertions.')
    sub.add_parser('check', help='Check required lifecycle-graph structure without extra dependencies.')
    p_hist = sub.add_parser('history', help='Show history for one wall/record mapping series.')
    p_hist.add_argument('--global-id', required=True)
    p_hist.add_argument('--record-id', required=True)

    p_val = sub.add_parser('validate', help='Create a new versioned mapping assertion from supplied evidence.')
    p_val.add_argument('--global-id', required=True)
    p_val.add_argument('--wall-name', default='')
    p_val.add_argument('--wall-family', required=True)
    p_val.add_argument('--wall-thickness', type=float)
    p_val.add_argument('--wall-material', action='append', default=[])
    p_val.add_argument('--model-version', required=True)
    p_val.add_argument('--record-uri', required=True)
    p_val.add_argument('--record-id', required=True)
    p_val.add_argument('--record-assembly', default='')
    p_val.add_argument('--record-family', required=True)
    p_val.add_argument('--record-thickness', type=float)
    p_val.add_argument('--record-version', required=True)
    p_val.add_argument('--unavailable', action='store_true')
    p_val.add_argument('--trigger', default='manual-validation')
    p_val.add_argument('--link-carrier', default='IfcDocumentReference')

    args = parser.parse_args()
    if args.cmd == 'demo':
        build_demo(args.out, args.schema)
        print(f'Wrote {args.out}')
        print(f'Wrote {args.out.with_suffix(".json")}')
        return

    if not args.graph:
        parser.error('--graph is required for this command')
    g = load_graph(args.graph, args.schema)
    if args.cmd == 'current':
        print(json.dumps(current_rows(g), indent=2))
    elif args.cmd == 'check':
        errors = structural_check(g)
        print(json.dumps({'conforms': not errors, 'errors': errors}, indent=2))
    elif args.cmd == 'history':
        print(json.dumps(history_rows(g, series_uri(args.global_id, args.record_id)), indent=2))
    elif args.cmd == 'validate':
        w = WallEvidence(args.global_id, args.wall_name, args.wall_family, args.wall_thickness,
                         args.wall_material, args.model_version)
        r = RecordEvidence(args.record_uri, args.record_id, args.record_assembly, args.record_family,
                           args.record_thickness, args.record_version, not args.unavailable)
        a = create_assertion(g, w, r, trigger=args.trigger, link_carrier=args.link_carrier)
        save_graph(g, args.graph)
        print(json.dumps({'created_assertion': str(a), 'current': current_rows(g)}, indent=2))

if __name__ == '__main__':
    main()
