from __future__ import annotations

import argparse
from pathlib import Path

BASE = "https://example.org/hft-acoustic/"


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Create the hybrid IFC carrier used by the final architecture: an IFC-native "
            "IfcDocumentReference carries the acoustic-record URI, while HFT_AcousticLink "
            "carries only a stable MappingSeries URI and semantic profile."
        )
    )
    p.add_argument("--ifc-in", type=Path, required=True, help="Source IFC (native-reference baseline or any IFC containing the target wall).")
    p.add_argument("--ifc-out", type=Path, required=True)
    p.add_argument("--global-id", required=True)
    p.add_argument("--record-uri", required=True)
    p.add_argument("--record-id", required=True)
    p.add_argument("--semantic-profile", default="HFT-Acoustic-Link-v1")
    args = p.parse_args()

    try:
        import ifcopenshell
        import ifcopenshell.guid
    except ImportError as e:
        raise RuntimeError("IfcOpenShell is required. Run in the thesis .venv.") from e

    model = ifcopenshell.open(str(args.ifc_in))
    wall = model.by_guid(args.global_id)
    if wall is None:
        raise RuntimeError(f"IFC element {args.global_id} not found")

    # 1) Native technical carrier. Reuse an existing IfcDocumentReference associated
    # with the wall if one exists; otherwise create the standard IFC association.
    native_rel = None
    native_doc = None
    for rel in model.get_inverse(wall):
        try:
            if rel.is_a() == "IfcRelAssociatesDocument":
                doc = getattr(rel, "RelatingDocument", None)
                if doc is not None and doc.is_a() == "IfcDocumentReference":
                    native_rel, native_doc = rel, doc
                    break
        except Exception:
            pass

    if native_doc is None:
        native_doc = model.create_entity(
            "IfcDocumentReference",
            Location=args.record_uri,
            Identification=args.record_id,
            Name="External acoustic RDF record",
            Description="IFC-native technical reference; semantic lifecycle state is governed externally.",
            ReferencedDocument=None,
        )
        native_rel = model.create_entity(
            "IfcRelAssociatesDocument",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=getattr(wall, "OwnerHistory", None),
            Name="Acoustic external reference",
            Description=None,
            RelatedObjects=[wall],
            RelatingDocument=native_doc,
        )
    else:
        native_doc.Location = args.record_uri
        try:
            native_doc.Identification = args.record_id
            native_doc.Name = "External acoustic RDF record"
            native_doc.Description = "IFC-native technical reference; semantic lifecycle state is governed externally."
        except Exception:
            pass

    # 2) Remove any previous prototype acoustic link pset from this wall so the custom
    # layer does not duplicate AcousticRecordURI / MappingStatus / MappingBasis.
    old_rels = []
    old_psets = []
    for rel in list(model.get_inverse(wall)):
        try:
            if rel.is_a() != "IfcRelDefinesByProperties":
                continue
            pset = getattr(rel, "RelatingPropertyDefinition", None)
            if pset is None or pset.is_a() != "IfcPropertySet":
                continue
            if str(getattr(pset, "Name", "") or "") in {"HFT_AcousticLink", "Pset_AcousticLink"}:
                old_rels.append(rel)
                old_psets.append(pset)
        except Exception:
            pass
    for rel in old_rels:
        try:
            model.remove(rel)
        except Exception:
            pass
    for pset in old_psets:
        props = list(getattr(pset, "HasProperties", None) or [])
        try:
            model.remove(pset)
        except Exception:
            pass
        for prop in props:
            try:
                model.remove(prop)
            except Exception:
                pass

    # 3) Lightweight HFT semantic anchor. It deliberately does NOT duplicate the
    # acoustic record URI. MappingSeries is stable while MappingAssertion revisions
    # can change externally without editing the IFC.
    series_uri = f"{BASE}mapping/series/{args.global_id}--{args.record_id}"
    p_mapping = model.create_entity(
        "IfcPropertySingleValue",
        Name="MappingSeriesURI",
        Description="Stable URI of the externally governed acoustic mapping series.",
        NominalValue=model.create_entity("IfcText", series_uri),
        Unit=None,
    )
    p_type = model.create_entity(
        "IfcPropertySingleValue",
        Name="AssociationType",
        Description=None,
        NominalValue=model.create_entity("IfcLabel", "AcousticPerformanceReference"),
        Unit=None,
    )
    p_profile = model.create_entity(
        "IfcPropertySingleValue",
        Name="SemanticProfile",
        Description=None,
        NominalValue=model.create_entity("IfcLabel", args.semantic_profile),
        Unit=None,
    )
    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=getattr(wall, "OwnerHistory", None),
        Name="HFT_AcousticLink",
        Description="Lightweight semantic anchor; the native IFC association remains authoritative for the acoustic-record URI.",
        HasProperties=[p_mapping, p_type, p_profile],
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=getattr(wall, "OwnerHistory", None),
        Name="Acoustic semantic anchor",
        Description=None,
        RelatedObjects=[wall],
        RelatingPropertyDefinition=pset,
    )

    model.write(str(args.ifc_out))
    print(f"Wrote hybrid IFC: {args.ifc_out}")
    print(f"Native acoustic record URI: {args.record_uri}")
    print(f"HFT MappingSeriesURI: {series_uri}")
    print("HFT_AcousticLink intentionally contains no AcousticRecordURI or mutable MappingStatus.")


if __name__ == "__main__":
    main()
