"""
Tool Registry and Execution Manager.
"""
from typing import Dict, List, Optional, Any
from core.tools.base import Tool, ToolDefinition
from core.tools.permissions import ToolPermissionGate, ToolPermissionError
from core.tools.builtin_tools import CalculatorTool, DateTimeTool, WebSearchTool


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(CalculatorTool())
        self.register(DateTimeTool())
        self.register(WebSearchTool())

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_definitions(self, allowed_permissions: Optional[set] = None) -> List[ToolDefinition]:
        if allowed_permissions is None:
            return [t.definition for t in self._tools.values()]
        return [t.definition for t in self._tools.values() if t.required_permission in allowed_permissions]

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        permission_gate: Optional[ToolPermissionGate] = None,
    ) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found."}

        gate = permission_gate or ToolPermissionGate()
        try:
            gate.verify_permission(tool.name, tool.required_permission)
        except ToolPermissionError as e:
            return {"success": False, "error": str(e)}

        return await tool.run(**arguments)


tool_registry = ToolRegistry()
