"""
ShivAI Universal Task Planner and DAG Decomposition Engine.
Transforms high-level user requests into ordered, dependency-aware, verifiable execution plans.
Assigns specialized agents, specifies required tools, and establishes concrete validation checkpoints.
"""
import uuid
import time
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from core.orchestration.intent import intent_classifier, IntentClassification

logger = logging.getLogger("shivai.orchestration.planner")


class PlanStep(BaseModel):
    step_id: str
    name: str
    assigned_agent: str
    description: str
    depends_on: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    validation_criteria: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    output: Optional[str] = None
    execution_time_ms: float = 0.0


class ExecutionPlan(BaseModel):
    plan_id: str
    goal: str
    intent: IntentClassification
    steps: List[PlanStep] = Field(default_factory=list)
    estimated_duration_seconds: float = 10.0
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    is_completed: bool = False


class TaskPlanner:
    """Generates structured DAG execution plans based on classified intent and domain blueprints."""

    def plan(self, goal: str) -> ExecutionPlan:
        """Decomposes user goal into ordered, verifiable execution steps."""
        intent = intent_classifier.classify(goal)
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        steps = []

        cat = intent.primary_intent

        if cat == "fullstack_development":
            steps = [
                PlanStep(
                    step_id="step_1_arch",
                    name="Architecture & API Specification",
                    assigned_agent="planner",
                    description="Deconstruct requirements into database schemas, REST endpoints, and UI state flows.",
                    depends_on=[],
                    required_tools=["datetime"],
                    validation_criteria="Detailed schema, API contract, and component layout defined.",
                ),
                PlanStep(
                    step_id="step_2_backend",
                    name="Backend Service & Database Implementation",
                    assigned_agent="app_builder",
                    description="Implement FastAPI / Express models, routes, business logic, and validation schemas.",
                    depends_on=["step_1_arch"],
                    required_tools=["sandboxed_python"],
                    validation_criteria="All endpoints implemented with type safety and error handlers.",
                ),
                PlanStep(
                    step_id="step_3_frontend",
                    name="Frontend UI & Integration",
                    assigned_agent="engineer",
                    description="Build responsive React / HTML5 UI views, form controls, and API client state.",
                    depends_on=["step_2_backend"],
                    required_tools=[],
                    validation_criteria="Modern responsive UI with loading, error, and interaction states.",
                ),
                PlanStep(
                    step_id="step_4_validate",
                    name="Automated Test Suite & Build Verification",
                    assigned_agent="tester",
                    description="Run static checks, unit tests, and build diagnostics in isolated sandbox.",
                    depends_on=["step_3_frontend"],
                    required_tools=["sandboxed_python"],
                    validation_criteria="All test assertions pass with zero syntax or compilation errors.",
                ),
                PlanStep(
                    step_id="step_5_deliver",
                    name="Package & Export Deliverable Bundle",
                    assigned_agent="app_builder",
                    description="Generate environment templates, README documentation, and exportable ZIP archive.",
                    depends_on=["step_4_validate"],
                    required_tools=[],
                    validation_criteria="Complete ZIP archive ready for download and local run.",
                ),
            ]
        elif cat in ("game_development_2d", "game_development_3d"):
            is_3d = cat == "game_development_3d"
            steps = [
                PlanStep(
                    step_id="step_1_mechanics",
                    name="Gameplay Mechanics & Asset Blueprint",
                    assigned_agent="game_developer",
                    description=f"Define player controls, rules, score logic, and {'Three.js 3D' if is_3d else 'Canvas 2D'} scene layout.",
                    depends_on=[],
                    required_tools=[],
                    validation_criteria="Game loop, physics model, and entity definitions finalized.",
                ),
                PlanStep(
                    step_id="step_2_engine",
                    name="Core Game Engine & Controllers",
                    assigned_agent="game_developer",
                    description="Implement player movement, collision detection, enemy behavior, and input handlers.",
                    depends_on=["step_1_mechanics"],
                    required_tools=[],
                    validation_criteria="Playable loop running at 60 FPS without unbounded state growth.",
                ),
                PlanStep(
                    step_id="step_3_ui_sound",
                    name="HUD, Audio & State System",
                    assigned_agent="game_developer",
                    description="Integrate score display, life counters, restart logic, and sound synthesis.",
                    depends_on=["step_2_engine"],
                    required_tools=[],
                    validation_criteria="Full UI overlay with game over and restart cycle.",
                ),
                PlanStep(
                    step_id="step_4_verify",
                    name="Headless Simulation & Test Verification",
                    assigned_agent="tester",
                    description="Run headless sanity check to ensure game code compiles without fatal errors.",
                    depends_on=["step_3_ui_sound"],
                    required_tools=["sandboxed_python"],
                    validation_criteria="Verification script reports zero syntax or runtime exceptions.",
                ),
                PlanStep(
                    step_id="step_5_bundle",
                    name="Playable HTML5 Bundle Assembly",
                    assigned_agent="game_developer",
                    description="Assemble standalone playable single-file HTML5 bundle ready for browser play.",
                    depends_on=["step_4_verify"],
                    required_tools=[],
                    validation_criteria="Self-contained playable index.html bundle generated.",
                ),
            ]
        elif cat == "video_creation_editing":
            steps = [
                PlanStep(
                    step_id="step_1_media_ingest",
                    name="Media Ingestion & Timeline Layout",
                    assigned_agent="video_editor",
                    description="Analyze input clips, resolution, FPS, duration, and arrange timeline sequence.",
                    depends_on=[],
                    required_tools=[],
                    validation_criteria="Timeline track schema validated with timestamps and durations.",
                ),
                PlanStep(
                    step_id="step_2_effects",
                    name="Transitions, Text & Audio Mixing",
                    assigned_agent="video_editor",
                    description="Apply cuts, volume balance, text titles, and subtitle overlays.",
                    depends_on=["step_1_media_ingest"],
                    required_tools=[],
                    validation_criteria="Visual and audio tracks aligned with target aspect ratio.",
                ),
                PlanStep(
                    step_id="step_3_render",
                    name="Render Preview & Export Job",
                    assigned_agent="video_editor",
                    description="Execute deterministic video processing job and verify exported MP4.",
                    depends_on=["step_2_effects"],
                    required_tools=[],
                    validation_criteria="Valid video file created and accessible in artifact store.",
                ),
            ]
        elif cat == "modeling_3d":
            steps = [
                PlanStep(
                    step_id="step_1_geometry",
                    name="Procedural Geometry & Mesh Generation",
                    assigned_agent="threed_specialist",
                    description="Compute vertex buffers, normal vectors, indices, and UV mappings for target 3D asset.",
                    depends_on=[],
                    required_tools=["sandboxed_python"],
                    validation_criteria="Non-degenerate geometric mesh created with valid bounds.",
                ),
                PlanStep(
                    step_id="step_2_materials",
                    name="PBR Material & Lighting Configuration",
                    assigned_agent="threed_specialist",
                    description="Assign albedo, roughness, metallic, and scene camera parameters.",
                    depends_on=["step_1_geometry"],
                    required_tools=[],
                    validation_criteria="PBR shader parameters and environment lighting verified.",
                ),
                PlanStep(
                    step_id="step_3_export",
                    name="GLB / glTF Binary Encoding & Inspection",
                    assigned_agent="threed_specialist",
                    description="Export standard GLB container and verify WebGL / Three.js readability.",
                    depends_on=["step_2_materials"],
                    required_tools=[],
                    validation_criteria="Standard GLB file verified and ready for browser viewport rendering.",
                ),
            ]
        elif cat == "design_2d":
            steps = [
                PlanStep(
                    step_id="step_1_canvas",
                    name="Canvas Setup & Layer Architecture",
                    assigned_agent="designer_2d",
                    description="Set canvas dimensions, background palette, and hierarchical layer stack.",
                    depends_on=[],
                    required_tools=[],
                    validation_criteria="Target resolution and layer hierarchy initialized.",
                ),
                PlanStep(
                    step_id="step_2_composition",
                    name="Visual Elements & Generative Asset Injection",
                    assigned_agent="designer_2d",
                    description="Place typography, vector shapes, logos, and FLUX visual assets on canvas.",
                    depends_on=["step_1_canvas"],
                    required_tools=[],
                    validation_criteria="Design layers positioned with x, y, width, height, and z-index.",
                ),
                PlanStep(
                    step_id="step_3_export",
                    name="Vector SVG & Raster PNG Rendering",
                    assigned_agent="designer_2d",
                    description="Render layer tree into exportable SVG and PNG formats.",
                    depends_on=["step_2_composition"],
                    required_tools=[],
                    validation_criteria="Clean vector SVG and high-resolution raster exported.",
                ),
            ]
        elif cat == "coding_debugging":
            steps = [
                PlanStep(
                    step_id="step_1_inspect",
                    name="Code Inspection & Diagnosis",
                    assigned_agent="engineer",
                    description="Analyze error traceback, source files, and dependencies to pinpoint root cause.",
                    depends_on=[],
                    required_tools=["sandboxed_python"],
                    validation_criteria="Identified root cause and scope of necessary patch.",
                ),
                PlanStep(
                    step_id="step_2_patch",
                    name="Targeted Patch Application",
                    assigned_agent="engineer",
                    description="Apply minimal, surgical code refactoring without destructive modifications.",
                    depends_on=["step_1_inspect"],
                    required_tools=[],
                    validation_criteria="Clean code patch produced with full type annotations.",
                ),
                PlanStep(
                    step_id="step_3_test",
                    name="Regression & Test Execution",
                    assigned_agent="tester",
                    description="Run unit test suite in sandboxed environment to verify resolution.",
                    depends_on=["step_2_patch"],
                    required_tools=["sandboxed_python"],
                    validation_criteria="100% green tests with zero regressions.",
                ),
            ]
        else:  # General conversation / research default
            steps = [
                PlanStep(
                    step_id="step_1_investigate",
                    name="Research & Fact Synthesis",
                    assigned_agent="researcher",
                    description="Investigate evidence, cross-reference sources, and structure verified facts.",
                    depends_on=[],
                    required_tools=["web_search"],
                    validation_criteria="Verified facts with clear attribution.",
                ),
                PlanStep(
                    step_id="step_2_synthesize",
                    name="Deliverable Formulation",
                    assigned_agent="writer",
                    description="Formulate structured, articulate response addressing all user goals.",
                    depends_on=["step_1_investigate"],
                    required_tools=[],
                    validation_criteria="Clear, comprehensive, actionable delivery.",
                ),
            ]

        plan = ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            intent=intent,
            steps=steps,
            estimated_duration_seconds=len(steps) * 3.5,
        )
        logger.info(f"Generated {len(steps)}-step execution plan ({plan_id}) for intent '{cat}'")
        return plan


task_planner = TaskPlanner()
