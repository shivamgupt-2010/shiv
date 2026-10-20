"""
ShivAI 2D Design Studio: Layered Vector & Raster Document Models.
Provides an editable, multi-layer canvas architecture for graphics, banners, sprites, and UI assets.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DesignLayer(BaseModel):
    layer_id: str
    name: str = "Layer"
    layer_type: str = "shape"  # "shape", "text", "image", "sprite"
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 100.0
    rotation: float = 0.0
    opacity: float = 1.0
    z_index: int = 0
    visible: bool = True
    locked: bool = False

    # Shape properties
    shape_type: Optional[str] = "rect"  # "rect", "circle", "ellipse", "star"
    fill_color: Optional[str] = "#3B82F6"
    stroke_color: Optional[str] = None
    stroke_width: float = 0.0
    border_radius: float = 0.0

    # Text properties
    text_content: Optional[str] = None
    font_family: str = "Inter, sans-serif"
    font_size: int = 24
    font_weight: str = "bold"
    text_align: str = "left"

    # Image / Sprite properties
    image_url: Optional[str] = None


class DesignProject(BaseModel):
    project_id: str
    name: str
    canvas_width: int = 1200
    canvas_height: int = 630
    background_color: str = "#0F172A"
    layers: List[DesignLayer] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
