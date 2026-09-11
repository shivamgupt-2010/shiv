"""
Tool permission enforcement layer.
Prevents unauthenticated or unauthorized tool invocation.
"""
from typing import Set, Dict, Any
import logging

logger = logging.getLogger("shivai.tools.permissions")


class ToolPermissionError(Exception):
    pass


class ToolPermissionGate:
    """Enforces fine-grained permission boundaries for tool executions."""

    def __init__(self, granted_permissions: Set[str] = None):
        self.granted_permissions = granted_permissions or {
            "default",
            "calculator",
            "datetime",
            "memory_read",
        }

    def can_execute(self, required_permission: str) -> bool:
        if "admin" in self.granted_permissions:
            return True
        return required_permission in self.granted_permissions

    def verify_permission(self, tool_name: str, required_permission: str) -> None:
        if not self.can_execute(required_permission):
            logger.warning(
                f"Permission denied executing tool '{tool_name}'. Required: '{required_permission}'"
            )
            raise ToolPermissionError(
                f"Execution of tool '{tool_name}' requires permission '{required_permission}', which was not granted."
            )
