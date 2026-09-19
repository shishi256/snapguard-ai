# SnapGuard AI — Application Configuration
"""
Central configuration, constants, and SQLite-backed settings manager.
"""

import os
import sqlite3
import json
import logging
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent          # snapguard-ai/
APP_DIR = Path(__file__).resolve().parent                  # snapguard-ai/app/
MODELS_DIR = ROOT_DIR / "models"
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"
LOGS_DIR = ROOT_DIR / "logs"
DOCS_DIR = ROOT_DIR / "docs"

for _d in (MODELS_DIR, DATA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "snapguard.db"

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_NAME = "SnapGuard AI"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Your laptop. Your data. Your privacy."
APP_AUTHOR = "SnapGuard AI Team"
COMPETITION = "Snapdragon AI Lab Build & Present Challenge"

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

MODEL_CONFIG_PATH = MODELS_DIR / "model_config.json"

DEFAULT_MODEL_CONFIG = {
    "model_name": "YOLOv8n",
    "model_file": "yolov8n.onnx",
    "input_size": [640, 640],
    "confidence_threshold": 0.5,
    "iou_threshold": 0.45,
    "person_class_id": 0,
    "source": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
    "license": "AGPL-3.0",
}

# ---------------------------------------------------------------------------
# Default application settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    # Camera — index 1 = built-in laptop camera (index 0 = iPhone Continuity Camera on macOS)
    "camera_index": 1,
    "camera_resolution_w": 640,
    "camera_resolution_h": 480,
    "camera_fps_target": 30,
    # Detection
    "confidence_threshold": 0.50,
    "iou_threshold": 0.45,
    # Privacy engine
    "risk_warning_delay_frames": 15,   # frames before escalating risk
    "risk_cooldown_frames": 30,        # frames of calm before de-escalating
    "shoulder_surf_proximity": 0.25,   # fraction of frame width
    # Privacy mode
    "privacy_mode_enabled": False,
    "privacy_mode_auto_activate": True,
    "privacy_mode_state": "OFF",       # OFF / MONITORING / PROTECTION_ACTIVE
    # Sensitive content
    "sensitive_content_detection": False,
    # AI backend
    "ai_backend": "local_onnx",        # local_onnx / qualcomm
    "target_device": "development",    # development / snapdragon_pc
    # Performance
    "benchmark_duration_sec": 10,
    # UI
    "theme": "light",
    "show_fps_overlay": True,
    "show_confidence": True,
    "demo_mode": False,
    "privacy_audio_alert": True,
    "privacy_auto_open_page": True,
}

# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

class RiskLevel:
    UNKNOWN = "UNKNOWN"
    SAFE    = "SAFE"
    LOW     = "LOW"
    MEDIUM  = "MEDIUM"
    HIGH    = "HIGH"

RISK_COLORS = {
    RiskLevel.UNKNOWN: "#6B7280",
    RiskLevel.SAFE:    "#10B981",
    RiskLevel.LOW:     "#F59E0B",
    RiskLevel.MEDIUM:  "#F97316",
    RiskLevel.HIGH:    "#EF4444",
}

# ---------------------------------------------------------------------------
# Settings manager
# ---------------------------------------------------------------------------

class SettingsManager:
    """SQLite-backed persistent settings store."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._cache: dict = {}
        self._init_db()
        self._load_all()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_results (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    backend     TEXT,
                    avg_latency REAL,
                    min_latency REAL,
                    max_latency REAL,
                    fps         REAL,
                    cpu_pct     REAL,
                    ram_mb      REAL,
                    notes       TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level     TEXT,
                    message   TEXT
                )
            """)
            conn.commit()

    def _load_all(self):
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        stored = {k: json.loads(v) for k, v in rows}
        # Merge defaults with stored (stored wins)
        self._cache = {**DEFAULT_SETTINGS, **stored}

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        self._cache[key] = value
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
            conn.commit()

    def get_all(self) -> dict:
        return dict(self._cache)

    def reset_to_defaults(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM settings")
            conn.commit()
        self._cache = dict(DEFAULT_SETTINGS)

    def save_benchmark_result(self, result: dict):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO benchmark_results
                    (timestamp, backend, avg_latency, min_latency, max_latency,
                     fps, cpu_pct, ram_mb, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get("timestamp", ""),
                result.get("backend", ""),
                result.get("avg_latency", 0),
                result.get("min_latency", 0),
                result.get("max_latency", 0),
                result.get("fps", 0),
                result.get("cpu_pct", 0),
                result.get("ram_mb", 0),
                result.get("notes", ""),
            ))
            conn.commit()

    def get_benchmark_results(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM benchmark_results ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def log_event(self, level: str, message: str):
        from datetime import datetime
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO event_log (timestamp, level, message) VALUES (?, ?, ?)",
                (datetime.now().isoformat(), level, message)
            )
            conn.commit()


# Singleton instance
_settings_manager: Optional[SettingsManager] = None

def get_settings() -> SettingsManager:
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
