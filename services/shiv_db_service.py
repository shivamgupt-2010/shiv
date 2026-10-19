"""
SHIV Database Data Fabric & Unified Auth Client Service.
Provides an asynchronous HTTP connector to the centralized SHIV DB & Auth Platform
hosted at https://shiv-database.onrender.com.
Enforces project isolation, user scoping, and audit logging.
"""
import httpx
import logging
from typing import Dict, Any, List, Optional
from config.settings import settings

logger = logging.getLogger("shivai.services.shiv_db")


class ShivDBService:
    """Async client for persisting records and managing user auth in the SHIV Platform."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        project_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.base_url = (base_url or settings.SHIV_DB_URL).rstrip("/")
        self.project_id = project_id or settings.SHIV_DB_PROJECT_ID
        self.api_key = api_key or settings.SHIV_DB_API_KEY
        self.timeout = timeout

    def _headers(self, user_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "x-project-id": self.project_id,
        }
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        return headers

    async def create_record(
        self,
        collection: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        user_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Stores a new record in SHIV DB under the scoped project."""
        payload = dict(data)
        if user_id:
            payload["_user_id"] = user_id

        url = f"{self.base_url}/data/{collection}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(url, json=payload, headers=self._headers(user_token))
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    return res_json.get("data")
                else:
                    logger.warning(f"SHIV DB create_record failed ({resp.status_code}): {resp.text}")
                    return None
        except Exception as e:
            logger.warning(f"Failed to connect to SHIV DB ({url}): {e}")
            return None

    async def get_record(
        self,
        collection: str,
        record_id: str,
        user_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single record by ID."""
        url = f"{self.base_url}/data/{collection}/{record_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._headers(user_token))
                if resp.status_code == 200:
                    return resp.json().get("data")
                return None
        except Exception as e:
            logger.warning(f"Failed to get record from SHIV DB: {e}")
            return None

    async def query_records(
        self,
        collection: str,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 50,
        offset: int = 0,
        user_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries records in a collection using FilterCriterion list."""
        url = f"{self.base_url}/data/{collection}/query"
        payload: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if filters:
            payload["filters"] = filters
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(url, json=payload, headers=self._headers(user_token))
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return data.get("items", [])
                return []
        except Exception as e:
            logger.warning(f"Failed to query SHIV DB: {e}")
            return []

    async def delete_record(
        self,
        collection: str,
        record_id: str,
        user_token: Optional[str] = None,
    ) -> bool:
        """Deletes a record from SHIV DB."""
        url = f"{self.base_url}/data/{collection}/{record_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.delete(url, headers=self._headers(user_token))
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to delete record from SHIV DB: {e}")
            return False

    async def register_user(
        self,
        email: str,
        password: str,
        username: str,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Registers a new user in SHIV Auth."""
        url = f"{self.base_url}/auth/register"
        payload = {
            "email": email,
            "password": password,
            "username": username,
            "display_name": display_name,
            "metadata": metadata or {},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                if resp.status_code in (200, 201):
                    return resp.json().get("data")
                logger.warning(f"SHIV Auth register failed ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Failed to connect to SHIV Auth register: {e}")
            return None

    async def login_user(
        self,
        email_or_username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """Authenticates user with SHIV Auth and retrieves JWT access/refresh tokens."""
        url = f"{self.base_url}/auth/login"
        payload = {
            "email_or_username": email_or_username,
            "password": password,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                if resp.status_code == 200:
                    return resp.json().get("data")
                logger.warning(f"SHIV Auth login failed ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Failed to connect to SHIV Auth login: {e}")
            return None

    async def get_me(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetches current user profile from SHIV Auth using Bearer token."""
        url = f"{self.base_url}/auth/me"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
                if resp.status_code == 200:
                    return resp.json().get("data")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch profile from SHIV Auth: {e}")
            return None

    async def check_health(self) -> Dict[str, Any]:
        """Checks status of centralized SHIV Database & Auth instance."""
        url = f"{self.base_url}/health/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "degraded", "code": resp.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


# Singleton SHIV DB Client
shiv_db_service = ShivDBService()
