"""
Integration tests for SHIV AI Device Operator & Digital Work Automation API Routers
Covers /v2/devices and /v2/automation endpoints end-to-end.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.fixture
def auth_headers():
    return {
        "X-API-Key": "shivai-production-key-2026",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_devices_api_endpoints(auth_headers):
    """Tests device pairing, observation, action dispatch, approval, and emergency stop."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Emergency stop status & reset
        res_es = await client.get("/v2/devices/emergency-stop/status", headers=auth_headers)
        assert res_es.status_code == 200

        await client.post("/v2/devices/emergency-stop/reset", headers=auth_headers)

        # 2. List devices
        res_devs = await client.get("/v2/devices", headers=auth_headers)
        assert res_devs.status_code == 200
        devs = res_devs.json()
        assert len(devs) >= 1
        host_id = devs[0]["device_id"]

        # 3. Request pairing code
        res_pair = await client.post(
            "/v2/devices/pair/request",
            json={"name": "Integration Test Tablet", "device_type": "android"},
            headers=auth_headers,
        )
        assert res_pair.status_code == 200
        pair_code = res_pair.json()["pairing_code"]

        # 4. Complete pairing
        res_comp = await client.post(
            "/v2/devices/pair/complete",
            json={"pairing_code": pair_code},
            headers=auth_headers,
        )
        assert res_comp.status_code == 200
        new_dev_id = res_comp.json()["device_id"]
        assert new_dev_id.startswith("dev-")

        # 5. Observe host device
        res_obs = await client.post(f"/v2/devices/{host_id}/observe", headers=auth_headers)
        assert res_obs.status_code == 200
        obs = res_obs.json()
        assert "active_window_title" in obs

        # 6. Dispatch Category A Action (auto-approved)
        res_act_a = await client.post(
            f"/v2/devices/{host_id}/action",
            json={"action_type": "observe_state", "target_app": "system"},
            headers=auth_headers,
        )
        assert res_act_a.status_code == 200
        assert res_act_a.json()["status"] == "completed"

        # 7. Dispatch Category B Action (requires approval)
        res_act_b = await client.post(
            f"/v2/devices/{host_id}/action",
            json={
                "action_type": "send_email",
                "target_app": "Outlook",
                "params": {"recipient": "boss@company.com", "subject": "Update"},
            },
            headers=auth_headers,
        )
        assert res_act_b.status_code == 200
        act_b_data = res_act_b.json()
        assert act_b_data["status"] == "pending_approval"
        appr_ticket = act_b_data["approval_ticket"]
        assert appr_ticket is not None
        appr_id = appr_ticket["approval_id"]

        # 8. List pending approvals
        res_apprs = await client.get("/v2/devices/approvals/pending", headers=auth_headers)
        assert res_apprs.status_code == 200
        assert any(a["approval_id"] == appr_id for a in res_apprs.json())

        # 9. Decide approval (approve)
        res_decide = await client.post(
            f"/v2/devices/approvals/{appr_id}/decide",
            json={"approved": True, "notes": "Approved by test suite"},
            headers=auth_headers,
        )
        assert res_decide.status_code == 200
        assert res_decide.json()["status"] == "approved"

        # 10. Emergency stop trigger & verify
        res_stop = await client.post(
            "/v2/devices/emergency-stop/trigger",
            json={"reason": "Test emergency halt"},
            headers=auth_headers,
        )
        assert res_stop.status_code == 200
        assert res_stop.json()["is_active"] is True

        # Reset emergency stop
        await client.post("/v2/devices/emergency-stop/reset", headers=auth_headers)


@pytest.mark.asyncio
async def test_automation_api_endpoints(auth_headers):
    """Tests digital work automation endpoints for social media, email, forms, and schedules."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Social calendar
        res_cal = await client.post(
            "/v2/automation/social/calendar",
            json={"goal": "AI Device Operator Launch", "days": 5},
            headers=auth_headers,
        )
        assert res_cal.status_code == 200
        assert len(res_cal.json()) >= 10

        # 2. Social draft
        res_draft = await client.post(
            "/v2/automation/social/draft",
            json={"platform": "linkedin", "topic": "Autonomous Digital Work"},
            headers=auth_headers,
        )
        assert res_draft.status_code == 200
        assert res_draft.json()["platform"] == "linkedin"
        assert res_draft.json()["status"] == "draft"

        # 3. Email thread summarize
        res_sum = await client.post(
            "/v2/automation/email/summarize",
            json={
                "messages": [
                    {"sender": "client@acme.com", "body": "Please provide status by Friday."},
                    {"sender": "lead@acme.com", "body": "Action: review documentation."},
                ]
            },
            headers=auth_headers,
        )
        assert res_sum.status_code == 200
        assert "thread_summary" in res_sum.json()

        # 4. Form extract
        res_form = await client.post(
            "/v2/automation/forms/extract",
            json={"document_text": "Name: Alice Wonder\nEmail: alice@wonderland.org\nPhone: (555) 123-4567"},
            headers=auth_headers,
        )
        assert res_form.status_code == 200
        fields = res_form.json()["extracted_fields"]
        assert fields.get("full_name") == "Alice Wonder"
        assert fields.get("email") == "alice@wonderland.org"

        # 5. Creative execution (Premiere FCPXML)
        res_creative = await client.post(
            "/v2/automation/creative/execute",
            json={
                "operation": "premiere_xml",
                "params": {"project_name": "TestEdit", "clips": [{"name": "C1", "duration": 4.0}]},
            },
            headers=auth_headers,
        )
        assert res_creative.status_code == 200
        assert res_creative.json()["success"] is True

        # 6. Schedules list & trigger
        res_scheds = await client.get("/v2/automation/schedules", headers=auth_headers)
        assert res_scheds.status_code == 200
        scheds = res_scheds.json()
        assert len(scheds) >= 1
        wf_id = scheds[0]["workflow_id"]

        res_trig = await client.post(f"/v2/automation/schedules/{wf_id}/trigger", headers=auth_headers)
        assert res_trig.status_code == 200
        assert res_trig.json()["workflow_id"] == wf_id
