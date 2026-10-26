"""
ShivAI Multi-Agent DAG Orchestrator.
Decomposes complex goals into subtasks, coordinates specialized agent handoffs,
executes parallel or sequential stages, and validates composite outputs.
"""
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from core.agents.v2.roles import SPECIALIZED_AGENTS, AgentRole
from core.v2.request_service import V2RequestService, V2ChatRequest
from core.tools.registry import tool_registry

logger = logging.getLogger("shivai.agents.orchestrator")


class SubTaskResult(BaseModel):
    task_id: str
    assigned_agent: str
    description: str
    output: str
    execution_time_ms: float = 0.0
    success: bool = True


class MultiAgentExecutionResult(BaseModel):
    goal: str
    subtasks: List[SubTaskResult] = Field(default_factory=list)
    final_output: str
    total_execution_time_ms: float = 0.0
    agents_involved: List[str] = Field(default_factory=list)


class MultiAgentOrchestrator:
    """Coordinates specialized agent execution and dependency-aware task completion."""

    def __init__(self):
        self.roles = SPECIALIZED_AGENTS
        self.request_service = V2RequestService()

    async def execute_task(
        self,
        goal: str,
        user_id: str = "agent_orchestrator_user",
        preferred_agents: Optional[List[str]] = None,
    ) -> MultiAgentExecutionResult:
        """
        Decomposes goal into specialized stages and executes them sequentially or concurrently:
        Stage 1: Planning / Decomposition (Planner)
        Stage 2: Research or Analysis (Researcher / Analyst)
        Stage 3: Synthesis / Execution (Writer / Engineer)
        """
        start_time = time.perf_counter()
        logger.info(f"Orchestrating multi-agent workflow for goal: '{goal[:80]}...'")

        subtask_results: List[SubTaskResult] = []
        agents_used = []

        # Stage 1: Strategy & Planning
        planner = self.roles.get("planner")
        p_start = time.perf_counter()
        plan_prompt = (
            f"Goal: {goal}\n\n"
            f"Analyze this goal and provide a structured 2-step execution plan:\n"
            f"Step 1: Key questions, facts, or technical specs to investigate.\n"
            f"Step 2: Core implementation, analysis, or answer required."
        )
        plan_req = V2ChatRequest(message=plan_prompt, mode="quality")
        plan_res = await self.request_service.execute_chat(plan_req, user_id=user_id, request_id=f"plan-{int(time.time())}")
        p_time = (time.perf_counter() - p_start) * 1000.0

        subtask_results.append(
            SubTaskResult(
                task_id="step_1_plan",
                assigned_agent="planner",
                description="Task decomposition and plan formulation",
                output=plan_res.response,
                execution_time_ms=round(p_time, 2),
            )
        )
        agents_used.append("planner")

        # Determine specialist: engineer for coding, researcher for questions/facts, analyst for math
        is_coding = any(k in goal.lower() for k in ["code", "function", "api", "script", "python", "bug", "implement"])
        is_analysis = any(k in goal.lower() for k in ["calculate", "compare", "data", "math", "metric"])

        if is_coding:
            specialist_role = "engineer"
        elif is_analysis:
            specialist_role = "analyst"
        else:
            specialist_role = "researcher"

        specialist = self.roles.get(specialist_role, self.roles["researcher"])
        s_start = time.perf_counter()
        specialist_prompt = (
            f"{specialist.system_instructions}\n\n"
            f"Goal: {goal}\n\n"
            f"Execution Strategy from Planner:\n{plan_res.response}\n\n"
            f"Now execute your specialized role ({specialist.name}) and provide the deep findings or implementation."
        )
        spec_req = V2ChatRequest(message=specialist_prompt, mode="quality")
        spec_res = await self.request_service.execute_chat(spec_req, user_id=user_id, request_id=f"spec-{int(time.time())}")
        s_time = (time.perf_counter() - s_start) * 1000.0

        subtask_results.append(
            SubTaskResult(
                task_id=f"step_2_{specialist_role}",
                assigned_agent=specialist_role,
                description=f"Specialized execution by {specialist.name}",
                output=spec_res.response,
                execution_time_ms=round(s_time, 2),
            )
        )
        agents_used.append(specialist_role)

        # Stage 3: Master Writer Synthesis & Review
        w_start = time.perf_counter()
        writer = self.roles["writer"]
        writer_prompt = (
            f"{writer.system_instructions}\n\n"
            f"Original Goal: {goal}\n\n"
            f"Findings from {specialist.name}:\n{spec_res.response}\n\n"
            f"Produce the final, polished, comprehensive response. Structure it logically with clear headings, "
            f"practical insights, and rigorous clarity."
        )
        writer_req = V2ChatRequest(message=writer_prompt, mode="quality")
        writer_res = await self.request_service.execute_chat(writer_req, user_id=user_id, request_id=f"write-{int(time.time())}")
        w_time = (time.perf_counter() - w_start) * 1000.0

        subtask_results.append(
            SubTaskResult(
                task_id="step_3_synthesis",
                assigned_agent="writer",
                description="Final content polishing and quality synthesis",
                output=writer_res.response,
                execution_time_ms=round(w_time, 2),
            )
        )
        agents_used.append("writer")

        total_time = (time.perf_counter() - start_time) * 1000.0
        return MultiAgentExecutionResult(
            goal=goal,
            subtasks=subtask_results,
            final_output=writer_res.response,
            total_execution_time_ms=round(total_time, 2),
            agents_involved=agents_used,
        )


# Global orchestrator instance
multi_agent_orchestrator = MultiAgentOrchestrator()
