"""
Unit & Integration Tests for SHIV AI Creative Powers:
1. Custom Agent Forge
2. Multi-Step Workflow Engine
3. SHIV Codespaces & Live Previews
4. SHIV 3D Studio & WebGL Viewports
5. Autonomous Studio Intent Router
"""
import pytest
from core.agents.custom_agent_manager import custom_agent_manager
from core.automation.workflow_engine import workflow_engine, StepType
from core.codespaces.manager import codespace_manager
from core.threed.scene import threed_studio
from core.orchestration.studio_router import StudioIntentRouter
from core.tools.registry import tool_registry


def test_custom_agent_forge_lifecycle():
    # 1. Create custom agent
    agent = custom_agent_manager.create_agent(
        name="RustMaster",
        purpose="Writes high-performance memory-safe Rust code",
        instructions="Always write safe, idiomatic Rust.",
    )
    assert agent.agent_id.startswith("agent_")
    assert agent.name == "RustMaster"
    assert agent.key == "rustmaster"

    # 2. Get and list
    fetched = custom_agent_manager.get_agent(agent.agent_id)
    assert fetched is not None
    assert fetched.name == "RustMaster"

    all_agents = custom_agent_manager.list_agents()
    assert any(a.agent_id == agent.agent_id for a in all_agents)

    # 3. Update agent
    updated = custom_agent_manager.update_agent(agent.agent_id, purpose="Updated Rust Specialist")
    assert updated.purpose == "Updated Rust Specialist"

    # 4. Delete agent
    deleted = custom_agent_manager.delete_agent(agent.agent_id)
    assert deleted is True
    assert custom_agent_manager.get_agent(agent.agent_id) is None


@pytest.mark.asyncio
async def test_workflow_engine_execution():
    # 1. Create workflow
    steps = [
        {
            "step_id": "step_prompt",
            "name": "Generate Outline",
            "step_type": "ai_prompt",
            "params": {"prompt": "Create product roadmap"},
        },
        {
            "step_id": "step_script",
            "name": "Compute Metric",
            "step_type": "python_script",
            "params": {"code": "print(24 * 7)"},
            "depends_on": ["step_prompt"],
        },
    ]

    wf = workflow_engine.create_workflow(
        name="Product Pipeline",
        description="Automated product roadmap generator",
        steps=steps,
    )
    assert wf.workflow_id.startswith("wf_")
    assert len(wf.steps) == 2

    # 2. Execute workflow
    report = await workflow_engine.execute_workflow(wf.workflow_id)
    assert report.status == "COMPLETED"
    assert "step_prompt" in report.step_results
    assert report.step_results["step_prompt"].status == "SUCCESS"
    assert "step_script" in report.step_results
    assert report.step_results["step_script"].status == "SUCCESS"
    assert "168" in report.step_results["step_script"].output

    # 3. Cleanup
    workflow_engine.delete_workflow(wf.workflow_id)
    assert workflow_engine.get_workflow(wf.workflow_id) is None


@pytest.mark.asyncio
async def test_codespace_manager_full_lifecycle():
    # 1. Create codespace
    meta = codespace_manager.create_codespace(
        user_id="test_user",
        name="TaskTracker",
        template="html5_app",
    )
    assert meta.codespace_id.startswith("cs_")

    # 2. List files
    tree = codespace_manager.list_files(meta.codespace_id)
    file_names = [n.name for n in tree]
    assert "index.html" in file_names
    assert "app.js" in file_names

    # 3. Read file
    html = codespace_manager.read_file(meta.codespace_id, "index.html")
    assert "TaskTracker" in html

    # 4. Write new file
    codespace_manager.write_file(meta.codespace_id, "style.css", "body { background: black; }")
    assert "background: black" in codespace_manager.read_file(meta.codespace_id, "style.css")

    # 5. Patch file
    codespace_manager.patch_file(
        meta.codespace_id,
        "style.css",
        target_chunk="black",
        replacement_chunk="#0F172A",
    )
    assert "#0F172A" in codespace_manager.read_file(meta.codespace_id, "style.css")

    # 6. Preview file
    content, mime = codespace_manager.get_preview_file(meta.codespace_id, "index.html")
    assert b"<!DOCTYPE html>" in content
    assert mime == "text/html"

    # 7. Execute terminal command
    cmd_res = await codespace_manager.execute_command(meta.codespace_id, "python -c \"print('CODESPACE_TEST_OK')\"")
    assert cmd_res.success is True
    assert "CODESPACE_TEST_OK" in cmd_res.stdout

    # 8. Export as zip
    zip_bytes = codespace_manager.export_as_zip(meta.codespace_id)
    assert len(zip_bytes) > 100

    # 9. Delete codespace
    deleted = codespace_manager.delete_codespace(meta.codespace_id)
    assert deleted is True


def test_3d_studio_generation_and_preview():
    asset = threed_studio.generate_asset(
        name="NeonSpaceship",
        mesh_type="cylinder",
        color_hex="#06B6D4",
    )
    assert asset["asset_id"].startswith("3d_")
    assert asset["mesh_type"] == "cylinder"
    assert len(asset["glb_bytes"]) > 0

    html = threed_studio.generate_html_preview(asset["asset_id"])
    assert "THREE.Scene()" in html
    assert "NeonSpaceship" in html


def test_studio_intent_router_matches():
    # 3D intent
    res_3d = StudioIntentRouter.match_and_execute("create a 3D model of a golden rocket")
    assert res_3d is not None
    assert "SHIV 3D Studio" in res_3d
    assert "Golden Rocket" in res_3d
    assert "/v2/studios/threed/" in res_3d

    # Codespace website intent
    res_cs = StudioIntentRouter.match_and_execute("create a web app for portfolio")
    assert res_cs is not None
    assert "SHIV Codespaces" in res_cs
    assert "/v2/codespaces/" in res_cs

    # Dynamic Agent intent
    res_agent = StudioIntentRouter.match_and_execute("create an agent named SqlMaster with instructions to write SQLite queries")
    assert res_agent is not None
    assert "SHIV Agent Forge" in res_agent
    assert "SqlMaster" in res_agent

    # Workflow intent
    res_wf = StudioIntentRouter.match_and_execute("create a workflow for daily news summary")
    assert res_wf is not None
    assert "SHIV Workflow Forge" in res_wf

    # Image intent
    res_img = StudioIntentRouter.match_and_execute("generate an image of a neon cybernetic tiger")
    assert res_img is not None
    assert "SHIV Editor" in res_img
    assert "https://image.pollinations.ai" in res_img

    # Unmatched regular question
    res_regular = StudioIntentRouter.match_and_execute("what is the capital of France?")
    assert res_regular is None


def test_creative_tools_registered_in_registry():
    assert tool_registry.get_tool("agent_forge") is not None
    assert tool_registry.get_tool("workflow_forge") is not None
    assert tool_registry.get_tool("codespace_manage") is not None
    assert tool_registry.get_tool("shiv_editor") is not None
    assert tool_registry.get_tool("shiv_3d") is not None
