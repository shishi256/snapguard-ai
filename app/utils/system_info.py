"""
System information utilities for SnapGuard AI.
Detects hardware capabilities including Qualcomm/Snapdragon NPU availability.
"""

import platform
import subprocess
import psutil
from dataclasses import dataclass, field
from typing import Optional
import logging

log = logging.getLogger("SnapGuard AI")


@dataclass
class SystemInfo:
    os_name: str = ""
    os_version: str = ""
    cpu_name: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    ram_total_gb: float = 0.0
    python_version: str = ""
    # GPU / NPU
    gpu_info: str = "Not detected"
    qualcomm_npu_available: bool = False
    qualcomm_npu_name: str = "Not available"
    # Runtime availability
    onnxruntime_available: bool = False
    onnxruntime_version: str = "Not installed"
    qai_hub_available: bool = False
    qai_hub_version: str = "Not installed"
    opencv_available: bool = False
    opencv_version: str = "Not installed"
    pyside6_available: bool = False
    pyside6_version: str = "Not installed"
    # Mode
    is_development_mode: bool = True
    mode_label: str = "Development / Compatibility Mode"


def collect_system_info() -> SystemInfo:
    info = SystemInfo()

    # OS
    info.os_name = platform.system()
    info.os_version = platform.version()

    # CPU
    info.cpu_cores_physical = psutil.cpu_count(logical=False) or 0
    info.cpu_cores_logical = psutil.cpu_count(logical=True) or 0
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(
                ["wmic", "cpu", "get", "name"], text=True, timeout=3
            )
            info.cpu_name = result.strip().split("\n")[1].strip()
        elif platform.system() == "Darwin":
            result = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=3
            )
            info.cpu_name = result.strip()
        else:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info.cpu_name = line.split(":")[1].strip()
                        break
    except Exception:
        info.cpu_name = platform.processor() or "Unknown"

    # RAM
    info.ram_total_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)

    # Python
    info.python_version = platform.python_version()

    # ONNX Runtime
    try:
        import onnxruntime as ort
        info.onnxruntime_available = True
        info.onnxruntime_version = ort.__version__
    except ImportError:
        pass

    # Qualcomm AI Hub
    try:
        import qai_hub
        info.qai_hub_available = True
        info.qai_hub_version = getattr(qai_hub, "__version__", "installed")
    except ImportError:
        pass

    # OpenCV
    try:
        import cv2
        info.opencv_available = True
        info.opencv_version = cv2.__version__
    except ImportError:
        pass

    # PySide6
    try:
        import PySide6
        info.pyside6_available = True
        info.pyside6_version = PySide6.__version__
    except ImportError:
        pass

    # Qualcomm NPU detection
    info.qualcomm_npu_available, info.qualcomm_npu_name = _detect_qualcomm_npu()

    # Mode
    if info.qualcomm_npu_available and info.qai_hub_available:
        info.is_development_mode = False
        info.mode_label = "Snapdragon NPU Mode"
    else:
        info.is_development_mode = True
        info.mode_label = "Development / Compatibility Mode"

    return info


def _detect_qualcomm_npu() -> tuple[bool, str]:
    """
    Attempt to detect Qualcomm Snapdragon NPU on this machine.
    Returns (available: bool, name: str).
    """
    # Check Windows Device Manager for Qualcomm NPU
    if platform.system() == "Windows":
        try:
            result = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Qualcomm*' -or $_.FriendlyName -like '*Hexagon*'} | Select-Object FriendlyName"],
                text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            lines = [l.strip() for l in result.strip().split("\n") if l.strip() and "FriendlyName" not in l]
            if lines:
                return True, lines[0]
        except Exception:
            pass

    # Check for QAIRT / AI Engine Direct on Windows
    try:
        import qai_hub
        devices = qai_hub.get_devices()
        if devices:
            return True, "Qualcomm AI Hub Connected"
    except Exception:
        pass

    return False, "Not available"


def get_current_metrics() -> dict:
    """Return live CPU and RAM usage."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_used_mb": round(psutil.virtual_memory().used / (1024 ** 2), 1),
        "ram_total_mb": round(psutil.virtual_memory().total / (1024 ** 2), 1),
        "ram_percent": psutil.virtual_memory().percent,
    }


# Cached at module level after first call
_cached_info: Optional[SystemInfo] = None

def get_system_info(refresh: bool = False) -> SystemInfo:
    global _cached_info
    if _cached_info is None or refresh:
        _cached_info = collect_system_info()
    return _cached_info
