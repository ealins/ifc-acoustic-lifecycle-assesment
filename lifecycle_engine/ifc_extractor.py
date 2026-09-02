"""
IFC extraction engine for GeoBIM lifecycle.

Parses IFC files and extracts wall evidence with construction family,
thickness, and material information.
"""

from pathlib import Path
from typing import Optional, Dict, List
import ifcopenshell
import ifcopenshell.util.element as el


@staticmethod
def get_wall_thickness_from_type(wall, ifc_file) -> Optional[float]:
    """
    Extract wall thickness from IfcWallType or material layers.
    
    Returns thickness in meters, or None if unavailable.
    """
    try:
        # Try to get from type
        wall_type = wall.IsDefinedBy
        if wall_type:
            for rel in wall_type:
                if hasattr(rel, 'RelatingPropertyDefinition'):
                    pset = rel.RelatingPropertyDefinition
                    if hasattr(pset, 'HasProperties'):
                        for prop in pset.HasProperties:
                            if hasattr(prop, 'Name') and 'Thickness' in prop.Name:
                                if hasattr(prop, 'NominalValue'):
                                    return float(prop.NominalValue.wrappedValue)
        
        # Try material layers
        if hasattr(wall, 'HasAssociations'):
            for assoc in wall.HasAssociations:
                if assoc.is_a('IfcRelAssociatesMaterial'):
                    mat = assoc.RelatingMaterial
                    if mat.is_a('IfcMaterialLayerSet'):
                        total = sum([layer.LayerThickness for layer in mat.MaterialLayers])
                        return float(total)
    except Exception:
        pass
    
    return None


def extract_walls_from_ifc(ifc_path: str) -> List[Dict]:
    """
    Parse IFC file and extract wall evidence.
    
    Returns list of wall dicts with:
    - global_id, name, construction_family, thickness, materials, model_version
    """
    ifc_file = ifcopenshell.open(ifc_path)
    walls = []
    
    try:
        model_version = getattr(ifc_file, 'schema', 'IFC2x3')
    except:
        model_version = 'IFC2x3'
    
    for wall in ifc_file.by_type('IfcWall'):
        try:
            # Extract basic properties
            global_id = wall.GlobalId
            name = wall.Name or "Unnamed Wall"
            
            # Extract family from type name
            family = "Generic Wall"
            if wall.ObjectType:
                family = wall.ObjectType
            elif wall.Name:
                # Try to extract from name (e.g., "Basic Wall:Wall_Generic_55cm")
                if ':' in wall.Name:
                    family = wall.Name.split(':')[0]
            
            # Extract thickness
            thickness = get_wall_thickness_from_type(wall, ifc_file)
            
            # Extract materials
            materials = []
            if hasattr(wall, 'HasAssociations'):
                for assoc in wall.HasAssociations:
                    if assoc.is_a('IfcRelAssociatesMaterial'):
                        mat = assoc.RelatingMaterial
                        if mat.is_a('IfcMaterialLayerSet'):
                            for layer in mat.MaterialLayers:
                                if layer.Material:
                                    mat_name = layer.Material.Name or "Unknown"
                                    materials.append(mat_name)
                        elif hasattr(mat, 'Name'):
                            materials.append(mat.Name)
            
            walls.append({
                'global_id': global_id,
                'name': name,
                'construction_family': family,
                'total_thickness_m': thickness,
                'material_evidence': materials,
                'model_version': model_version,
            })
        except Exception as e:
            # Skip walls with extraction errors
            continue
    
    return walls


def sample_walls_from_ifc(ifc_path: str, sample_size: int = 5) -> List[Dict]:
    """Extract a sample of walls from IFC for demo purposes."""
    all_walls = extract_walls_from_ifc(ifc_path)
    if len(all_walls) <= sample_size:
        return all_walls
    
    # Return first, last, and middle walls for variety
    step = len(all_walls) // sample_size
    return [all_walls[i * step] for i in range(sample_size)]
