#!/usr/bin/env python3
"""
Comprehensive Verification Test for SHIV Database & Auth Platform
Using credentials:
  Project ID: 7d810bd0-f625-4856-a154-4e04aca955fc
  API Key:    shiv_sk_7VpCyHo_X0_Q74V2oX3UJgCQ28DASaccElh5NbJ8amU
"""

import asyncio
import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.shiv_db_service import shiv_db_service
from config.settings import settings


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f" {title}")
    print("=" * 65)


async def main():
    print_header("SHIV DATABASE & AUTH INTEGRATION AUDIT")
    print(f"Target DB URL:    {settings.SHIV_DB_URL}")
    print(f"Project ID:       {settings.SHIV_DB_PROJECT_ID}")
    print(f"API Key:          {settings.SHIV_DB_API_KEY[:10]}...{settings.SHIV_DB_API_KEY[-8:]}")

    # 1. Health Check
    print_header("Test 1: Health & System Diagnostics")
    health = await shiv_db_service.check_health()
    print(f"Health Response: {health}")
    assert health.get("status") == "ok", f"Health check failed: {health}"
    print("[PASS] Health endpoint active and responsive.")

    # 2. Database Record Creation
    print_header("Test 2: Database Record Creation (POST /data/{collection})")
    test_collection = "devices_registry"
    now_ts = time.time()
    sample_record = {
        "device_id": f"dev_{int(now_ts)}",
        "device_name": "ShivOS Launcher Mobile",
        "os_version": "Android 14 / SHIV-OS 2.0",
        "registered_at": now_ts,
    }
    created = await shiv_db_service.create_record(
        collection=test_collection,
        data=sample_record,
        user_id="user_shivam_admin"
    )
    print(f"Created Record: {created}")
    assert created and "id" in created, "Failed to create record in SHIV DB"
    record_id = created["id"]
    print(f"[PASS] Successfully created record ID: {record_id}")

    # 3. Database Record Retrieval by ID
    print_header("Test 3: Database Record Retrieval by ID (GET /data/{col}/{id})")
    retrieved = await shiv_db_service.get_record(collection=test_collection, record_id=record_id)
    print(f"Retrieved Record: {retrieved}")
    assert retrieved and retrieved.get("id") == record_id, "Failed to retrieve record by ID"
    print(f"[PASS] Successfully verified retrieved record: {retrieved.get('data')}")

    # 4. Database Querying
    print_header("Test 4: Database Collection Query (POST /data/{collection}/query)")
    query_results = await shiv_db_service.query_records(collection=test_collection, limit=10)
    print(f"Query returned {len(query_results)} items.")
    assert len(query_results) > 0, "Query returned no items"
    found_item = any(item.get("id") == record_id for item in query_results)
    print(f"[PASS] Query records verified. Newly created item present: {found_item}")

    # 5. Database Record Cleanup
    print_header("Test 5: Database Record Deletion (DELETE /data/{col}/{id})")
    deleted = await shiv_db_service.delete_record(collection=test_collection, record_id=record_id)
    print(f"Deletion result: {deleted}")
    assert deleted, "Failed to delete test record"
    print(f"[PASS] Record {record_id} successfully deleted.")

    # 6. Auth User Registration
    print_header("Test 6: User Registration (POST /auth/register)")
    test_username = f"user_{int(time.time())}"
    test_email = f"{test_username}@example.com"
    test_password = "SecurePassword123!"

    reg_result = await shiv_db_service.register_user(
        email=test_email,
        password=test_password,
        username=test_username,
        display_name="Shivam Platform Admin"
    )
    print(f"Registration Result: {reg_result}")
    assert reg_result and reg_result.get("username") == test_username, "User registration failed"
    print(f"[PASS] Successfully registered user: {reg_result.get('email')}")

    # 7. Auth User Login & JWT Token Retrieval
    print_header("Test 7: User Login & JWT Issuance (POST /auth/login)")
    login_result = await shiv_db_service.login_user(
        email_or_username=test_username,
        password=test_password
    )
    print(f"Login Response: token_type={login_result.get('token_type')}, expires_in={login_result.get('expires_in')}")
    access_token = login_result.get("access_token")
    assert access_token, "No access token received from login"
    print(f"[PASS] Received JWT Access Token: {access_token[:25]}...")

    # 8. User Profile Verification
    print_header("Test 8: User Profile Verification with Bearer Token (GET /auth/me)")
    profile = await shiv_db_service.get_me(access_token=access_token)
    print(f"Profile: {profile}")
    assert profile and profile.get("username") == test_username, "Failed to resolve user profile"
    print(f"[PASS] Profile verified for user {profile.get('username')} (role: {profile.get('role')})")

    print_header("AUDIT SUMMARY: ALL SHIV DB & AUTH INTEGRATION TESTS PASSED 100%")


if __name__ == "__main__":
    asyncio.run(main())
