"""
ShivAI 2D Design Studio: Canvas Rendering and Vector SVG Exporter.
Transforms layered canvas documents into standard scalable vector graphics (SVG) and JSON templates.
"""
import uuid
import json
import logging
from typing import Dict, Any, List, Optional

from core.design.document import DesignProject, DesignLayer
from core.execution.artifacts import artifact_manager, StoredArtifact

logger = logging.getLogger("shivai.design.renderer")


class DesignRenderer:
    """Manages 2D layered canvas documents, transformations, and SVG exports."""

    PRESETS = {
        "social_banner": (1200, 630),
        "square_post": (1080, 1080),
        "youtube_thumbnail": (1280, 720),
        "app_icon": (512, 512),
        "game_sprite": (256, 256),
    }

    def __init__(self):
        self._projects: Dict[str, DesignProject] = {}

    def create_project(
        self,
        name: str,
        preset: str = "social_banner",
        custom_width: Optional[int] = None,
        custom_height: Optional[int] = None,
        background_color: str = "#0F172A",
    ) -> DesignProject:
        """Initializes a new layered design canvas."""
        w, h = self.PRESETS.get(preset, (1200, 630))
        if custom_width and custom_height:
            w, h = custom_width, custom_height

        project_id = f"des_{uuid.uuid4().hex[:10]}"
        project = DesignProject(
            project_id=project_id,
            name=name,
            canvas_width=w,
            canvas_height=h,
            background_color=background_color,
            layers=[],
            metadata={"preset": preset},
        )
        self._projects[project_id] = project
        logger.info(f"Created 2D design project '{name}' ({project_id}) - {w}x{h}")
        return project

    def get_project(self, project_id: str) -> Optional[DesignProject]:
        return self._projects.get(project_id)

    def add_shape(
        self,
        project_id: str,
        name: str = "Shape",
        shape_type: str = "rect",
        x: float = 50,
        y: float = 50,
        width: float = 200,
        height: float = 100,
        fill_color: str = "#3B82F6",
        border_radius: float = 8.0,
    ) -> Optional[DesignLayer]:
        """Adds a geometric shape layer."""
        project = self.get_project(project_id)
        if not project:
            return None

        layer_id = f"layer_{uuid.uuid4().hex[:8]}"
        layer = DesignLayer(
            layer_id=layer_id,
            name=name,
            layer_type="shape",
            shape_type=shape_type,
            x=x,
            y=y,
            width=width,
            height=height,
            fill_color=fill_color,
            border_radius=border_radius,
            z_index=len(project.layers),
        )
        project.layers.append(layer)
        return layer

    def add_text(
        self,
        project_id: str,
        text: str,
        name: str = "Headline",
        x: float = 80,
        y: float = 120,
        font_size: int = 48,
        font_color: str = "#FFFFFF",
        font_family: str = "Inter, sans-serif",
    ) -> Optional[DesignLayer]:
        """Adds a typography text layer."""
        project = self.get_project(project_id)
        if not project:
            return None

        layer_id = f"layer_{uuid.uuid4().hex[:8]}"
        layer = DesignLayer(
            layer_id=layer_id,
            name=name,
            layer_type="text",
            text_content=text,
            x=x,
            y=y,
            font_size=font_size,
            fill_color=font_color,
            font_family=font_family,
            z_index=len(project.layers),
        )
        project.layers.append(layer)
        return layer

    def add_image(
        self,
        project_id: str,
        image_url: str,
        name: str = "Image",
        x: float = 100,
        y: float = 100,
        width: float = 400,
        height: float = 400,
    ) -> Optional[DesignLayer]:
        """Adds an image or sprite layer."""
        project = self.get_project(project_id)
        if not project:
            return None

        layer_id = f"layer_{uuid.uuid4().hex[:8]}"
        layer = DesignLayer(
            layer_id=layer_id,
            name=name,
            layer_type="image",
            image_url=image_url,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=len(project.layers),
        )
        project.layers.append(layer)
        return layer

    def render_svg(self, project_id: str) -> str:
        """Renders the layered design project into a valid standalone SVG string."""
        project = self.get_project(project_id)
        if not project:
            raise FileNotFoundError(f"Design project '{project_id}' not found.")

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {project.canvas_width} {project.canvas_height}" '
            f'width="{project.canvas_width}" height="{project.canvas_height}">',
            f'  <rect width="100%" height="100%" fill="{project.background_color}" />',
        ]

        # Sort layers by z_index
        sorted_layers = sorted(project.layers, key=lambda l: l.z_index)

        for l in sorted_layers:
            if not l.visible:
                continue

            opacity_attr = f'opacity="{l.opacity}" ' if l.opacity < 1.0 else ""
            transform_attr = f'transform="rotate({l.rotation} {l.x + l.width/2} {l.y + l.height/2})" ' if l.rotation != 0 else ""

            if l.layer_type == "shape":
                if l.shape_type == "circle":
                    r = min(l.width, l.height) / 2
                    cx = l.x + r
                    cy = l.y + r
                    svg_parts.append(f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{l.fill_color}" {opacity_attr}{transform_attr}/>')
                else:  # rect
                    svg_parts.append(
                        f'  <rect x="{l.x}" y="{l.y}" width="{l.width}" height="{l.height}" rx="{l.border_radius}" '
                        f'fill="{l.fill_color}" {opacity_attr}{transform_attr}/>'
                    )
            elif l.layer_type == "text" and l.text_content:
                escaped_text = l.text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                svg_parts.append(
                    f'  <text x="{l.x}" y="{l.y}" font-family="{l.font_family}" font-size="{l.font_size}px" '
                    f'font-weight="{l.font_weight}" fill="{l.fill_color}" {opacity_attr}{transform_attr}>{escaped_text}</text>'
                )
            elif l.layer_type == "image" and l.image_url:
                svg_parts.append(
                    f'  <image href="{l.image_url}" x="{l.x}" y="{l.y}" width="{l.width}" height="{l.height}" '
                    f'{opacity_attr}{transform_attr}/>'
                )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def export_project(self, project_id: str, job_id: str) -> StoredArtifact:
        """Stores rendered SVG vector art as a permanent downloadable artifact."""
        svg_content = self.render_svg(project_id).encode("utf-8")
        return artifact_manager.store_bytes(
            job_id=job_id,
            name=f"{project_id}_design.svg",
            data=svg_content,
            mime_type="image/svg+xml",
            metadata={"type": "vector_design_svg"},
        )


design_renderer = DesignRenderer()
