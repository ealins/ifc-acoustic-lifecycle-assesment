# Research positioning

## Preferred project description

**A prototype FAIR-oriented acoustic component research-object profile and workflow for IFC-linked measurement datasets, with qualified relationship evidence and lifecycle stewardship.**

The prototype does not claim to invent FAIR principles, generic research objects, IFC-to-acoustic linking, acoustic BIM workflows, IDS, bSDD, a universal acoustic metadata standard, a certified FAIR assessment method, or a new acoustic simulation method.

## Research problem

Measured building-acoustic data require component identity, geometry, measurement context, provenance, rights, access information, and version evidence for responsible reuse. A file-level link between an IFC element and an acoustic record is insufficient when the association must later be reviewed after either source changes.

## Existing work and complementary roles

- **FAIR** provides high-level goals for findability, accessibility, interoperability, and reusability.
- **Research-object and RO-Crate concepts** provide a generic lightweight packaging baseline for related research assets and metadata.
- **IFC** provides building-component representation, identity, type/material context, and model version evidence.
- **Building-acoustic BIM workflows** already connect digital building models with acoustic calculation, simulation, or measurement information.
- **RDF and Linked Data** provide machine-readable entities and relationships.
- **IDS** can specify IFC-side information requirements.
- **bSDD** can identify shared property concepts when genuine dictionary identifiers are supplied.

These roles are complementary. IDS and bSDD are not alternatives to FAIR, and FAIR is not an IFC validation mechanism.

## Specific gap addressed by this prototype

For the selected IFC/external-acoustic-data use case, the prototype focuses on a specialized profile that combines:

1. one IFC model and one selected IFC component,
2. one or more acoustic datasets or references,
3. explicit classification of acoustic-data origin,
4. a qualified geometry-measurement relationship,
5. structured evidence explaining that relationship,
6. FAIR-oriented package metadata and access/rights evidence,
7. version and provenance information, and
8. lifecycle reassessment when relationship-relevant source evidence changes.

The contribution is intentionally narrower than a universal acoustic metadata standard or FAIR certification method.

## Conceptual outputs

1. **Acoustic Component Research-Object Profile**
2. **Metadata Profile**
3. **Qualified Geometry-Measurement Relationship Model**
4. **Lifecycle Stewardship and FAIR-Support Evaluation**

## Research artifact

The software artifact is a prototype `AcousticComponentResearchObject` domain model, metadata profile, qualified relationship/evidence model, RO-Crate-style package builder, bounded FAIR-support evaluator, local component catalog, and lifecycle stewardship adapter around the existing lifecycle engines.

## Research questions

### RQ1
How can an IFC component and an external acoustic measurement dataset be represented as entities within a coherent acoustic component research object?

### RQ2
Which identification, provenance, access, rights, measurement-context, and relationship-evidence metadata are required for the selected IFC/VaBDat use case?

### RQ3
How can the claim that a measurement characterizes an IFC component be represented, justified, versioned, and reassessed?

### RQ4
To what extent does the resulting prototype support selected FAIR indicators while maintaining lifecycle traceability of the geometry-measurement relationship?

## Evaluation strategy

- technical validation of source parsing and package integrity,
- metadata-profile coverage,
- bounded FAIR-support assessment with criterion evidence,
- lifecycle scenario evaluation and trigger detection,
- RO-Crate/RDF serialization checks,
- checksum and archive verification,
- reproducibility-resource packaging, and
- explicit limitation analysis.

## Non-contributions

The prototype does **not** establish acoustic scientific validity, certify whether a measurement is suitable for a design decision, issue DOIs, guarantee long-term preservation, provide an institutional repository, define a universal acoustic ontology, or certify FAIR compliance.

> This prototype evaluates metadata, package structure, and relationship stewardship. It does not establish the scientific validity or acoustic suitability of measurement values.
