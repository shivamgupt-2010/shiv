"""
Unit tests for Tool System and AST Calculator security.
"""
import pytest
from core.tools.builtin_tools import CalculatorTool, DateTimeTool
from core.tools.permissions import ToolPermissionGate, ToolPermissionError


@pytest.mark.asyncio
async def test_calculator_basic_operations():
    calc = CalculatorTool()
    res = await calc.run("2 + 2 * 10")
    assert res["success"] is True
    assert res["result"] == 22

    res_pow = await calc.run("2 ** 8")
    assert res_pow["success"] is True
    assert res_pow["result"] == 256


@pytest.mark.asyncio
async def test_calculator_security_boundary():
    calc = CalculatorTool()
    # Attempting to call malicious code via calculator must fail safely
    res = await calc.run("__import__('os').system('dir')")
    assert res["success"] is False
    assert "error" in res


@pytest.mark.asyncio
async def test_datetime_tool():
    dt_tool = DateTimeTool()
    res = await dt_tool.run()
    assert res["success"] is True
    assert "utc_iso" in res
    assert "day_of_week" in res


def test_permission_gate():
    gate = ToolPermissionGate(granted_permissions={"calculator"})
    assert gate.can_execute("calculator") is True
    assert gate.can_execute("admin") is False

    with pytest.raises(ToolPermissionError):
        gate.verify_permission("admin_tool", "admin")
