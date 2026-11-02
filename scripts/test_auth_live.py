import json
import time
import urllib.request

ts = int(time.time())
test_email = f"testdev_{ts}@shiv.platform"
test_username = f"dev_{ts % 100000}"

print(f"Testing registration for: {test_email} / {test_username}...")
reg_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/register",
    data=json.dumps({
        "email": test_email,
        "username": test_username,
        "password": "SecurePassword123!",
        "display_name": "Shiv Test Developer",
        "phone": "+919876543210"
    }).encode(),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(reg_req) as resp:
        reg_data = json.loads(resp.read().decode())
        print("Registration SUCCESS:", reg_data)
        user_info = reg_data.get("data", {})
        print(f"Created SHIV ID: {user_info.get('shiv_id')}, User ID: {user_info.get('id')}")
except Exception as e:
    print("Registration FAILED:", e)
    raise

# Now test login with newly created user
print("\nTesting login with new user...")
login_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/login",
    data=json.dumps({
        "email_or_username": test_username,
        "password": "SecurePassword123!"
    }).encode(),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(login_req) as resp:
    login_data = json.loads(resp.read().decode())
    print("Login SUCCESS!")
    token = login_data["data"]["access_token"]
    refresh = login_data["data"]["refresh_token"]
    print(f"JWT Token Prefix: {token[:35]}...")

# Now test /auth/me with new token
print("\nTesting /auth/me with bearer token...")
me_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/me",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(me_req) as resp:
    me_data = json.loads(resp.read().decode())
    print("Profile SUCCESS:", me_data["data"])

# Now test /auth/refresh
print("\nTesting /auth/refresh with refresh token...")
ref_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/refresh",
    data=json.dumps({"refresh_token": refresh}).encode(),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(ref_req) as resp:
    ref_data = json.loads(resp.read().decode())
    print("Refresh SUCCESS! New access token:", ref_data["data"]["access_token"][:35] + "...")

print("\nALL AUTH TESTS PASSED PERFECTLY!")
