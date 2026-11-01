"""
SHIV AI Creative & Studio Tools.
Registers native studio tools into the AI Tool Registry so SHIV AI can
autonomously create agents, workflows, codespaces, videos, images, and 3D scenes
when prompted by users from the launcher or chat interface.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from core.tools.base import Tool, ToolDefinition, ToolParameter
from core.agents.custom_agent_manager import custom_agent_manager
from core.automation.workflow_engine import workflow_engine
from core.codespaces.manager import codespace_manager
from core.threed.scene import threed_studio
from core.video.editor import video_editor
from core.design.renderer import design_renderer

logger = logging.getLogger("shivai.tools.creative")


class AgentForgeTool(Tool):
    """Allows SHIV AI to create, list, and delete custom AI agents."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="agent_forge",
                description="Creates, manages, and deletes custom specialized AI agents in ShivAI. Use whenever the user asks to create a custom agent, persona, or specialist.",
                required_permission="agents",
                parameters=[
                    ToolParameter(name="action", type="string", description="'create', 'list', or 'delete'"),
                    ToolParameter(name="name", type="string", description="Name of the agent", required=False),
                    ToolParameter(name="purpose", type="string", description="Purpose or job description", required=False),
                    ToolParameter(name="instructions", type="string", description="System prompt instructions", required=False),
                    ToolParameter(name="agent_id", type="string", description="Agent ID (required for delete)", required=False),
                ],
            )
        )

    async def run(
        self,
        action: str = "list",
        name: str = "",
        purpose: str = "",
        instructions: str = "",
        agent_id: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        if action == "create":
            if not name or not instructions:
                return {"success": False, "error": "name and instructions are required to create an agent."}
            agent = custom_agent_manager.create_agent(
                name=name,
                purpose=purpose or f"Custom specialist {name}",
                instructions=instructions,
            )
            return {
                "success": True,
                "message": f"Successfully created and registered agent '{agent.name}'!",
                "agent_id": agent.agent_id,
                "key": agent.key,
            }
        elif action == "delete":
            if not agent_id:
                return {"success": False, "error": "agent_id is required to delete."}
            ok = custom_agent_manager.delete_agent(agent_id)
            return {"success": ok, "message": f"Agent {agent_id} deleted." if ok else "Agent not found."}
        else:
            agents = custom_agent_manager.list_agents()
            return {"success": True, "agents": [a.model_dump() for a in agents]}


class WorkflowForgeTool(Tool):
    """Allows SHIV AI to author, list, and execute multi-step automated workflows."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="workflow_forge",
                description="Creates and executes multi-step automated DAG workflows in ShivAI. Use whenever user asks to create or run an automated multi-step workflow.",
                required_permission="automation",
                parameters=[
                    ToolParameter(name="action", type="string", description="'create', 'execute', or 'list'"),
                    ToolParameter(name="name", type="string", description="Workflow title", required=False),
                    ToolParameter(name="description", type="string", description="Summary of workflow", required=False),
                    ToolParameter(name="steps", type="array", description="List of step objects", required=False),
                    ToolParameter(name="workflow_id", type="string", description="ID of workflow (for execute)", required=False),
                ],
            )
        )

    async def run(
        self,
        action: str = "list",
        name: str = "",
        description: str = "",
        steps: Optional[List[Dict[str, Any]]] = None,
        workflow_id: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        if action == "create":
            if not name or not steps:
                return {"success": False, "error": "name and steps list are required."}
            wf = workflow_engine.create_workflow(name=name, steps=steps, description=description)
            return {
                "success": True,
                "message": f"Workflow '{wf.name}' created with {len(wf.steps)} steps.",
                "workflow_id": wf.workflow_id,
            }
        elif action == "execute":
            if not workflow_id:
                return {"success": False, "error": "workflow_id is required to execute."}
            report = await workflow_engine.execute_workflow(workflow_id)
            return {
                "success": report.status == "COMPLETED",
                "status": report.status,
                "execution_id": report.execution_id,
                "step_results": {k: v.model_dump() for k, v in report.step_results.items()},
                "total_time_ms": report.total_time_ms,
            }
        else:
            all_wf = workflow_engine.list_workflows()
            return {"success": True, "workflows": [w.model_dump() for w in all_wf]}


class CodespaceTool(Tool):
    """Allows SHIV AI to create websites, web apps, write files, and run terminal commands."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="codespace_manage",
                description="Creates and manages full web applications, websites, codebases, files, and executes terminal commands in SHIV Codespaces.",
                required_permission="codespaces",
                parameters=[
                    ToolParameter(name="action", type="string", description="'create_app', 'write_file', 'read_file', 'execute_command', or 'list'"),
                    ToolParameter(name="name", type="string", description="Name of the app/codespace", required=False),
                    ToolParameter(name="template", type="string", description="'html5_app' or 'python_fastapi'", required=False),
                    ToolParameter(name="codespace_id", type="string", description="Target codespace ID", required=False),
                    ToolParameter(name="file_path", type="string", description="Relative file path", required=False),
                    ToolParameter(name="content", type="string", description="Content to write", required=False),
                    ToolParameter(name="command", type="string", description="Terminal command to run", required=False),
                ],
            )
        )

    async def run(
        self,
        action: str = "create_app",
        name: str = "MyWebApp",
        template: str = "html5_app",
        codespace_id: str = "",
        file_path: str = "",
        content: str = "",
        command: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        if action == "create_app":
            meta = codespace_manager.create_codespace(
                user_id="default_user",
                name=name,
                template=template,
                description=f"Created autonomously by ShivAI: {name}",
            )
            return {
                "success": True,
                "codespace_id": meta.codespace_id,
                "name": meta.name,
                "preview_url": f"/v2/codespaces/{meta.codespace_id}/preview",
                "download_url": f"/v2/codespaces/{meta.codespace_id}/download",
                "message": f"Web application '{meta.name}' created! Live preview available at /v2/codespaces/{meta.codespace_id}/preview",
            }
        elif action == "write_file":
            if not codespace_id or not file_path:
                return {"success": False, "error": "codespace_id and file_path are required."}
            codespace_manager.write_file(codespace_id, file_path, content)
            return {"success": True, "message": f"Saved {file_path} in {codespace_id}."}
        elif action == "read_file":
            if not codespace_id or not file_path:
                return {"success": False, "error": "codespace_id and file_path are required."}
            text = codespace_manager.read_file(codespace_id, file_path)
            return {"success": True, "content": text}
        elif action == "execute_command":
            if not codespace_id or not command:
                return {"success": False, "error": "codespace_id and command are required."}
            res = await codespace_manager.execute_command(codespace_id, command)
            return res.model_dump()
        else:
            all_cs = codespace_manager.list_codespaces()
            return {"success": True, "codespaces": [c.model_dump() for c in all_cs]}


class ShivEditorTool(Tool):
    """Allows SHIV AI to create high-resolution images, video timelines, and voiceovers."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="shiv_editor",
                description="Creates high-resolution FLUX images, video timelines, and multimedia assets in SHIV Editor.",
                required_permission="creative",
                parameters=[
                    ToolParameter(name="action", type="string", description="'generate_image', 'create_video', or 'edit_video_file'"),
                    ToolParameter(name="prompt", type="string", description="Visual prompt describing the image or scene", required=False),
                    ToolParameter(name="title", type="string", description="Title of the video project", required=False),
                    ToolParameter(name="aspect_ratio", type="string", description="'16:9', '9:16', or '1:1'", required=False),
                    ToolParameter(name="input_path", type="string", description="Path to input video file for editing", required=False),
                    ToolParameter(name="output_path", type="string", description="Path for edited output video", required=False),
                    ToolParameter(name="voiceover_text", type="string", description="Voiceover text to synthesize and add", required=False),
                    ToolParameter(name="remove_background", type="boolean", description="Whether to remove/replace background", required=False),
                ],
            )
        )

    async def run(
        self,
        action: str = "generate_image",
        prompt: str = "Cinematic digital art",
        title: str = "Video Project",
        aspect_ratio: str = "16:9",
        **kwargs,
    ) -> Dict[str, Any]:
        if action == "edit_video_file":
            input_path = kwargs.get("input_path") or kwargs.get("video_path")
            if not input_path:
                return {"success": False, "error": "input_path is required for edit_video_file"}
            output_path = kwargs.get("output_path") or input_path.replace(".mp4", "_edited.mp4")
            remove_bg = kwargs.get("remove_background", True)
            voiceover = kwargs.get("voiceover_text") or "Time waits for nothing."
            text_overlay = kwargs.get("text_overlay") or "TIME WAITS FOR NOTHING"
            return await video_editor.render_binary_video(
                input_video_path=input_path,
                output_video_path=output_path,
                remove_background=remove_bg,
                voiceover_text=voiceover,
                text_overlay=text_overlay,
            )

        import urllib.parse
        encoded = urllib.parse.quote(prompt.strip())
        dim_map = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024)}
        w, h = dim_map.get(aspect_ratio, (1024, 1024))

        if action == "generate_image":
            image_url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&model=flux&nologo=true"
            return {
                "success": True,
                "media_type": "image/jpeg",
                "image_url": image_url,
                "prompt": prompt,
                "dimensions": f"{w}x{h}",
                "message": f"Generated image for prompt: '{prompt}'",
            }
        else:
            # Video timeline
            proj = video_editor.create_timeline(name=title, aspect_ratio=aspect_ratio)
            video_editor.add_clip(
                proj.project_id,
                source_url=f"https://image.pollinations.ai/prompt/{encoded}?model=flux-video&duration=4",
                name="AI Clip 1",
                start_time=0.0,
                end_time=4.0,
            )
            video_editor.add_text_overlay(
                proj.project_id,
                text=title,
                start_time=0.5,
                end_time=3.5,
            )
            manifest = video_editor.render_manifest(proj.project_id)
            return {
                "success": True,
                "project_id": proj.project_id,
                "title": title,
                "manifest": manifest,
                "message": f"Created video timeline project '{title}' ({proj.project_id}).",
            }


class Shiv3DTool(Tool):
    """Allows SHIV AI to create procedural 3D models, PBR materials, and interactive Three.js viewports."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="shiv_3d",
                description="Generates procedural 3D assets, meshes, materials, and Three.js 3D previews in SHIV 3D Studio.",
                required_permission="creative",
                parameters=[
                    ToolParameter(name="name", type="string", description="Name of the 3D model/asset"),
                    ToolParameter(name="mesh_type", type="string", description="'cube', 'sphere', or 'cylinder'"),
                    ToolParameter(name="color", type="string", description="Hex color code (e.g. #38BDF8)", required=False),
                    ToolParameter(name="metallic", type="number", description="Metallic 0.0 to 1.0", required=False),
                    ToolParameter(name="roughness", type="number", description="Roughness 0.0 to 1.0", required=False),
                    ToolParameter(name="wireframe", type="boolean", description="Wireframe mode", required=False),
                ],
            )
        )

    async def run(
        self,
        name: str = "Sculpture",
        mesh_type: str = "cube",
        color: str = "#38BDF8",
        metallic: float = 0.2,
        roughness: float = 0.5,
        wireframe: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        asset = threed_studio.generate_asset(
            name=name,
            mesh_type=mesh_type,
            color_hex=color,
            metallic=float(metallic),
            roughness=float(roughness),
            wireframe=bool(wireframe),
        )
        return {
            "success": True,
            "asset_id": asset["asset_id"],
            "name": asset["name"],
            "mesh_type": asset["mesh_type"],
            "preview_url": f"/v2/studios/threed/{asset['asset_id']}/preview",
            "glb_url": f"/v2/studios/threed/{asset['asset_id']}/glb",
            "triangles": asset["triangle_count"],
            "message": f"Created 3D model '{name}'. Interactive 3D preview: /v2/studios/threed/{asset['asset_id']}/preview",
        }
