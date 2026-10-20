"""
ShivAI V2 Creative and Engineering Studios API Router.
Unifies:
1. Video Studio: timeline assembly, preview render, and project export
2. 2D Design Studio: multi-layer canvas, SVG rendering, and vector export
3. 3D Asset Studio: procedural meshes, OBJ, GLB, and Three.js viewports
4. Game Studio: 2D Canvas and 3D Three.js playable games with headless validation
5. App Builder: multi-tier FastAPI + React/HTML5 full-stack apps with ZIP export
6. Software Engineer: repository analysis, bug diagnosis, and targeted surgical code patches
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from core.video.editor import video_editor
from core.design.renderer import design_renderer
from core.threed.scene import threed_studio
from core.games.generator import game_generator
from core.games.validator import game_validator, GameValidationResult
from core.app_builder.packager import app_packager
from core.agents.software_engineer import software_engineer, DiagnosisReport, PatchResult
from security.shiv_auth import get_current_user, UserContext

router = APIRouter(prefix="/v2/studios", tags=["Creative & Engineering Studios"])


# --- 1. Video Studio Requests ---
class CreateVideoTimelineRequest(BaseModel):
    name: str = "My Project"
    aspect_ratio: str = "16:9"  # "16:9", "9:16", "1:1", "4:5"
    fps: int = 30
    clips: List[Dict[str, Any]] = Field(default_factory=list)
    text_overlays: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/video/create")
def create_video_timeline(
    req: CreateVideoTimelineRequest,
    user: UserContext = Depends(get_current_user),
):
    """Creates a multi-track video timeline and calculates composite render manifest."""
    project = video_editor.create_timeline(name=req.name, aspect_ratio=req.aspect_ratio, fps=req.fps)
    for c in req.clips:
        video_editor.add_clip(
            project.project_id,
            source_url=c.get("source_url", ""),
            name=c.get("name", "Clip"),
            start_time=c.get("start_time", 0.0),
            end_time=c.get("end_time", 5.0),
        )
    for t in req.text_overlays:
        video_editor.add_text_overlay(
            project.project_id,
            text=t.get("text", "Subtitle"),
            start_time=t.get("start_time", 0.0),
            end_time=t.get("end_time", 5.0),
        )
    manifest = video_editor.render_manifest(project.project_id)
    return manifest


# --- 2. 2D Design Studio Requests ---
class CreateDesignRequest(BaseModel):
    name: str = "Banner Design"
    preset: str = "social_banner"
    background_color: str = "#0F172A"
    headline: Optional[str] = "Build with ShivAI"
    shapes: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/design/create")
def create_design(
    req: CreateDesignRequest,
    user: UserContext = Depends(get_current_user),
):
    """Creates a multi-layer design canvas and renders scalable vector SVG."""
    project = design_renderer.create_project(
        name=req.name,
        preset=req.preset,
        background_color=req.background_color,
    )
    # Add accent shape
    design_renderer.add_shape(
        project.project_id,
        name="Accent Card",
        x=60,
        y=60,
        width=project.canvas_width - 120,
        height=project.canvas_height - 120,
        fill_color="#1E293B",
        border_radius=16,
    )
    if req.headline:
        design_renderer.add_text(
            project.project_id,
            text=req.headline,
            x=100,
            y=140,
            font_size=42,
            font_color="#38BDF8",
        )
    svg_data = design_renderer.render_svg(project.project_id)
    return {
        "project_id": project.project_id,
        "name": project.name,
        "width": project.canvas_width,
        "height": project.canvas_height,
        "svg": svg_data,
    }


# --- 3. 3D Asset Studio Requests ---
class Create3DAssetRequest(BaseModel):
    name: str = "Crystal"
    mesh_type: str = "cube"  # cube, sphere, cylinder
    color: str = "#38BDF8"
    metallic: float = 0.2
    roughness: float = 0.5
    wireframe: bool = False


@router.post("/threed/create")
def create_3d_asset(
    req: Create3DAssetRequest,
    user: UserContext = Depends(get_current_user),
):
    """Generates procedural 3D geometry with OBJ and GLB export and Three.js preview."""
    asset = threed_studio.generate_asset(
        name=req.name,
        mesh_type=req.mesh_type,
        color_hex=req.color,
        metallic=req.metallic,
        roughness=req.roughness,
        wireframe=req.wireframe,
    )
    html_preview = threed_studio.generate_html_preview(asset["asset_id"])
    return {
        "asset_id": asset["asset_id"],
        "name": asset["name"],
        "mesh_type": asset["mesh_type"],
        "vertex_count": asset["vertex_count"],
        "triangle_count": asset["triangle_count"],
        "obj_size": len(asset["obj_content"]),
        "glb_size": len(asset["glb_bytes"]),
        "html_preview": html_preview,
    }


# --- 4. Game Development Studio Requests ---
class CreateGameRequest(BaseModel):
    title: str = "Space Runner"
    game_type: str = "2d"  # 2d, 3d
    player_speed: int = 5
    obstacle_speed: int = 4
    primary_color: str = "#38BDF8"


@router.post("/games/create")
def create_game(
    req: CreateGameRequest,
    user: UserContext = Depends(get_current_user),
):
    """Generates a complete, playable standalone HTML5 browser game and validates mechanics."""
    if req.game_type == "3d":
        html = game_generator.generate_3d_arena_game(title=req.title)
    else:
        html = game_generator.generate_2d_arcade_game(
            title=req.title,
            player_speed=req.player_speed,
            obstacle_speed=req.obstacle_speed,
            primary_color=req.primary_color,
        )
    validation = game_validator.validate_html5_game(html)
    return {
        "title": req.title,
        "game_type": req.game_type,
        "is_valid": validation.is_valid,
        "validation_checks": validation.checks_passed,
        "html_bundle": html,
    }


# --- 5. Full-Stack App Builder Requests ---
class CreateAppRequest(BaseModel):
    app_name: str = "TaskManager"
    entity_name: str = "Task"
    description: str = "A full-stack workflow management system."


@router.post("/apps/create")
def create_app(
    req: CreateAppRequest,
    user: UserContext = Depends(get_current_user),
):
    """Generates a complete multi-tier web application, validates syntax, and creates downloadable ZIP bundle."""
    return app_packager.create_and_package_app(
        user_id=user.user_id,
        app_name=req.app_name,
        entity_name=req.entity_name,
        description=req.description,
    )


# --- 6. Autonomous Software Engineer Requests ---
class DiagnoseRequest(BaseModel):
    error_log: str
    context_code: Optional[str] = None


class PatchRequest(BaseModel):
    original_code: str
    target_chunk: str
    replacement_chunk: str


@router.post("/engineer/diagnose", response_model=DiagnosisReport)
def diagnose_code_error(
    req: DiagnoseRequest,
    user: UserContext = Depends(get_current_user),
):
    """Diagnoses runtime errors and stack traces with recommended surgical fixes."""
    return software_engineer.diagnose_error(req.error_log, context_code=req.context_code)


@router.post("/engineer/patch", response_model=PatchResult)
def apply_code_patch(
    req: PatchRequest,
    user: UserContext = Depends(get_current_user),
):
    """Applies a non-destructive targeted patch to source code safely."""
    return software_engineer.apply_targeted_patch(
        original_code=req.original_code,
        target_chunk=req.target_chunk,
        replacement_chunk=req.replacement_chunk,
    )
