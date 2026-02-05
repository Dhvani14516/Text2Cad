"""
UMACAD - Unified Multi-Agent Collaborative Design
Core Data Structures for Design Brief
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class GeometricRelationship(str, Enum):
    """Types of geometric relationships"""
    PERPENDICULAR = "perpendicular"
    PARALLEL = "parallel"
    CONCENTRIC = "concentric"
    ALIGNED = "aligned"
    TANGENT = "tangent"
    OFFSET = "offset"


class DimensionType(str, Enum):
    """Types of dimensions"""
    LENGTH = "length"
    WIDTH = "width"
    HEIGHT = "height"
    DIAMETER = "diameter"
    RADIUS = "radius"
    THICKNESS = "thickness"
    ANGLE = "angle"
    DISTANCE = "distance"


class Dimension(BaseModel):
    """Represents a specific dimension with value and tolerance"""
    name: str = Field(..., description="Name of the dimension")
    type: DimensionType = Field(..., description="Type of dimension")
    value: float = Field(..., description="Nominal value")
    unit: str = Field(default="mm", description="Unit of measurement")
    tolerance: Optional[float] = Field(None, description="Tolerance value")
    tolerance_type: Optional[str] = Field(None, description="± or +/- or unilateral")


class GeometricFeature(BaseModel):
    """Represents a geometric feature in the design"""
    feature_id: str = Field(..., description="Unique identifier for the feature")
    feature_type: str = Field(..., description="Type: block, hole, cylinder, etc.")
    dimensions: List[Dimension] = Field(default_factory=list)
    position: Dict[str, float] = Field(default_factory=dict, description="x, y, z position")
    relationships: Dict[str, str] = Field(default_factory=dict, description="Relationships to other features")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MaterialSpecification(BaseModel):
    """Material properties and requirements"""
    material_name: Optional[str] = Field(None, description="Material name")
    material_type: Optional[str] = Field(None, description="Metal, plastic, composite, etc.")
    properties: Dict[str, Any] = Field(default_factory=dict)
    finish: Optional[str] = Field(None, description="Surface finish requirements")


class DesignBrief(BaseModel):
    """
    Structured, machine-readable design specification
    Output of Phase 1: Requirements Analyst
    """
    brief_id: str = Field(..., description="Unique identifier for this design brief")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # User Input
    user_input_text: str = Field(..., description="Original user text input")
    user_input_image_path: Optional[str] = Field(None, description="Path to uploaded sketch/image")
    
    # High-Level Description
    design_title: str = Field(..., description="Short title of the design")
    design_description: str = Field(..., description="Detailed description")
    design_category: Optional[str] = Field(None, description="bracket, housing, connector, etc.")
    
    # Detailed Specifications
    features: List[GeometricFeature] = Field(default_factory=list)
    global_dimensions: List[Dimension] = Field(default_factory=list)
    material: Optional[MaterialSpecification] = Field(None)
    
    # Constraints and Requirements
    constraints: List[str] = Field(default_factory=list, description="Design constraints")
    functional_requirements: List[str] = Field(default_factory=list)
    manufacturing_requirements: List[str] = Field(default_factory=list)
    
    # Ambiguities Resolved
    clarification_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Q&A history from RA agent"
    )
    
    # Metadata
    confidence_score: float = Field(default=1.0, description="RA's confidence in completeness")
    tags: List[str] = Field(default_factory=list, description="Tags for EDR indexing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "brief_id": "brief_001",
                "design_title": "L-Shaped Shelf Bracket",
                "design_description": "An L-shaped bracket with two perpendicular legs and mounting holes",
                "features": [
                    {
                        "feature_id": "leg_short",
                        "feature_type": "rectangular_block",
                        "dimensions": [
                            {"name": "length", "type": "length", "value": 50.0, "unit": "mm"},
                            {"name": "width", "type": "width", "value": 40.0, "unit": "mm"},
                            {"name": "thickness", "type": "thickness", "value": 5.0, "unit": "mm"}
                        ]
                    }
                ],
                "tags": ["bracket", "L-shape", "mounting"]
            }
        }
    
    def to_json_file(self, filepath: str) -> None:
        """Export design brief to JSON file"""
        with open(filepath, 'w') as f:
            f.write(self.model_dump_json(indent=2))
    
    @classmethod
    def from_json_file(cls, filepath: str) -> 'DesignBrief':
        """Load design brief from JSON file"""
        with open(filepath, 'r') as f:
            return cls.model_validate_json(f.read())
