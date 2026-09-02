# Association model v6

Small correctness patch over v5.

## Fix
`association_lifecycle.py` no longer renders RDF boolean `false` as an empty string in `current` and `history` output. The RDF graph already stored `xsd:boolean false`; Python/RDFLib boolean literals evaluate as false in boolean context, so the old display expression `value or ''` hid the value.

No evidence model or lifecycle semantics changed. Existing v5 RDF graphs can be copied directly into v6 and continued without rebuilding r1-r4.
