# IDS and bSDD Positioning

IDS and bSDD are optional supporting mechanisms in this prototype. Neither replaces the acoustic dataset, the FAIR-oriented research-data metadata, the research-object package, or relationship lifecycle stewardship.

## IFC

IFC remains authoritative for building-component identity, geometry, relationships, materials and spatial context. The prototype selects a real IFC element and records its GlobalId and source evidence without translating the complete IFC model into RDF.

## IDS

IDS can specify and validate IFC-side information requirements, for example whether a required component property or identifier is present. Optional package metadata can record an IDS specification reference and validation status.

The prototype does not fabricate IDS references and does not require an IDS file for the metadata profile to work.

## bSDD

bSDD can support shared classifications, property definitions, vocabulary semantics and references to standardized concepts. Optional metadata fields accept a real bSDD concept URI, property vocabulary URI and mapping status where such references are genuinely available.

No online bSDD connection is required. A supplied URI may require external/manual semantic verification and is not automatically treated as valid merely because it is syntactically well formed.

## Division of responsibility

- IFC: component representation and identity.
- IDS: optional IFC-side information requirements/validation.
- bSDD: optional shared concept/property semantics.
- acoustic dataset: scientific/catalog/reference values.
- metadata profile: identification, context, provenance, access, rights, quality, version and relationship metadata.
- research-object package: portable assembly and evidence.
- lifecycle stewardship: continuing validity of the component-dataset relationship.
