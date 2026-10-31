"""
ShivAI Dynamic Custom Agent Manager.
Allows users and SHIV AI to create, edit, list, and delete custom specialized AI agents.
Persists custom agents to disk and registers them into the active runtime.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.agents.base import BaseAgent, AgentDefinition
from core.agents.agent_manager import agent_manager

logger = logging.getLogger("shivai.agents.custom")


class CustomAgentModel(BaseModel):
    agent_id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str
    key: str
    purpose: str
    instructions: str
    required_capabilities: Dict[str, bool] = Field(default_factory=lambda: {"reasoning": True})
    allowed_tools: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    preferred_provider: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class CustomAgentManager:
    """Manages creation, storage, and runtime registration of user/AI created agents."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            root = Path(__file__).resolve().parent.parent.parent
            self.storage_dir = root / "storage" / "agents"
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._custom_agents: Dict[str, CustomAgentModel] = {}
        self._load_persisted_agents()

    def _get_agent_path(self, agent_id: str) -> Path:
        return self.storage_dir / f"{agent_id}.json"

    def _load_persisted_agents(self) -> None:
        """Loads all custom agents from disk into memory and registers them in agent_manager."""
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    agent_model = CustomAgentModel(**data)
                    self._custom_agents[agent_model.agent_id] = agent_model
                    self._register_in_runtime(agent_model)
            except Exception as e:
                logger.error(f"Failed to load custom agent from {file}: {e}")

    def _register_in_runtime(self, model: CustomAgentModel) -> None:
        """Mounts agent into the active ShivAI AgentManager."""
        definition = AgentDefinition(
            name=model.name,
            purpose=model.purpose,
            instructions=model.instructions,
            required_capabilities=model.required_capabilities,
            allowed_tools=model.allowed_tools,
            permissions=model.permissions,
            preferred_provider=model.preferred_provider,
        )
        base_agent = BaseAgent(definition)
        agent_manager.register(model.key, base_agent)
        logger.info(f"Registered custom agent '{model.name}' under key '{model.key}'")

    def create_agent(
        self,
        name: str,
        purpose: str,
        instructions: str,
        key: Optional[str] = None,
        required_capabilities: Optional[Dict[str, bool]] = None,
        allowed_tools: Optional[List[str]] = None,
        preferred_provider: Optional[str] = None,
    ) -> CustomAgentModel:
        """Creates and immediately activates a new specialized agent."""
        agent_key = (key or name.lower().replace(" ", "_")).strip()
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"

        model = CustomAgentModel(
            agent_id=agent_id,
            name=name,
            key=agent_key,
            purpose=purpose,
            instructions=instructions,
            required_capabilities=required_capabilities or {"reasoning": True},
            allowed_tools=allowed_tools or [],
            preferred_provider=preferred_provider,
        )

        # Save to disk
        file_path = self._get_agent_path(agent_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(model.model_dump(), f, indent=2)

        self._custom_agents[agent_id] = model
        self._register_in_runtime(model)
        return model

    def get_agent(self, agent_id_or_key: str) -> Optional[CustomAgentModel]:
        """Retrieves a custom agent by agent_id or key."""
        if agent_id_or_key in self._custom_agents:
            return self._custom_agents[agent_id_or_key]
        for a in self._custom_agents.values():
            if a.key == agent_id_or_key.lower():
                return a
        return None

    def list_agents(self) -> List[CustomAgentModel]:
        """Returns all custom agents."""
        return list(self._custom_agents.values())

    def update_agent(
        self,
        agent_id: str,
        name: Optional[str] = None,
        purpose: Optional[str] = None,
        instructions: Optional[str] = None,
        required_capabilities: Optional[Dict[str, bool]] = None,
        allowed_tools: Optional[List[str]] = None,
        preferred_provider: Optional[str] = None,
    ) -> Optional[CustomAgentModel]:
        """Updates an existing agent and synchronizes runtime."""
        model = self.get_agent(agent_id)
        if not model:
            return None

        if name is not None:
            model.name = name
        if purpose is not None:
            model.purpose = purpose
        if instructions is not None:
            model.instructions = instructions
        if required_capabilities is not None:
            model.required_capabilities = required_capabilities
        if allowed_tools is not None:
            model.allowed_tools = allowed_tools
        if preferred_provider is not None:
            model.preferred_provider = preferred_provider

        model.updated_at = time.time()

        file_path = self._get_agent_path(model.agent_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(model.model_dump(), f, indent=2)

        self._custom_agents[model.agent_id] = model
        self._register_in_runtime(model)
        return model

    def delete_agent(self, agent_id: str) -> bool:
        """Deletes an agent from disk and unregisters from active registry."""
        model = self.get_agent(agent_id)
        if not model:
            return False

        file_path = self._get_agent_path(model.agent_id)
        if file_path.exists():
            file_path.unlink()

        if model.agent_id in self._custom_agents:
            del self._custom_agents[model.agent_id]

        # Re-initialize defaults in agent_manager if needed
        if model.key in agent_manager._agents:
            del agent_manager._agents[model.key]

        logger.info(f"Deleted custom agent '{model.name}' ({model.agent_id})")
        return True


# Global custom agent manager instance
custom_agent_manager = CustomAgentManager()
