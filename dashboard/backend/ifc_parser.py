"""IFC extraction for FAIR geometry resources."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import hashlib
import json


class IFCExtractor:
    """Extract IFC component identity, materials, dimensions and spatial context."""

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

    def extract_all_walls(self, ifc_path: Path) -> list[dict]:
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
            wall_entities = {str(w.GlobalId): w for w in model.by_type("IfcWall") if getattr(w, "GlobalId", None)}
            walls = [
                self._extract_wall(wall_entities[guid], model, unit_scale, ifc_path.stem, ifc_path.name, source_hash)
                for guid in sorted(wall_entities)
            ]
            self._write_cache(ifc_path, walls)
            return walls
        except Exception as exc:
            return [{"extraction_success": False, "error_details": f"IFC parsing error: {exc}"}]

    def _extract_wall(self, wall, model, unit_scale: float, model_version: str, source_file: str, source_hash: str) -> dict:
        try:
            layers = self._material_layers(wall, unit_scale)
            materials = [item["name"] for item in layers if item.get("name")]
            if not materials:
                materials = self._material_names(wall)
            thickness = sum(item.get("thickness_m", 0.0) or 0.0 for item in layers) or self._property_thickness(wall, unit_scale)
            spatial = self._spatial_context(wall)
            predefined = str(getattr(wall, "PredefinedType", "") or getattr(wall, "ObjectType", "") or "")
            return {
                "global_id": str(wall.GlobalId),
                "ifc_class": wall.is_a(),
                "name": str(getattr(wall, "Name", None) or "Unnamed IFC component"),
                "construction_family": self._infer_family(materials, predefined),
                "semantic_classification": predefined,
                "total_thickness_m": round(float(thickness), 6) if thickness is not None else None,
                "material_evidence": materials,
                "material_layers": layers,
                "spatial_context": spatial,
                "model_version": model_version,
                "source_file": source_file,
                "source_sha256": source_hash,
                "extraction_success": True,
                "error_details": None,
            }
        except Exception as exc:
            return {
                "global_id": str(getattr(wall, "GlobalId", "UNKNOWN")),
                "extraction_success": False,
                "error_details": f"Component extraction failed: {exc}",
            }

    def _material_layers(self, wall, unit_scale: float) -> list[dict]:
        try:
            from ifcopenshell.util.element import get_material
            material = get_material(wall)
            if not material:
                return []
            if material.is_a("IfcMaterialLayerSetUsage"):
                material = material.ForLayerSet
            if material.is_a("IfcMaterialLayerSet"):
                rows = []
                for layer in material.MaterialLayers:
                    name = str(layer.Material.Name) if layer.Material and layer.Material.Name else "Unnamed material"
                    rows.append({"name": name, "thickness_m": round(float(layer.LayerThickness) * unit_scale, 6)})
                return rows
            if material.is_a("IfcMaterial"):
                return [{"name": str(material.Name or "Unnamed material"), "thickness_m": None}]
        except Exception:
            pass
        return []

    def _material_names(self, wall) -> list[str]:
        names: list[str] = []
        try:
            from ifcopenshell.util.element import get_material
            material = get_material(wall)
            if material and getattr(material, "Name", None):
                names.append(str(material.Name))
        except Exception:
            pass
        return names

    def _property_thickness(self, wall, unit_scale: float) -> Optional[float]:
        try:
            from ifcopenshell.util.element import get_psets
            psets = get_psets(wall)
            for properties in psets.values():
                if not isinstance(properties, dict):
                    continue
                for key, value in properties.items():
                    if str(key).lower() in {"thickness", "width", "overallwidth"} and isinstance(value, (int, float)):
                        return float(value) * unit_scale
        except Exception:
            pass
        return None

    def _spatial_context(self, wall) -> dict:
        context = {"structure_type": None, "name": None, "global_id": None}
        try:
            relationships = getattr(wall, "ContainedInStructure", []) or []
            if relationships:
                structure = relationships[0].RelatingStructure
                context = {
                    "structure_type": structure.is_a(),
                    "name": str(getattr(structure, "Name", None) or ""),
                    "global_id": str(getattr(structure, "GlobalId", None) or ""),
                }
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


def extract_walls_from_ifc(ifc_path: Path, cache_dir: Optional[Path] = None) -> list[dict]:
    return IFCExtractor(cache_dir=cache_dir).extract_all_walls(ifc_path)
