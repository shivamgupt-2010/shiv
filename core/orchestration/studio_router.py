"""
SHIV AI Autonomous Studio Router.
Detects user creation intents across:
1. Dynamic Agents (create/delete custom agents)
2. Dynamic Workflows (create/run DAG workflows)
3. SHIV Codespaces (create websites, web apps, write code, run terminal commands)
4. SHIV Editor (generate images, create video timelines)
5. SHIV 3D Studio (create 3D models, render Three.js previews, export GLB)

Executes studio actions by default so un-updated clients (such as the SHIV Android Launcher)
can immediately access and control all studios without client-side modifications.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from core.agents.custom_agent_manager import custom_agent_manager
from core.automation.workflow_engine import workflow_engine
from core.codespaces.manager import codespace_manager
from core.threed.scene import threed_studio
from core.video.editor import video_editor


class StudioIntentRouter:
    """Interprets creation prompts and deterministically triggers studio operations."""

    @classmethod
    def match_and_execute(cls, prompt: str, user_id: str = "default_user") -> Optional[str]:
        """
        Attempts to match a studio creation command.
        If matched, executes the studio engine and returns a rich Markdown response.
        If not matched, returns None to allow regular LLM reasoning.
        """
        text = prompt.strip()
        lower = text.lower()

        # ----------------------------------------------------------------------
        # 1. 3D Model Creation Intent
        # ----------------------------------------------------------------------
        if ("3d" in lower or "three.js" in lower or "mesh" in lower or "glb" in lower) and any(
            verb in lower for verb in ["create", "make", "generate", "build", "render", "model", "design"]
        ):
            mesh_type = "cube"
            if "sphere" in lower or "ball" in lower or "planet" in lower:
                mesh_type = "sphere"
            elif "cylinder" in lower or "column" in lower or "tube" in lower or "rocket" in lower:
                mesh_type = "cylinder"

            color = "#38BDF8"  # Shiv blue
            if "gold" in lower or "yellow" in lower:
                color = "#EAB308"
            elif "red" in lower:
                color = "#EF4444"
            elif "green" in lower:
                color = "#10B981"
            elif "purple" in lower:
                color = "#A855F7"
            elif "neon" in lower or "cyan" in lower:
                color = "#06B6D4"

            name_match = re.search(r"(?:3d model|3d asset|3d scene|3d)\s+(?:of\s+)?(?:a\s+|an\s+)?([a-zA-Z0-9_\-\s]{2,30})", text, re.IGNORECASE)
            name = name_match.group(1).strip().title() if name_match else "Custom 3D Sculpture"

            asset = threed_studio.generate_asset(
                name=name,
                mesh_type=mesh_type,
                color_hex=color,
                metallic=0.4,
                roughness=0.3,
            )
            asset_id = asset["asset_id"]

            return (
                f"### 🧊 SHIV 3D Studio — Asset Created\n\n"
                f"I have created the 3D model **{name}** in the SHIV 3D Editor.\n\n"
                f"- **Asset ID**: `{asset_id}`\n"
                f"- **Geometry**: `{mesh_type.upper()}` ({asset['triangle_count']} triangles, {asset['vertex_count']} vertices)\n"
                f"- **PBR Material**: Color `{color}`, Metallic `0.4`, Roughness `0.3`\n\n"
                f"**Explore & Preview in 3D Viewport:**\n"
                f"🔗 [Open Interactive 3D Viewport](/v2/studios/threed/{asset_id}/preview)\n\n"
                f"**Download Production Model:**\n"
                f"📥 [Download GLB Binary](/v2/studios/threed/{asset_id}/glb)"
            )

        # ----------------------------------------------------------------------
        # 2. Codespaces & Web Application Creation Intent
        # ----------------------------------------------------------------------
        if any(kw in lower for kw in ["codespace", "website", "web app", "web application", "landing page", "frontend"]) and any(
            verb in lower for verb in ["create", "build", "make", "generate", "code", "scaffold", "develop"]
        ):
            name_match = re.search(r"(?:app|website|page|codespace)\s+(?:named|called|for)?\s*(?:a\s+|an\s+)?([a-zA-Z0-9_\-\s]{2,30})", text, re.IGNORECASE)
            app_name = name_match.group(1).strip().title() if name_match else "ShivWebApp"

            meta = codespace_manager.create_codespace(
                user_id=user_id,
                name=app_name,
                template="html5_app",
                description=f"Autonomously scaffolded by ShivAI: {text}",
            )
            cs_id = meta.codespace_id

            return (
                f"### 💻 SHIV Codespaces — Application Created\n\n"
                f"I have created a new web application codespace for **{app_name}**.\n\n"
                f"- **Codespace ID**: `{cs_id}`\n"
                f"- **Template**: `HTML5 + Tailwind CSS + Responsive UI`\n"
                f"- **Files Initialized**: `index.html`, `app.js`, `README.md`\n\n"
                f"**Live Interactive Preview:**\n"
                f"🌐 [Launch Live Web App Preview](/v2/codespaces/{cs_id}/preview)\n\n"
                f"**Download & Edit:**\n"
                f"📦 [Download ZIP Project Bundle](/v2/codespaces/{cs_id}/download)\n"
                f"You can instruct me to edit files, add features, or run terminal commands in this codespace anytime!"
            )

        # ----------------------------------------------------------------------
        # 3. Dynamic Agent Creation Intent
        # ----------------------------------------------------------------------
        if ("agent" in lower or "persona" in lower or "specialist" in lower) and any(
            verb in lower for verb in ["create", "build", "register", "make", "configure", "forge"]
        ):
            name_match = re.search(r"agent\s+(?:named|called)\s+([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
            agent_name = name_match.group(1).strip() if name_match else "CustomSpecialist"
            agent_key = agent_name.lower().replace(" ", "_")

            instructions = f"You are {agent_name}, a specialized AI agent configured in ShivAI. Follow user requests with expert accuracy."
            if "for" in lower or "with instructions" in lower:
                instructions = text

            agent = custom_agent_manager.create_agent(
                name=agent_name,
                key=agent_key,
                purpose=f"Specialized AI agent: {agent_name}",
                instructions=instructions,
            )

            return (
                f"### 🤖 SHIV Agent Forge — New Agent Activated\n\n"
                f"I have created and registered the custom agent **{agent.name}** into the active SHIV AI runtime!\n\n"
                f"- **Agent ID**: `{agent.agent_id}`\n"
                f"- **Key**: `{agent.key}`\n"
                f"- **Purpose**: {agent.purpose}\n"
                f"- **Status**: `ACTIVE` (Available immediately across chat and multi-agent workflows)\n\n"
                f"You can invoke this specialist anytime by setting `agent=\"{agent.key}\"` or asking me to delegate tasks to {agent.name}."
            )

        # ----------------------------------------------------------------------
        # 4. Multi-Step Workflow Creation Intent
        # ----------------------------------------------------------------------
        if ("workflow" in lower or "pipeline" in lower) and any(
            verb in lower for verb in ["create", "build", "schedule", "make", "author", "setup"]
        ):
            name_match = re.search(r"workflow\s+(?:named|called|for)?\s*([a-zA-Z0-9_\-\s]{2,40})", text, re.IGNORECASE)
            wf_name = name_match.group(1).strip().title() if name_match else "Automated Workflow"

            steps = [
                {
                    "step_id": "step_1",
                    "name": "Analyze Objective",
                    "step_type": "ai_prompt",
                    "params": {"prompt": f"Analyze requirements for: {text}"},
                },
                {
                    "step_id": "step_2",
                    "name": "Execute Action",
                    "step_type": "ai_prompt",
                    "params": {"prompt": "Execute primary deliverable based on {step_1.output}"},
                    "depends_on": ["step_1"],
                },
            ]

            wf = workflow_engine.create_workflow(
                name=wf_name,
                steps=steps,
                description=f"Multi-step automated routine created from: {text}",
            )

            return (
                f"### ⚙️ SHIV Workflow Forge — Workflow Created\n\n"
                f"I have authored and registered the multi-step DAG workflow **{wf.name}**.\n\n"
                f"- **Workflow ID**: `{wf.workflow_id}`\n"
                f"- **Step Count**: {len(wf.steps)} steps with dependency graph\n"
                f"- **Trigger Status**: `READY`\n\n"
                f"To run this workflow now, simply say *'Execute workflow {wf.workflow_id}'*."
            )

        # ----------------------------------------------------------------------
        # 5. Image / Video Generation (SHIV Editor)
        # ----------------------------------------------------------------------
        if ("image" in lower or "picture" in lower or "photo" in lower or "wallpaper" in lower) and any(
            verb in lower for verb in ["create", "generate", "make", "draw", "render", "paint"]
        ):
            # Clean prompt
            clean_prompt = re.sub(r"^(?:create|generate|make|draw|render|paint)\s+(?:an?\s+)?(?:image|picture|photo|wallpaper)\s+(?:of\s+)?", "", text, flags=re.IGNORECASE).strip()
            if not clean_prompt:
                clean_prompt = "Futuristic cybernetic city"

            encoded = urllib.parse.quote(clean_prompt)
            image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true"

            return (
                f"### 🎬 SHIV Editor — Image Generated\n\n"
                f"Here is your high-resolution image generated with **FLUX.1**:\n\n"
                f"![{clean_prompt}]({image_url})\n\n"
                f"- **Prompt**: *{clean_prompt}*\n"
                f"- **Resolution**: `1024x1024` (Zero-RAM Serverless FLUX)\n"
                f"- **Direct High-Res Link**: [View Original Image]({image_url})"
            )

        if ("video" in lower or "animation" in lower or "clip" in lower) and any(
            verb in lower for verb in ["create", "generate", "make", "produce", "render"]
        ):
            clean_prompt = re.sub(r"^(?:create|generate|make|produce|render)\s+(?:an?\s+)?(?:video|animation|clip)\s+(?:of\s+|about\s+)?", "", text, flags=re.IGNORECASE).strip()
            if not clean_prompt:
                clean_prompt = "Deep space galaxy voyage"

            encoded = urllib.parse.quote(clean_prompt)
            video_url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux-video&duration=4"

            proj = video_editor.create_timeline(name=clean_prompt[:30])
            video_editor.add_clip(
                proj.project_id,
                source_url=video_url,
                name="AI Render Track",
                start_time=0.0,
                end_time=4.0,
            )

            return (
                f"### 🎬 SHIV Editor — Video Created\n\n"
                f"I have initialized and rendered your video project in the SHIV Editor:\n\n"
                f"- **Project ID**: `{proj.project_id}`\n"
                f"- **Prompt**: *{clean_prompt}*\n"
                f"- **Duration**: `4.0s` | **Format**: `16:9 MP4`\n\n"
                f"🎥 **Stream Render:** [Watch Generated Video]({video_url})"
            )

        return None
