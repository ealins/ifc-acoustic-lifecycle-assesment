"""IFC extraction for acoustic component research objects."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import hashlib
import json


ACOUSTIC_COMPONENT_CLASSES = (
    "IfcWall", "IfcSlab", "IfcRoof", "IfcDoor", "IfcWindow", "IfcCurtainWall",
    "IfcCovering", "IfcPlate", "IfcMember", "IfcColumn", "IfcBeam",
)


class IFCExtractor:
    """Extract verifiable IFC identity/evidence without duplicating the full IFC model."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, ifc_path: Path) -> str:
        digest = hashlib.sha256(ifc_path.read_bytes()).hexdigest()[:20]
        return f"{ifc_path.stem}_{digest}"

    def _read_cache(self, ifc_path: Path):
        if not self.cache_dir:
            return None
        target = self.cache_dir / f"{self._cache_key(ifc_path)}.json"
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, ifc_path: Path, data: list[dict]) -> None:
        if not self.cache_dir:
            return
        try:
            (self.cache_dir / f"{self._cache_key(ifc_path)}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def extract_all_components(self, ifc_path: Path) -> list[dict]:
        cached = self._read_cache(ifc_path)
        if cached is not None:
            return cached
        try:
            import ifcopenshell
            from ifcopenshell.util.unit import calculate_unit_scale
        except ImportError:
            return [{"extraction_success": False, "error_details": "IfcOpenShell is not installed."}]
        try:
            model = ifcopenshell.open(str(ifc_path))
            unit_scale = float(calculate_unit_scale(model))
            source_hash = hashlib.sha256(ifc_path.read_bytes()).hexdigest()
            schema = str(getattr(model, "schema", "") or "")
            entities = {}
            for class_name in ACOUSTIC_COMPONENT_CLASSES:
                for entity in model.by_type(class_name):
                    gid = getattr(entity, "GlobalId", None)
                    if gid:
                        entities[str(gid)] = entity
            rows = [
                self._extract_component(entities[guid], unit_scale, ifc_path.stem, ifc_path.name, source_hash, schema)
                for guid in sorted(entities)
            ]
            self._write_cache(ifc_path, rows)
            return rows
        except Exception as exc:
            return [{"extraction_success": False, "error_details": f"IFC parsing error: {exc}"}]

    def extract_all_walls(self, ifc_path: Path) -> list[dict]:
        """Compatibility view used by older UI/tests."""
        return [item for item in self.extract_all_components(ifc_path) if item.get("ifc_class") == "IfcWall" or not item.get("extraction_success")]

    def resolve_global_id(self, ifc_path: Path, global_id: str) -> dict:
        matches = [item for item in self.extract_all_components(ifc_path) if item.get("global_id") == global_id]
        if not matches:
            return {"resolved": False, "global_id": global_id, "error_details": "Selected GlobalId was not found among supported IFC building components."}
        return {"resolved": True, **matches[0]}

    def _extract_component(self, element, unit_scale: float, model_version: str, source_file: str, source_hash: str, schema: str) -> dict:
        try:
            layers = self._material_layers(element, unit_scale)
            materials = [item["name"] for item in layers if item.get("name")]
            if not materials:
                materials = self._material_names(element)
            thickness = sum(item.get("thickness_m", 0.0) or 0.0 for item in layers) or self._property_thickness(element, unit_scale)
            predefined = str(getattr(element, "PredefinedType", "") or getattr(element, "ObjectType", "") or "")
            type_info = self._type_assignment(element)
            return {
                "global_id": str(element.GlobalId),
                "ifc_class": element.is_a(),
                "ifc_schema": schema,
                "name": str(getattr(element, "Name", None) or ""),
                "description": str(getattr(element, "Description", None) or ""),
                "component_type": type_info.get("name") or predefined,
                "component_type_global_id": type_info.get("global_id"),
                "construction_family": self._infer_family(materials, predefined),
                "semantic_classification": predefined,
                "total_thickness_m": round(float(thickness), 6) if thickness is not None else None,
                "material_evidence": materials,
                "material_layers": layers,
                "spatial_context": self._spatial_context(element),
                "model_version": model_version,
                "source_file": source_file,
                "source_sha256": source_hash,
                "extraction_success": True,
                "error_details": None,
            }
        except Exception as exc:
            return {"global_id": str(getattr(element, "GlobalId", "UNKNOWN")), "extraction_success": False, "error_details": f"Component extraction failed: {exc}"}

    def _type_assignment(self, element) -> dict:
        try:
            from ifcopenshell.util.element import get_type
            type_object = get_type(element)
            if type_object:
                return {
                    "name": str(getattr(type_object, "Name", None) or ""),
                    "global_id": str(getattr(type_object, "GlobalId", None) or "") or None,
                    "ifc_class": type_object.is_a(),
                }
        except Exception:
            pass
        return {"name": None, "global_id": None, "ifc_class": None}

    def _material_layers(self, element, unit_scale: float) -> list[dict]:
        try:
            from ifcopenshell.util.element import get_material
            material = get_material(element)
            if not material:
                return []
            if material.is_a("IfcMaterialLayerSetUsage"):
                material = material.ForLayerSet
            if material.is_a("IfcMaterialLayerSet"):
                return [
                    {"name": str(layer.Material.Name) if layer.Material and layer.Material.Name else "", "thickness_m": round(float(layer.LayerThickness) * unit_scale, 6)}
                    for layer in material.MaterialLayers
                ]
            if material.is_a("IfcMaterial"):
                return [{"name": str(material.Name or ""), "thickness_m": None}]
        except Exception:
            pass
        return []

    def _material_names(self, element) -> list[str]:
        try:
            from ifcopenshell.util.element import get_material
            material = get_material(element)
            return [str(material.Name)] if material and getattr(material, "Name", None) else []
        except Exception:
            return []

    def _property_thickness(self, element, unit_scale: float) -> Optional[float]:
        try:
            from ifcopenshell.util.element import get_psets
            for properties in get_psets(element).values():
                if not isinstance(properties, dict):
                    continue
                for key, value in properties.items():
                    if str(key).lower() in {"thickness", "width", "overallwidth"} and isinstance(value, (int, float)):
                        return float(value) * unit_scale
        except Exception:
            pass
        return None

    def _spatial_context(self, element) -> dict:
        context = {"structure_type": None, "name": None, "global_id": None}
        try:
            relationships = getattr(element, "ContainedInStructure", []) or []
            if relationships:
                structure = relationships[0].RelatingStructure
                context = {"structure_type": structure.is_a(), "name": str(getattr(structure, "Name", None) or ""), "global_id": str(getattr(structure, "GlobalId", None) or "")}
        except Exception:
            pass
        return context

    @staticmethod
    def _infer_family(materials: list[str], classification: str) -> str:
        text = " ".join(materials + [classification]).lower()
        if any(term in text for term in ["concrete", "beton"]):
            return "Concrete"
        if any(term in text for term in ["brick", "masonry", "mortar", "ziegel"]):
            return "Masonry Wall"
        if any(term in text for term in ["wood", "timber", "holz", "clt"]):
            return "Timber Frame"
        if any(term in text for term in ["steel", "metal", "stud"]):
            return "Steel Frame"
        return "Unknown Family"


def extract_components_from_ifc(ifc_path: Path, cache_dir: Optional[Path] = None) -> list[dict]:
    return IFCExtractor(cache_dir=cache_dir).extract_all_components(ifc_path)


def extract_walls_from_ifc(ifc_path: Path, cache_dir: Optional[Path] = None) -> list[dict]:
    return IFCExtractor(cache_dir=cache_dir).extract_all_walls(ifc_path)


def resolve_component_by_global_id(ifc_path: Path, global_id: str, cache_dir: Optional[Path] = None) -> dict:
    return IFCExtractor(cache_dir=cache_dir).resolve_global_id(ifc_path, global_id)
