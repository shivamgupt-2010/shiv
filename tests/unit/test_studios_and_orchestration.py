"""
Comprehensive Unit Tests for ShivAI Universal Orchestration, Studios, Job Queue, and Engineering Agent.
"""
import pytest
import asyncio
import tempfile
import os

from core.orchestration.intent import intent_classifier, UniversalIntentClassifier
from core.orchestration.planner import task_planner, TaskPlanner
from core.execution.job_queue import JobQueue, JobPriority, JobStatus
from core.execution.artifacts import ArtifactManager
from core.video.editor import video_editor
from core.design.renderer import design_renderer
from core.threed.generator import ProceduralMeshGenerator
from core.threed.scene import threed_studio
from core.games.generator import game_generator
from core.games.validator import game_validator
from core.app_builder.generator import fullstack_generator
from core.app_builder.packager import app_packager
from core.agents.software_engineer import software_engineer


# ---------------------------------------------------------------------------
# 1. Intent Recognition Tests
# ---------------------------------------------------------------------------
def test_intent_classification_domains():
    c1 = intent_classifier.classify("Build a fullstack SaaS application with FastAPI and React")
    assert c1.primary_intent == "fullstack_development"
    assert c1.recommended_agent == "app_builder"

    c2 = intent_classifier.classify("Create a 2D platformer game with player controls and score")
    assert c2.primary_intent == "game_development_2d"
    assert c2.recommended_agent == "game_developer"

    c3 = intent_classifier.classify("Trim this video clip, add subtitles and render at 30 fps")
    assert c3.primary_intent == "video_creation_editing"
    assert c3.recommended_agent == "video_editor"

    c4 = intent_classifier.classify("Generate a 3D procedural cube mesh and export as GLB")
    assert c4.primary_intent == "modeling_3d"
    assert c4.recommended_agent == "threed_specialist"

    c5 = intent_classifier.classify("Design a social media banner poster with vibrant colors")
    assert c5.primary_intent == "design_2d"
    assert c5.recommended_agent == "designer_2d"


def test_intent_ambiguity_and_multi_intent():
    res = intent_classifier.classify("app")
    assert res.is_ambiguous is True
    assert res.clarification_question is not None

    multi = intent_classifier.classify("Design a 2D logo sprite and build a 2D game using it")
    assert "game_development_2d" in [multi.primary_intent] + multi.secondary_intents
    assert "design_2d" in [multi.primary_intent] + multi.secondary_intents


# ---------------------------------------------------------------------------
# 2. Task Planning Tests
# ---------------------------------------------------------------------------
def test_task_planner_dag():
    plan = task_planner.plan("Build a full-stack inventory management web application")
    assert len(plan.steps) >= 4
    assert plan.steps[0].assigned_agent == "planner"
    assert plan.steps[1].depends_on == ["step_1_arch"]

    game_plan = task_planner.plan("Create a 2D space shooter game")
    assert any("game_developer" in s.assigned_agent for s in game_plan.steps)
    assert any("tester" in s.assigned_agent for s in game_plan.steps)


# ---------------------------------------------------------------------------
# 3. Artifact Storage Tests
# ---------------------------------------------------------------------------
def test_artifact_manager_hashing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = ArtifactManager(base_dir=tmp_dir)
        payload = b"Hello ShivAI Artifacts 2026!"
        art = mgr.store_bytes("job_test_1", "test.txt", payload, mime_type="text/plain")
        assert art.size_bytes == len(payload)
        assert art.sha256_checksum is not None
        assert os.path.exists(art.absolute_path)

        # Retrieval check
        path = mgr.get_artifact_path("job_test_1", "test.txt")
        assert path == art.absolute_path

        # Listing check
        listed = mgr.list_artifacts("job_test_1")
        assert len(listed) == 1
        assert listed[0].name == "test.txt"


# ---------------------------------------------------------------------------
# 4. Asynchronous Job Queue Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_queue_execution():
    queue = JobQueue(max_concurrent_workers=2)

    async def sample_handler(job, progress_cb):
        progress_cb(50.0, "Halfway there")
        await asyncio.sleep(0.05)
        progress_cb(100.0, "Done")
        return {"processed": True, "count": job.payload.get("count", 0) * 2}

    queue.register_handler("test_task", sample_handler)
    job = await queue.submit_job("user_test", "test_task", {"count": 21}, priority=JobPriority.HIGH)

    # Wait for execution
    for _ in range(50):
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.05)

    assert job.status == JobStatus.COMPLETED
    assert job.result == {"processed": True, "count": 42}
    assert job.progress.percentage == 100.0

    await queue.stop()


@pytest.mark.asyncio
async def test_job_queue_cancellation():
    queue = JobQueue(max_concurrent_workers=1)

    async def long_handler(job, progress_cb):
        await asyncio.sleep(5.0)
        return {"done": True}

    queue.register_handler("long_task", long_handler)
    job = await queue.submit_job("user_test", "long_task", {})

    await asyncio.sleep(0.05)
    cancelled = await queue.cancel_job(job.job_id, user_id="user_test")
    assert cancelled is True
    assert job.status == JobStatus.CANCELLED

    await queue.stop()


# ---------------------------------------------------------------------------
# 5. Video Studio Tests
# ---------------------------------------------------------------------------
def test_video_studio_timeline():
    proj = video_editor.create_timeline("Cyber Promo", aspect_ratio="16:9")
    assert proj.width == 1920
    assert proj.height == 1080

    clip1 = video_editor.add_clip(proj.project_id, "https://example.com/clip1.mp4", duration=4.0)
    clip2 = video_editor.add_clip(proj.project_id, "https://example.com/clip2.mp4", duration=6.0)
    assert clip1 is not None
    assert clip2.timeline_start == 4.0

    txt = video_editor.add_text_overlay(proj.project_id, "Welcome to ShivAI", start_time=1.0, end_time=5.0)
    assert txt is not None

    manifest = video_editor.render_manifest(proj.project_id)
    assert manifest["total_duration"] == 10.0
    assert len(manifest["tracks"][0]["clips"]) == 2
    assert len(manifest["text_overlays"]) == 1


# ---------------------------------------------------------------------------
# 6. 2D Design Studio Tests
# ---------------------------------------------------------------------------
def test_design_studio_rendering():
    des = design_renderer.create_project("Header Card", preset="social_banner")
    assert des.canvas_width == 1200
    assert des.canvas_height == 630

    shape = design_renderer.add_shape(des.project_id, name="Card Background", fill_color="#1E293B")
    assert shape is not None

    text = design_renderer.add_text(des.project_id, text="ShivAI Next-Gen Design")
    assert text is not None

    svg_str = design_renderer.render_svg(des.project_id)
    assert "<svg" in svg_str
    assert "viewBox=\"0 0 1200 630\"" in svg_str
    assert "ShivAI Next-Gen Design" in svg_str
    assert "</svg>" in svg_str


# ---------------------------------------------------------------------------
# 7. 3D Asset Studio Tests
# ---------------------------------------------------------------------------
def test_threed_asset_studio():
    # Test Procedural Mesh Generation
    cube = ProceduralMeshGenerator.create_cube(size=2.0)
    assert len(cube.vertices) == 24
    assert len(cube.indices) == 36

    obj_str = ProceduralMeshGenerator.to_obj_string(cube)
    assert "v " in obj_str
    assert "f " in obj_str

    glb_bytes = ProceduralMeshGenerator.to_glb_bytes(cube)
    assert len(glb_bytes) > 100
    # Magic bytes check: 'glTF' in hex 0x46546C67 (little-endian: 0x67, 0x6c, 0x54, 0x46 -> b'glTF')
    assert glb_bytes[:4] == b"glTF"

    # Test Studio API
    scene = threed_studio.generate_asset("Glowing Orb", mesh_type="sphere")
    assert scene["vertex_count"] > 0
    assert scene["triangle_count"] > 0

    preview = threed_studio.generate_html_preview(scene["asset_id"])
    assert "<!DOCTYPE html>" in preview
    assert "THREE.WebGLRenderer" in preview


# ---------------------------------------------------------------------------
# 8. Game Development Studio Tests
# ---------------------------------------------------------------------------
def test_game_generation_and_validation():
    # 2D Arcade Game
    game_html = game_generator.generate_2d_arcade_game(title="Neon Defender")
    val_2d = game_validator.validate_html5_game(game_html)
    assert val_2d.is_valid is True
    assert val_2d.has_audio is True
    assert "Standard 60 FPS requestAnimationFrame game loop" in val_2d.checks_passed

    # 3D Arena Game
    game_3d = game_generator.generate_3d_arena_game(title="Cyber Horizon 3D")
    val_3d = game_validator.validate_html5_game(game_3d)
    assert val_3d.is_valid is True


# ---------------------------------------------------------------------------
# 9. Full-Stack App Builder Tests
# ---------------------------------------------------------------------------
def test_fullstack_app_builder():
    res = app_packager.create_and_package_app(
        user_id="dev_user",
        app_name="ExpenseTracker",
        entity_name="Expense",
        description="Personal finance tracker",
    )
    assert res["validation_passed"] is True
    assert "main.py" in res["files"]
    assert "index.html" in res["files"]
    assert res["artifact"]["mime_type"] == "application/zip"
    assert os.path.exists(res["artifact"]["absolute_path"])


# ---------------------------------------------------------------------------
# 10. Autonomous Software Engineer Tests
# ---------------------------------------------------------------------------
def test_software_engineer_diagnostics_and_patching():
    # Diagnostic test
    diag = software_engineer.diagnose_error("SyntaxError: invalid syntax on line 42")
    assert diag.error_type == "SyntaxError"

    # Patching test
    orig = "def add(a, b):\n    return a - b\n"
    patch_res = software_engineer.apply_targeted_patch(
        original_code=orig,
        target_chunk="return a - b",
        replacement_chunk="return a + b",
    )
    assert patch_res.success is True
    assert "return a + b" in patch_res.patched_code

    # Multi-occurrence safety failure test
    multi = "print('hi')\nprint('hi')\n"
    failed_patch = software_engineer.apply_targeted_patch(multi, "print('hi')", "print('bye')")
    assert failed_patch.success is False
    assert "multiple locations" in failed_patch.error


@pytest.mark.asyncio
async def test_software_engineer_sandboxed_test_runner():
    src = "def multiply(x, y):\n    return x * y\n"
    tests = (
        "class TestMath(unittest.TestCase):\n"
        "    def test_mul(self):\n"
        "        self.assertEqual(module.multiply(3, 4), 12)\n"
    )
    res = await software_engineer.run_sandboxed_tests(src, tests)
    assert res.success is True
    assert "Ran 1 test" in res.stderr or "OK" in res.stderr
