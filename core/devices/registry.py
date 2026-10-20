"""
SHIV AI — Device Registry & User-Controlled Pairing Manager
Handles secure device enrollment, short-lived pairing codes, token exchange,
capability discovery, health monitoring, and explicit revocation.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import secrets
import threading
import time
import uuid
from typing import Dict, List, Optional

from core.devices.types import (
    DeviceCapabilities,
    DeviceRecord,
    DeviceStatus,
    DeviceType,
)

logger = logging.getLogger("shivai.devices.registry")


class DeviceRegistry:
    """Central registry for enrolled, authorized, and paired devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, DeviceRecord] = {}
        self._pairing_codes: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Proactively register the local host as default device
        self._register_local_host_device()

    def _register_local_host_device(self) -> None:
        """Automatically enrolls the host running the backend as a controlled device."""
        os_name = platform.system().lower()
        dev_type = DeviceType.WINDOWS if "windows" in os_name else (
            DeviceType.MACOS if "darwin" in os_name else DeviceType.LINUX
        )
        host_record = DeviceRecord(
            device_id="host-local-primary",
            name=f"Primary Host ({platform.node() or 'Localhost'})",
            device_type=dev_type,
            status=DeviceStatus.ONLINE,
            capabilities=DeviceCapabilities(
                supports_screen_capture=True,
                supports_input_simulation=True,
                supports_accessibility_tree=True,
                supports_browser_automation=True,
                supports_file_transfer=True,
                screen_resolution="1920x1080",
                os_version=f"{platform.system()} {platform.release()}",
            ),
            paired_by_user_id="default_user",
            token_hash=hashlib.sha256(b"local-host-internal-token").hexdigest(),
            allowed_applications=["*"],
            granted_permissions=["read", "act", "admin"],
        )
        self._devices[host_record.device_id] = host_record

    def generate_pairing_code(
        self,
        user_id: str,
        name: str,
        device_type: DeviceType,
        ttl_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Generates a secure 6-digit or alpha-numeric pairing code."""
        code = f"{secrets.randbelow(900000) + 100000}"
        with self._lock:
            self._pairing_codes[code] = {
                "user_id": user_id,
                "name": name,
                "device_type": device_type,
                "expires_at": time.time() + ttl_seconds,
            }
        logger.info(f"Generated pairing code '{code}' for {user_id} ({device_type.value})")
        return {
            "pairing_code": code,
            "expires_in_seconds": ttl_seconds,
            "device_type": device_type.value,
        }

    def complete_pairing(
        self,
        pairing_code: str,
        capabilities: Optional[DeviceCapabilities] = None,
    ) -> Dict[str, Any]:
        """Exchanges a valid pairing code for a permanent device enrollment record and auth token."""
        with self._lock:
            info = self._pairing_codes.get(pairing_code)
            if not info:
                raise KeyError("Invalid or expired pairing code")

            if time.time() > info["expires_at"]:
                del self._pairing_codes[pairing_code]
                raise TimeoutError("Pairing code has expired")

            del self._pairing_codes[pairing_code]

            device_id = f"dev-{uuid.uuid4().hex[:12]}"
            device_secret_token = f"shiv-dev-{secrets.token_urlsafe(32)}"
            token_hash = hashlib.sha256(device_secret_token.encode()).hexdigest()

            record = DeviceRecord(
                device_id=device_id,
                name=info["name"],
                device_type=info["device_type"],
                status=DeviceStatus.ONLINE,
                capabilities=capabilities or DeviceCapabilities(),
                paired_by_user_id=info["user_id"],
                token_hash=token_hash,
                created_at=time.time(),
                last_seen_at=time.time(),
            )
            self._devices[device_id] = record

        logger.info(f"Device paired successfully: {device_id} ({record.name})")
        return {
            "device_id": device_id,
            "device_token": device_secret_token,
            "name": record.name,
            "device_type": record.device_type.value,
            "status": record.status.value,
        }

    def list_devices(self, user_id: Optional[str] = None) -> List[DeviceRecord]:
        """Lists all registered devices."""
        with self._lock:
            devs = list(self._devices.values())
            if user_id:
                devs = [d for d in devs if d.paired_by_user_id in (user_id, "default_user")]
            return sorted(devs, key=lambda d: d.created_at)

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        with self._lock:
            return self._devices.get(device_id)

    def heartbeat(self, device_id: str) -> bool:
        """Updates last_seen timestamp for a device."""
        with self._lock:
            dev = self._devices.get(device_id)
            if dev and dev.status != DeviceStatus.REVOKED:
                dev.last_seen_at = time.time()
                if dev.status == DeviceStatus.OFFLINE:
                    dev.status = DeviceStatus.ONLINE
                return True
            return False

    def revoke_device(self, device_id: str, user_id: str = "default_user") -> bool:
        """Revokes a device authorization completely."""
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return False
            dev.status = DeviceStatus.REVOKED
            dev.token_hash = ""
            logger.warning(f"Device '{device_id}' revoked by {user_id}")
            return True


_device_registry_singleton = DeviceRegistry()


def get_device_registry() -> DeviceRegistry:
    return _device_registry_singleton
