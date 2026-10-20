"""
SHIV AI — Device Adapters Package
"""

from typing import Dict, Optional

from core.devices.adapters.android import AndroidDeviceAdapter
from core.devices.adapters.base import BaseDeviceAdapter
from core.devices.adapters.browser import BrowserAutomationAdapter
from core.devices.adapters.linux import LinuxDesktopAdapter
from core.devices.adapters.macos import MacOSDesktopAdapter
from core.devices.adapters.windows import WindowsDesktopAdapter
from core.devices.types import DeviceRecord, DeviceType

_ADAPTER_CACHE: Dict[str, BaseDeviceAdapter] = {}


def get_adapter_for_device(device: DeviceRecord) -> BaseDeviceAdapter:
    """Returns or creates the appropriate adapter instance for a device record."""
    dev_id = device.device_id
    if dev_id in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[dev_id]

    dtype = device.device_type
    adapter: BaseDeviceAdapter
    if dtype == DeviceType.WINDOWS:
        adapter = WindowsDesktopAdapter(device_id=dev_id)
    elif dtype == DeviceType.ANDROID:
        adapter = AndroidDeviceAdapter(device_id=dev_id)
    elif dtype == DeviceType.BROWSER:
        adapter = BrowserAutomationAdapter(device_id=dev_id)
    elif dtype == DeviceType.MACOS:
        adapter = MacOSDesktopAdapter(device_id=dev_id)
    elif dtype == DeviceType.LINUX:
        adapter = LinuxDesktopAdapter(device_id=dev_id)
    else:
        adapter = WindowsDesktopAdapter(device_id=dev_id)

    _ADAPTER_CACHE[dev_id] = adapter
    return adapter


__all__ = [
    "BaseDeviceAdapter",
    "WindowsDesktopAdapter",
    "AndroidDeviceAdapter",
    "BrowserAutomationAdapter",
    "MacOSDesktopAdapter",
    "LinuxDesktopAdapter",
    "get_adapter_for_device",
]
