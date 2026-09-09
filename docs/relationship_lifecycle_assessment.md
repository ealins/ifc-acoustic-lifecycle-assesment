# Relationship Lifecycle Assessment

The existing lifecycle engine is preserved as a supporting mechanism for the component-dataset relationship. It is not the primary metadata artifact and its states are not FAIR statuses.

## States

- `ACCEPTABLE` — current evidence supports the declared relationship.
- `SEMANTICALLY_STALE` — references may still exist, but changed source information weakens the original rationale/evidence.
- `BROKEN` — a required source is missing, corrupt, or explicitly unreachable.
- `AMBIGUOUS` — available evidence is insufficient or contradictory.
- `MULTIPLE_CANDIDATES` — more than one candidate satisfies the minimum conditions and selection requires review.
- `UNMATCHED` — no candidate satisfies the minimum relationship conditions.
- `INVALID` — available evidence contradicts the declared relationship or the target is no longer valid.
- `MANUAL_REVIEW` — the issue cannot be resolved automatically and requires an actual domain/workflow decision.

Legacy UI may display `SEMANTICALLY_STALE` as `STALE`; the persisted semantic state remains explicit.

## Reassessment triggers

The prototype records typed triggers for IFC checksum/schema/GlobalId/entity/type/material/layer/dimension changes; acoustic dataset checksum/version/URI/availability changes; provenance/licence/access changes; metadata-profile changes; relationship target/type/evidence changes; competing candidate changes; and editorial package-title changes.

Every trigger records ID, timestamp, affected entity, previous/current value, severity, assessment consequence, resulting state and recommended action.

Editorial changes are explicitly separated from interpretation-affecting changes. For example, a package-title edit can leave the relationship acceptable while a relevant thickness change can make it semantically stale.

## Stewardship history

MappingSeries/MappingAssertion and existing lifecycle structures remain authoritative for the legacy stewardship logic. New relationship records add source versions/checksums and trigger evidence without deleting prior assertions.

## Independence from metadata and FAIR

A lifecycle change does not automatically change metadata completeness or FAIR support. Conversely, missing licence/provenance metadata does not automatically invalidate the physical/semantic component-dataset relationship.

Acoustic scientific suitability remains `NOT_ASSESSED` unless a real external/manual process supplies such evidence.
