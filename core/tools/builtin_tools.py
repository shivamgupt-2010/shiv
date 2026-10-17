"""
Built-in production tools for ShivAI.
"""
import ast
import operator
from datetime import datetime, timezone
from typing import Dict, Any
from core.tools.base import Tool, ToolDefinition, ToolParameter


class CalculatorTool(Tool):
    """Safely evaluates basic arithmetic expressions using AST parsing."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="calculator",
                description="Performs safe mathematical calculations (+, -, *, /, **, %)",
                required_permission="calculator",
                parameters=[
                    ToolParameter(
                        name="expression",
                        type="string",
                        description="Mathematical expression to evaluate, e.g. '24 * 60 * 60' or '2 ** 10'",
                    )
                ],
            )
        )
        self._operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in self._operators:
                return self._operators[op_type](left, right)
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type in self._operators:
                return self._operators[op_type](operand)
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        else:
            raise ValueError(f"Unsupported AST node type: {type(node).__name__}")

    async def run(self, expression: str = "", **kwargs) -> Dict[str, Any]:
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = self._eval_node(tree.body)
            return {"success": True, "result": result, "expression": expression}
        except Exception as e:
            return {"success": False, "error": str(e), "expression": expression}


class DateTimeTool(Tool):
    """Provides authoritative system and UTC time context."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="get_current_time",
                description="Returns current UTC timestamp, day of week, and ISO format date.",
                required_permission="datetime",
                parameters=[],
            )
        )

    async def run(self, **kwargs) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "success": True,
            "utc_iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time_utc": now.strftime("%H:%M:%S UTC"),
            "day_of_week": now.strftime("%A"),
        }


from core.research.search_engine import search_engine
from core.tools.sandbox import code_sandbox


class WebSearchTool(Tool):
    """Real-time web search lookup tool using DuckDuckGo."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="web_search",
                description="Searches public online sources for up-to-date information, facts, and documentation.",
                required_permission="web_search",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search keywords or research question",
                    )
                ],
            )
        )

    async def run(self, query: str = "", **kwargs) -> Dict[str, Any]:
        results = await search_engine.search(query, max_results=3)
        return {
            "success": True,
            "query": query,
            "results": [r.to_dict() for r in results],
            "count": len(results),
        }


class SandboxedPythonTool(Tool):
    """Executes Python code safely in a restricted subprocess with timeout limits."""

    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="sandboxed_python",
                description="Executes a Python script safely in an isolated ephemeral sandbox and captures output.",
                required_permission="code_execution",
                parameters=[
                    ToolParameter(
                        name="code",
                        type="string",
                        description="Python code to execute",
                    )
                ],
            )
        )

    async def run(self, code: str = "", **kwargs) -> Dict[str, Any]:
        res = await code_sandbox.execute_python(code=code)
        return {
            "success": res.success,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.exit_code,
            "timed_out": res.timed_out,
            "execution_time_ms": res.execution_time_ms,
        }
