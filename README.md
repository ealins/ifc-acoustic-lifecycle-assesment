# MappingSeries Lifecycle Validator

> An interactive Streamlit research prototype for validating and auditing the lifecycle link between IFC building elements and external RDF acoustic-performance records.

## What this is

The **MappingSeries Lifecycle Validator** demonstrates how an IFC wall can remain associated with the correct external acoustic record as either source changes over time. It combines native IFC document references, an optional stable MappingSeries URI, IDS-style evidence-readiness checks, bSDD-style terminology alignment, RDF data validation, and PROV-style immutable revision history in one explainable workflow.

### At a glance

| Area | What the application does |
| --- | --- |
| IFC evidence | Uses element identity, construction family, thickness, materials, and native/Pset record links. |
| RDF evidence | Checks record identity, acoustic `Rw` value and unit, assembly, source, report, provenance, and availability. |
| Validation | Separates technical link resolution from semantic data compatibility instead of treating a resolvable URI as sufficient evidence. |
| Lifecycle | Creates immutable `MappingAssertion` revisions, snapshots, change events, and reviewer decisions without overwriting history. |
| Interface | Provides editable presets, real-IFC extraction, decision details, a revision timeline, and a provenance graph. |

The application is a **thesis/research prototype**, not an acoustic simulation or laboratory measurement tool. Its purpose is to test a governed association-and-validation architecture and make every acceptance decision traceable.

## Quick start

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open <http://localhost:8501>.

## Research goal

The prototype makes the architecture visible: IFC evidence, a native IFC record link, optional MappingSeries routing, IDS evidence readiness, bSDD-style terminology alignment, RDF evidence, and an append-only MappingAssertion lifecycle.

## Acceptance logic

Acceptance is deliberately conjunctive, not based on URI resolution alone:

`ACCEPTABLE = Link decision RESOLVED AND RDF data decision PASS AND IDS PASS AND bSDD alignment not UNALIGNED AND target approved`

The link decision requires a matching, available native URI and, when enabled, a passing MappingSeries URI. The RDF data decision requires record identity, matching construction family, thickness within tolerance, a numeric `Rw` value, `dB` units, assembly, source, report, provenance, and availability. A changed record therefore creates a new revision; it remains acceptable only when the replacement data passes the same checks. This follows the buildingSMART IDS model of explicit, machine-interpretable requirements and automated compliance results, while the revision snapshots follow PROV-O-style entity/activity provenance.

Changing the record target itself is a separate lifecycle condition: a changed native URI, MappingSeries URI, RDF record URI, or RDF record ID produces `UNMATCHED` and requires explicit reviewer approval, even if the replacement record passes all data checks. This prevents a valid but unreviewed replacement record from silently becoming the accepted association.

A **MappingSeries** is the stable wall-record association anchor derived from the IFC GlobalId and RDF record id. A **MappingAssertion** is one immutable, timestamped assessment revision. It records snapshots, validation results, rationale, review state, and change events without overwriting earlier revisions.

IFC-side fields represent identity, construction evidence, native document location, and optional semantic-routing evidence. RDF-side fields own acoustic performance, assembly, source, report, provenance, and availability. The native link checks URI equality and record availability. MappingSeries checks the expected derived URI. IDS is simulated as required and optional field readiness. bSDD alignment is simulated with a small local concept map.

The app includes five selectable wall/component presets and five selectable acoustic-record presets based on component identifiers, construction types, assemblies, and thicknesses listed by [VaBDat Bauteile](https://www.vabdat.de/Bauteil/). The listing does not expose five acoustic `Rw` measurements in its table, so the five `Rw` values are clearly marked prototype sample values. Select a preset, then edit every IFC or RDF registry field directly in the evidence workspace.

Technical resolution is intentionally separate from semantic validity: a URI can resolve while evidence is ambiguous or contradictory. A changed or unavailable record creates a new MappingAssertion; an identical rerun creates no new assertion. The timeline and graph show revisions, snapshots, activities, and change events.

## Proposed architecture

The architecture is a five-layer validation pipeline:

1. **Identity and association:** IFC GlobalId, native `IfcDocumentReference.Location`, RDF record URI/ID, and the derived MappingSeries URI.
2. **Evidence:** immutable IFC and RDF snapshots captured at assessment time.
3. **Validation:** native-link resolution, MappingSeries integrity, IDS readiness, bSDD terminology alignment, and RDF acoustic-data checks.
4. **Decision:** separate Link and Data decisions, followed by semantic status (`ACCEPTABLE`, `AMBIGUOUS`, `INVALID`, `BROKEN`, `UNMATCHED`, or `SEMANTICALLY_STALE`).
5. **Provenance and governance:** append-only MappingAssertions, validation activities, change events, reviewer overrides, and PROV-style revision links.

This separation is important: IFC external references answer where external information is identified, IDS answers whether specified IFC information requirements are met, bSDD supports controlled terminology, and PROV describes how an assertion was produced. None of those standards alone defines the complete lifecycle decision for an IFC element associated with an acoustic RDF record.

## Literature and novelty assessment

The defensible novelty claim is a **candidate systems contribution**, not a claim that MappingSeries or MappingAssertion are new standards. The standards and literature reviewed here establish the individual ingredients:

| Source | Established capability | Boundary left open by the source |
| --- | --- | --- |
| buildingSMART IFC 4.3, `IfcExternalReference` and `IfcDocumentReference` | URI/identification of external information and document association to IFC objects | No domain-specific semantic compatibility decision or append-only assessment lifecycle |
| buildingSMART IDS | Machine-interpretable exchange requirements and automated compliance results | Primarily validates IFC delivery requirements; it does not validate the identity and current compatibility of an external acoustic record |
| buildingSMART bSDD | Shared definitions and controlled concepts for built-environment terminology | Does not by itself decide whether two evidence snapshots justify an association |
| W3C PROV-O / PROV-DM | Entities, activities, usage, generation, derivation, and revision provenance | Domain rules for IFC-to-acoustic evidence compatibility must be supplied by an application |
| Pauwels et al., *Semantic web technologies in the architecture, engineering and construction domain: A review*, Automation in Construction 73 (2017), DOI [10.1016/j.autcon.2016.10.003](https://doi.org/10.1016/j.autcon.2016.10.003) | Establishes the role of semantic web and linked-data methods in AEC interoperability | Does not establish this specific two-part link/data acceptance gate with record-target re-approval and immutable MappingAssertion revisions |
| ISO 10140-2 and ISO 717-1 | Measurement/rating context for airborne sound insulation and `Rw`-type acoustic results | The prototype does not replace laboratory measurement or standards-compliant acoustic calculation |

The potentially novel combination is therefore: **an IFC-native external reference plus a stable MappingSeries identity, explicit two-part link/data acceptance, cross-side evidence comparison, record-target re-approval, and immutable PROV-style MappingAssertion revisions for acoustic lifecycle assessment**. A literature review cannot prove novelty by itself. A publishable novelty claim requires a systematic search protocol, comparison against the closest systems, and an ablation/evaluation showing that the lifecycle gate detects cases that link-only validation misses.

## Source preservation and enrichment

The original IFC and RDF are not overwritten. The IFC remains the source of element identity, geometry-related evidence represented here by editable proxy fields, and the native external document reference. The RDF record remains the source of acoustic performance and registry metadata. On each assessment, the app copies both current inputs into `EvidenceSnapshot` entities and creates a derived `MappingAssertion`. The enriched result is therefore a governed assessment layer, not a mutation of either source. In a production implementation, the snapshots should additionally store source file URI, source version, retrieval time, content hash, and agent/activity identifiers.

### Native IFC link versus Pset link

The **native IFC link** represents the technically authoritative external reference: an IFC `IfcDocumentReference.Location` or equivalent document association used to locate the RDF/acoustic record. The **Pset link** is a semantic enrichment property attached to the wall, such as `Pset_AcousticMapping.RecordURI` and `Pset_AcousticMapping.MappingSeriesURI`. It makes the mapping discoverable in IFC workflows and carries the semantic context, but it does not replace the native document reference or the external record. The validator requires both channels to agree with the RDF target when Pset validation is enabled. A native match with a Pset mismatch is therefore not accepted.

### Queries in the workflow

The **link-validation query** is a precondition query: it finds a wall, native URI, RDF URI, and MappingSeries and returns only URI-consistent candidates. It supports technical reachability and candidate discovery; it does not prove acoustic compatibility. The **lifecycle query** is an audit query: it retrieves MappingAssertion revisions and their `prov:wasRevisionOf` links in revision order. It supports traceability, comparison of evidence snapshots, and reconstruction of how the current decision was produced. In this prototype the query definitions are shown in the Graph tab, while the checks run in Python over the in-memory evidence state.

### Overall workflow

`Original IFC + original RDF -> native/Pset link discovery -> MappingSeries identity check -> IDS IFC readiness -> bSDD terminology alignment -> RDF data compatibility -> Link/Data decision -> reviewer approval if retargeted -> immutable MappingAssertion + snapshots + change events -> enriched assessment view`

The enrichment is consequently **derived and reversible**: a consumer can inspect the original source fields, the exact evidence used, the validation rules, the decision, and the provenance chain independently. This is stronger than copying `Rw` into IFC without recording where it came from or which validation activity justified it.

## Real IFC mode

The Evidence & rules tab can load `data/HFT_Bau4_2025.04.22 (1).ifc` through IfcOpenShell. This tested IFC4X3 file contains 514 wall objects. The extractor reads GlobalId, IFC entity type, name, material-layer names, and summed layer thickness where an IFC material-layer set is present. If the real model has no native document reference or custom acoustic Pset, those links remain empty and are reported as missing; the application does not manufacture them. The external RDF record remains separate and can be matched to the selected real wall.


## Run

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The app uses in-memory `st.session_state`; use the download control for a compact Turtle representation when needed. The prototype supports real IFC extraction through IfcOpenShell, while the acoustic RDF record remains external and is currently supplied through the editable registry fields.

## Reference standards

- [buildingSMART Information Delivery Specification](https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/): computer-interpretable exchange requirements and automated compliance checking.
- [buildingSMART IDS technical description](https://technical.buildingsmart.org/projects/information-delivery-specification-ids/): requirements for objects, properties, values, and units.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/): provenance entities, activities, usage, generation, and revision relationships.
- [VaBDat Bauteile](https://www.vabdat.de/Bauteil/): component identifiers, assemblies, construction types, and thickness metadata used by the presets.
