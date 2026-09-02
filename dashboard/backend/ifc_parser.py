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
        """
        Initialize IFC extractor with optional caching.
        
        Args:
            cache_dir: Directory to cache extraction results. If None, caching is disabled.
        """
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, ifc_path: Path) -> str:
        """Generate cache key from IFC file path and content hash."""
        file_hash = hashlib.md5(ifc_path.read_bytes()).hexdigest()
        return f"{ifc_path.stem}_{file_hash}"
    
    def _read_from_cache(self, ifc_path: Path) -> Optional[List[Dict]]:
        """Read cached extraction results."""
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
        """Write extraction results to cache."""
        if not self.cache_dir:
            return
        
        cache_file = self.cache_dir / f"{self._get_cache_key(ifc_path)}.json"
        try:
            cache_file.write_text(json.dumps(walls, indent=2))
        except Exception:
            pass  # Silently fail on cache write

    
    
    def extract_all_walls(self, ifc_path: Path) -> List[Dict]:
        """
        Extract all walls from an IFC file.
        
        Args:
            ifc_path: Path to IFC file
            
        Returns:
            List of wall dictionaries with evidence
        """
        # Check cache first
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
            
            # Extract all walls from the IFC model
            wall_entities = model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")
            
            for wall_entity in wall_entities:
                wall_dict = self._extract_wall_evidence(wall_entity, model, model_version)
                walls.append(wall_dict)
            
            # Cache successful results
            self._write_to_cache(ifc_path, walls)
            
        except Exception as e:
            walls.append({
                "extraction_success": False,
                "error_details": f"IFC parsing error: {str(e)}"
            })
    
    def _extract_wall_evidence(self, wall_entity, model, model_version: str) -> Dict:
        """
        Extract evidence from a single wall entity.
        
        Args:
            wall_entity: IfcWall or IfcWallStandardCase entity
            model: ifcopenshell model object
            model_version: Version identifier for the model
            
        Returns:
            Dictionary with wall evidence
        """
        try:
            global_id = wall_entity.GlobalId
            name = getattr(wall_entity, "Name", "Unknown Wall")
            
            # Extract material information
            material_evidence = self._extract_materials(wall_entity)
            construction_family = self._infer_construction_family(material_evidence, wall_entity)
            
            # Extract thickness
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
        """Extract material names from wall entity."""
        materials = []
        
        try:
            # Get HasAssociations
            associations = getattr(wall_entity, "HasAssociations", [])
            for assoc in associations:
                if hasattr(assoc, "RelatedObjects"):
                    for obj in assoc.RelatedObjects:
                        if hasattr(obj, "Name"):
                            mat_name = str(obj.Name).strip()
                            if mat_name and mat_name not in materials:
                                materials.append(mat_name)
            
            # Try material properties
            if hasattr(wall_entity, "HasPropertySets"):
                for pset in wall_entity.HasPropertySets:
                    if hasattr(pset, "HasProperties"):
                        for prop in pset.HasProperties:
                            if "Material" in str(getattr(prop, "Name", "")):
                                if hasattr(prop, "NominalValue"):
                                    mat_name = str(prop.NominalValue).strip()
                                    if mat_name and mat_name not in materials:
                                        materials.append(mat_name)
        except Exception:
            pass
        
        return materials if materials else ["Unknown Material"]
    
    def _extract_thickness(self, wall_entity) -> Optional[float]:
        """Extract total thickness from wall entity in meters."""
        try:
            # Check IfcWallStandardCase Quantity properties
            if hasattr(wall_entity, "HasPropertySets"):
                for pset in wall_entity.HasPropertySets:
                    if hasattr(pset, "HasProperties"):
                        for prop in pset.HasProperties:
                            prop_name = str(getattr(prop, "Name", "")).lower()
                            if "thickness" in prop_name:
                                if hasattr(prop, "NominalValue"):
                                    try:
                                        return float(prop.NominalValue)
                                    except (ValueError, TypeError):
                                        pass
        except Exception:
            pass
        
        return None
    
    def _infer_construction_family(self, materials: List[str], wall_entity) -> str:
        """Infer construction family from materials and wall type."""
        material_str = " ".join(materials).lower()
        
        # Pattern matching for construction families
        if any(term in material_str for term in ["concrete", "beton"]):
            return "Concrete"
        elif any(term in material_str for term in ["brick", "masonry", "mortar"]):
            return "Masonry Wall"
        elif any(term in material_str for term in ["wood", "timber", "holz", "clt"]):
            return "Timber Frame"
        elif any(term in material_str for term in ["steel", "metal", "metallstud"]):
            return "Steel Frame"
        else:
            return "Unknown Family"


def extract_walls_from_ifc(ifc_path: Path, cache_dir: Optional[Path] = None) -> List[Dict]:
    """
    Convenience function to extract all walls from an IFC file.
    
    Args:
        ifc_path: Path to IFC file
        cache_dir: Optional directory for caching results
        
    Returns:
        List of wall evidence dictionaries
    """
    extractor = IFCExtractor(cache_dir=cache_dir)
    return extractor.extract_all_walls(ifc_path)


