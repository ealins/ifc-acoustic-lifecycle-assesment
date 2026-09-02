# Association lifecycle model v4

Key upgrades over v3:

1. **Content-addressed evidence snapshots.** IFC and acoustic-record snapshot URIs include the evidence hash. A changed record therefore creates a different immutable snapshot even when its human version label is unchanged.
2. **Field-level change provenance.** Each new mapping assertion carries structured `map:ChangeEvent` nodes with category, field, old value and new value.
3. **Reproducible evidence state.** The exact wall and record evidence used by each assertion is stored as canonical JSON plus structured RDF snapshot triples.
4. **Evidence model version 3.** This prevents silent comparison of incompatible fingerprint definitions.

For a formal experiment, start a new graph rather than continuing a v3 graph, because v3 snapshot identifiers were version-label based.
