# Upgraded IFC–Acoustic Association Model

## Purpose

This layer governs the relationship between an IFC building element and an independently maintained acoustic record. It does **not** duplicate the acoustic record in IFC and it does not make the acoustic registry part of the IFC model.

Recommended separation of authority:

1. **IFC model** — wall identity, geometry, type, materials, spatial context.
2. **Acoustic RDF registry** — acoustic metric/value/unit, tested assembly/specimen, source, version and provenance.
3. **Association lifecycle graph** — mapping status, rationale, versions assessed, validation provenance and revision history.

The IFC-side carrier can remain `IfcDocumentReference` with its `Location` set to the stable acoustic-record URI. The association graph records whether that technically resolvable reference is currently semantically trustworthy.

## Why the model is version-aware

A `map:MappingSeries` is the stable identity of the wall↔record association. Each assessment creates a new `map:MappingAssertion` (`prov:Entity`) and a corresponding `map:ValidationActivity` (`prov:Activity`). The new assertion uses `prov:wasRevisionOf` to point to the previous assessment instead of overwriting it.

Each validation activity explicitly `prov:used`:

- a version-specific `map:IFCElementSnapshot`, and
- a version-specific `map:AcousticRecordSnapshot`.

This means a later user can reconstruct **which IFC version and which acoustic-record version were actually assessed**.

## Status vocabulary

- `ACCEPTABLE` — current evidence supports the association.
- `AMBIGUOUS` — technically usable, but current construction evidence is insufficient or non-equivalent.
- `INVALID` — current evidence contradicts the referenced record.
- `UNMATCHED` — no defensible record has been established.
- `MULTIPLE_CANDIDATES` — more than one plausible record requires resolution.
- `BROKEN` — the IFC-side identifier/reference exists but the external resource is unavailable.
- `SEMANTICALLY_STALE` — a previously acceptable association remains technically resolvable but model evolution has invalidated the previous correspondence.

## Files

- `association_model_schema.ttl` — lightweight local vocabulary and status concepts.
- `association_lifecycle.py` — versioned assertion/lifecycle manager.
- `association_lifecycle_demo.ttl` — generated Bau 1/VaBDat lifecycle demonstration.
- `association_lifecycle_demo.json` — human-readable summary of the current state and history.
- `queries.sparql` — example current-state, review, history and provenance queries.

## Run the demonstration

```powershell
python .\association_lifecycle.py demo --out .\association_lifecycle_demo.ttl
```

Show the current state:

```powershell
python .\association_lifecycle.py --graph .\association_lifecycle_demo.ttl current
```

Show history for the pilot association:

```powershell
python .\association_lifecycle.py --graph .\association_lifecycle_demo.ttl history `
  --global-id 2qL6OSUnz6ZAzEOn1HxeD2 `
  --record-id vabdat-310
```

## Add a new validation revision

```powershell
python .\association_lifecycle.py --graph .\association_lifecycle_demo.ttl validate `
  --global-id 2qL6OSUnz6ZAzEOn1HxeD2 `
  --wall-name "Walls : Walls_3OGArc01 : Walls_3OGArc01" `
  --wall-family metal_frame `
  --wall-thickness 0.285 `
  --wall-material "Metal Stud Layer" `
  --model-version bau1-v2 `
  --record-uri https://example.org/hft-acoustic/record/vabdat-310 `
  --record-id vabdat-310 `
  --record-assembly "B_bGP12_frM75||iMW60_bGP12" `
  --record-family metal_frame `
  --record-thickness 0.100 `
  --record-version prototype-v2 `
  --trigger ifc-model-revision
```

Use `--unavailable` to record an external-resource outage **without changing the stable IFC-side reference URI**.

## Research interpretation

This is a lifecycle/governance model, not an acoustic prediction model. The simple semantic assessment included in the script is only a transparent prototype for exercising the lifecycle states. The thesis should evaluate the quality of the workflow using traceability, version awareness, technical integrity, semantic integrity, ambiguity handling and recovery after change. Acoustic correspondence decisions should remain evidence-based and may require domain-expert validation.

## Structural validation

`association_model_shapes.ttl` contains SHACL constraints for the lifecycle graph: every mapping series must have exactly one current assertion, every assertion must record the two resources, status, rationale, versions, resolution/review flags and generating validation activity, and every validation activity must identify the evidence it used.

The script also includes a dependency-free structural check:

```powershell
python .\association_lifecycle.py --graph .\association_lifecycle_demo.ttl check
```

The demonstration's `prototype-v2` record state is a **controlled hypothetical revision** used to exercise lifecycle versioning; it is not claimed to be a second real VaBDat publication.
