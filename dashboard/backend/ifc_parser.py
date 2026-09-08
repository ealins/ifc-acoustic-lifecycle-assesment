"""
IFC File Parser for Wall Extraction

Extracts wall evidence from IFC files using ifcopenshell.
Implements caching and error handling for production use.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List
import hashlib
import json


@dataclass
class WallExtractionResult:
    """Result of extracting a wall from an IFC file."""
    global_id: str
    name: str
    construction_family: str
    total_thickness_m: Optional[float]
    material_evidence: List[str]
    model_version: str
    extraction_success: bool
    error_details: Optional[str] = None


class IFCExtractor:
    """Extract wall evidence from IFC files."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, ifc_path: Path) -> str:
        file_hash = hashlib.md5(ifc_path.read_bytes()).hexdigest()
        return f"{ifc_path.stem}_{file_hash}"

    def _read_from_cache(self, ifc_path: Path) -> Optional[List[Dict]]:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / f"{self._get_cache_key(ifc_path)}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None

    def _write_to_cache(self, ifc_path: Path, walls: List[Dict]) -> None:
        if not self.cache_dir:
            return
        cache_file = self.cache_dir / f"{self._get_cache_key(ifc_path)}.json"
        try:
            cache_file.write_text(json.dumps(walls, indent=2))
        except Exception:
            pass

    def extract_all_walls(self, ifc_path: Path) -> List[Dict]:
        cached = self._read_from_cache(ifc_path)
        if cached is not None:
            return cached

        try:
            import ifcopenshell
        except ImportError:
            return [{
                "extraction_success": False,
                "error_details": "ifcopenshell not installed. Install with: pip install ifcopenshell"
            }]

        walls = []
        try:
            model = ifcopenshell.open(str(ifc_path))
            model_version = ifc_path.stem
            wall_entities = model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")

            seen_ids = set()
            for wall_entity in wall_entities:
                global_id = str(getattr(wall_entity, "GlobalId", ""))
                if global_id and global_id in seen_ids:
                    continue
                if global_id:
                    seen_ids.add(global_id)
                walls.append(self._extract_wall_evidence(wall_entity, model, model_version))

            self._write_to_cache(ifc_path, walls)
        except Exception as e:
            walls.append({
                "extraction_success": False,
                "error_details": f"IFC parsing error: {str(e)}"
            })

        return walls

    def _extract_wall_evidence(self, wall_entity, model, model_version: str) -> Dict:
        try:
            global_id = wall_entity.GlobalId
            name = getattr(wall_entity, "Name", "Unknown Wall") or "Unknown Wall"
            material_evidence = self._extract_materials(wall_entity)
            construction_family = self._infer_construction_family(material_evidence, wall_entity)
            total_thickness_m = self._extract_thickness(wall_entity)

            return {
                "global_id": str(global_id),
                "name": str(name),
                "construction_family": construction_family,
                "total_thickness_m": total_thickness_m,
                "material_evidence": material_evidence,
                "model_version": model_version,
                "extraction_success": True,
                "error_details": None
            }
        except Exception as e:
            return {
                "global_id": getattr(wall_entity, "GlobalId", "UNKNOWN"),
                "extraction_success": False,
                "error_details": f"Wall extraction failed: {str(e)}"
            }

    def _extract_materials(self, wall_entity) -> List[str]:
        materials = []
        try:
            associations = getattr(wall_entity, "HasAssociations", [])
            for assoc in associations:
                relating_material = getattr(assoc, "RelatingMaterial", None)
                if relating_material is None:
                    continue
                if relating_material.is_a("IfcMaterialLayerSetUsage"):
                    relating_material = relating_material.ForLayerSet
                if relating_material.is_a("IfcMaterialLayerSet"):
                    for layer in relating_material.MaterialLayers or []:
                        material = getattr(layer, "Material", None)
                        mat_name = getattr(material, "Name", None)
                        if mat_name and str(mat_name) not in materials:
                            materials.append(str(mat_name))
                else:
                    mat_name = getattr(relating_material, "Name", None)
                    if mat_name and str(mat_name) not in materials:
                        materials.append(str(mat_name))
        except Exception:
            pass
        return materials if materials else ["Unknown Material"]

    def _extract_thickness(self, wall_entity) -> Optional[float]:
        try:
            for assoc in getattr(wall_entity, "HasAssociations", []) or []:
                relating_material = getattr(assoc, "RelatingMaterial", None)
                if relating_material is None:
                    continue
                if relating_material.is_a("IfcMaterialLayerSetUsage"):
                    relating_material = relating_material.ForLayerSet
                if relating_material.is_a("IfcMaterialLayerSet"):
                    thicknesses = [
                        float(layer.LayerThickness)
                        for layer in relating_material.MaterialLayers or []
                        if getattr(layer, "LayerThickness", None) is not None
                    ]
                    if thicknesses:
                        total = sum(thicknesses)
                        # IFC projects commonly use millimetres; normalize obvious mm totals.
                        return total / 1000.0 if total > 10 else total
        except Exception:
            pass
        return None

    def _infer_construction_family(self, materials: List[str], wall_entity) -> str:
        material_str = " ".join(materials).lower()
        if any(term in material_str for term in ["concrete", "beton"]):
            return "Concrete"
        if any(term in material_str for term in ["brick", "masonry", "mortar", "ziegel"]):
            return "Masonry Wall"
        if any(term in material_str for term in ["wood", "timber", "holz", "clt"]):
            return "Timber Frame"
        if any(term in material_str for term in ["steel", "metal", "metall"]):
            return "Steel Frame"
        return "Unknown Family"


def extract_walls_from_ifc(ifc_path: Path, cache_dir: Optional[Path] = None) -> List[Dict]:
    extractor = IFCExtractor(cache_dir=cache_dir)
    return extractor.extract_all_walls(ifc_path)
