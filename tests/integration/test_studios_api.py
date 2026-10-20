"""
Integration Tests for ShivAI V2 Orchestration, Studios, and Background Jobs Endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app


@pytest.fixture
def auth_headers():
    return {
        "X-API-Key": "shivai-production-key-2026",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_orchestration_api_endpoints(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Classify
        res1 = await client.post(
            "/v2/orchestration/classify",
            json={"prompt": "Build a 2D neon space runner arcade game"},
            headers=auth_headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["primary_intent"] == "game_development_2d"
        assert data1["recommended_agent"] == "game_developer"

        # 2. Plan
        res2 = await client.post(
            "/v2/orchestration/plan",
            json={"goal": "Build a fullstack SaaS application with FastAPI and React"},
            headers=auth_headers,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2["steps"]) >= 4
        assert data2["steps"][0]["assigned_agent"] == "planner"


@pytest.mark.asyncio
async def test_studios_api_endpoints(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 2D Design Studio
        d_res = await client.post(
            "/v2/studios/design/create",
            json={"name": "Header Banner", "preset": "social_banner", "headline": "ShivAI V2 Launch"},
            headers=auth_headers,
        )
        assert d_res.status_code == 200
        d_data = d_res.json()
        assert "<svg" in d_data["svg"]
        assert "ShivAI V2 Launch" in d_data["svg"]

        # 2. 3D Asset Studio
        td_res = await client.post(
            "/v2/studios/threed/create",
            json={"name": "PBR Orb", "mesh_type": "sphere", "color": "#06B6D4"},
            headers=auth_headers,
        )
        assert td_res.status_code == 200
        td_data = td_res.json()
        assert td_data["vertex_count"] > 0
        assert "<!DOCTYPE html>" in td_data["html_preview"]

        # 3. Game Studio
        g_res = await client.post(
            "/v2/studios/games/create",
            json={"title": "Cyber Dodge", "game_type": "2d"},
            headers=auth_headers,
        )
        assert g_res.status_code == 200
        g_data = g_res.json()
        assert g_data["is_valid"] is True
        assert "<canvas" in g_data["html_bundle"]

        # 4. App Builder
        app_res = await client.post(
            "/v2/studios/apps/create",
            json={"app_name": "TaskPilot", "entity_name": "Task", "description": "Workflow management system"},
            headers=auth_headers,
        )
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["validation_passed"] is True
        assert "main.py" in app_data["files"]

        # 5. Software Engineer: Diagnose & Patch
        diag_res = await client.post(
            "/v2/studios/engineer/diagnose",
            json={"error_log": "TypeError: unsupported operand type(s) for +: 'int' and 'str'"},
            headers=auth_headers,
        )
        assert diag_res.status_code == 200
        assert diag_res.json()["error_type"] == "TypeError"

        patch_res = await client.post(
            "/v2/studios/engineer/patch",
            json={
                "original_code": "def greet(name):\n    return 'Hello ' + name\n",
                "target_chunk": "'Hello ' + name",
                "replacement_chunk": "f'Hello, {name}!'",
            },
            headers=auth_headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["success"] is True


@pytest.mark.asyncio
async def test_jobs_api_lifecycle(auth_headers):
    import asyncio
    from core.execution.job_queue import job_queue

    async def slow_handler(job, progress_cb):
        await asyncio.sleep(2.0)
        return {"done": True}

    job_queue.register_handler("slow_render", slow_handler)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit Job
        sub_res = await client.post(
            "/v2/jobs",
            json={"job_type": "slow_render", "payload": {"scene_id": "test_1"}, "priority": "HIGH"},
            headers=auth_headers,
        )
        assert sub_res.status_code == 202
        job_data = sub_res.json()
        job_id = job_data["job_id"]
        assert job_id.startswith("job_")

        # Get Job Details
        get_res = await client.get(f"/v2/jobs/{job_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["job_id"] == job_id

        # List Jobs
        list_res = await client.get("/v2/jobs", headers=auth_headers)
        assert list_res.status_code == 200
        assert any(j["job_id"] == job_id for j in list_res.json())

        # Cancel Job
        cancel_res = await client.post(f"/v2/jobs/{job_id}/cancel", headers=auth_headers)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

