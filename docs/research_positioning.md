# Revised Research Positioning

## Preferred project description

**A prototype FAIR-oriented metadata profile, research-object package, and workflow for reusable acoustic component datasets linked to IFC representations.**

## Research problem

Acoustic datasets may exist independently from the digital representations of the components they describe. Without sufficient identification, measurement-context, provenance, access, rights, version, quality, and relationship metadata, such datasets may be technically available but difficult to understand or reuse.

## Research gap

Existing work addresses IFC-based acoustic calculations, IFC information requirements, semantic property definitions, BIM-acoustic workflows, generic FAIR principles, and generic research-data packaging. However, the selected use case lacks a focused metadata profile and prototype package workflow for managing acoustic component datasets together with IFC component representations as reusable research objects.

## Primary artifact

A **prototype FAIR-oriented acoustic component metadata profile and package model**.

The metadata profile specifies identification, IFC component context, acoustic dataset description, measurement/generation context, provenance, access, rights, quality, version, reuse and component-dataset relationship metadata for the selected prototype use case.

## Supporting artifacts

- component-dataset relationship and structured evidence model;
- metadata-completeness assessment;
- selected FAIR-support evaluation;
- relationship lifecycle assessment/stewardship;
- prototype acoustic component library;
- RO-Crate-style package serialization with RDF/Turtle and integrity evidence.

Lifecycle relationship assessment is retained as a supporting mechanism. It checks whether the relationship between an IFC component and acoustic dataset remains acceptable, stale, broken, ambiguous, unmatched, invalid, multiple-candidate, or in need of manual review.

## Research questions

### RQ1

What metadata are needed to identify, understand, assess, and reuse acoustic component datasets linked to IFC representations?

### RQ2

How can IFC component information, acoustic dataset metadata, provenance, access conditions, rights, quality information, and relationship evidence be represented in a coherent acoustic component research object?

### RQ3

How can a prototype workflow operationalize metadata creation, validation, package export, and component-library registration?

### RQ4

To what extent does the resulting metadata profile and package support selected FAIR indicators and maintain a traceable relationship between the IFC component and acoustic dataset?

## Contribution statement

The thesis develops and evaluates a FAIR-oriented acoustic component metadata profile and package model. The profile specifies the identification, component-context, measurement-context, provenance, access, rights, quality, version, and relationship metadata required for the selected IFC/VaBDat use case. The implementation operationalizes the profile as an acoustic component package builder and prototype library, while FAIR-support and relationship lifecycle assessments provide independent evaluation mechanisms.

## Role of FAIR

FAIR is a design and evaluation framework, not the thesis invention. The implementation uses **FAIR-oriented design**, **selected FAIR indicators**, **FAIR-support assessment**, **metadata completeness**, and **support for reuse**. It does not claim formal FAIR certification, universal FAIR compliance, repository certification, guaranteed long-term accessibility, or issuance of persistent identifiers.

## Related technical responsibilities

- **IFC**: authoritative component identity, geometry, relationships, materials and spatial context; GlobalId is used as component identity evidence.
- **IDS**: optional IFC-side information-requirement specification/validation; does not replace acoustic research-data metadata.
- **bSDD**: optional shared property/classification semantics; does not store or steward the acoustic dataset/package.
- **RO-Crate**: generic research-object packaging baseline used where practical; not an invention of the thesis.
- **RDF/PROV**: machine-readable package, provenance, relationship and assessment representation.

## Scope limitations

The prototype is not an acoustic simulation engine, IDS replacement, bSDD replacement, universal acoustic metadata standard, certified repository, DOI registration service, FAIR certification service or automatic scientific-validity assessor.

**Visible application statement:**

> This prototype evaluates metadata coverage, package structure, FAIR support, and component-dataset relationship status. It does not establish the scientific validity or acoustic suitability of the measurement values.
