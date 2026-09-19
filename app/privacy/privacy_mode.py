"""
Privacy Mode Manager for SnapGuard AI.
Controls privacy protection state machine and triggers in-app protective actions.
"""

import logging
from enum import Enum
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from app.config import RiskLevel, get_settings

log = logging.getLogger("SnapGuard AI")


class PrivacyModeState(str, Enum):
    OFF               = "OFF"
    MONITORING        = "MONITORING"
    PROTECTION_ACTIVE = "PROTECTION_ACTIVE"


class PrivacyModeManager(QObject):
    """
    State machine for Privacy Mode.

    States:
        OFF               → Not watching, no actions taken
        MONITORING        → Watching, will react if HIGH risk detected
        PROTECTION_ACTIVE → HIGH risk confirmed, protective actions active

    Emits:
        state_changed(str)     → new state string
        alert_triggered(str)   → alert message when entering PROTECTION_ACTIVE
        alert_dismissed()      → user dismissed the alert
        incident_logged(dict)  → new incident entry
    """

    state_changed    = Signal(str)
    alert_triggered  = Signal(str)
    alert_dismissed  = Signal()
    incident_logged  = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = PrivacyModeState.OFF
        self._settings = get_settings()
        self._auto_activate = self._settings.get("privacy_mode_auto_activate", True)
        self._auto_dismiss = self._settings.get("privacy_mode_auto_dismiss", True)
        self._incidents: list[dict] = []

        # Load persisted state
        saved_state = self._settings.get("privacy_mode_state", "MONITORING")
        try:
            self._state = PrivacyModeState(saved_state)
        except ValueError:
            self._state = PrivacyModeState.MONITORING

        # Add initial boot log
        self._log_incident("INFO", "Privacy engine initialized", f"State: {self._state.value}")

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "PrivacyModeManager":
        global _privacy_mgr_instance
        if _privacy_mgr_instance is None:
            _privacy_mgr_instance = PrivacyModeManager()
        return _privacy_mgr_instance

    # ------------------------------------------------------------------
    # State control
    # ------------------------------------------------------------------

    @property
    def state(self) -> PrivacyModeState:
        return self._state

    def set_state(self, new_state: PrivacyModeState):
        if new_state == self._state:
            return
        old = self._state
        self._state = new_state
        self._settings.set("privacy_mode_state", new_state.value)
        log.info(f"[PrivacyMode] {old.value} → {new_state.value}")
        self.state_changed.emit(new_state.value)

    def enable_monitoring(self):
        self.set_state(PrivacyModeState.MONITORING)
        self._log_incident("INFO", "Monitoring Enabled", "Watching for unauthorized viewers")

    def disable(self):
        if self._state == PrivacyModeState.PROTECTION_ACTIVE:
            self.dismiss_alert()
        self.set_state(PrivacyModeState.OFF)
        self._log_incident("INFO", "Protection Disabled", "Privacy guard turned off")

    def activate_protection(self, reason: str = "High privacy risk detected"):
        self.set_state(PrivacyModeState.PROTECTION_ACTIVE)
        self.alert_triggered.emit(reason)
        self._settings.log_event("WARNING", f"Privacy protection activated: {reason}")
        self._log_incident("WARNING", "Shield Activated", reason)

    def dismiss_alert(self):
        if self._state == PrivacyModeState.PROTECTION_ACTIVE:
            self.set_state(PrivacyModeState.MONITORING)
        self.alert_dismissed.emit()
        self._log_incident("INFO", "Alert Dismissed", "Returned to active monitoring")

    def simulate_test_alert(self):
        """Trigger a simulated alert to test the overlay and notification mechanisms."""
        self.activate_protection("Test Simulation: Unauthorized observer simulated near display")

    # ------------------------------------------------------------------
    # Risk integration
    # ------------------------------------------------------------------

    def process_risk(self, risk_level: str, message: str = ""):
        """
        Called every frame with the current risk level.
        Automatically activates protection if configured to do so.
        Debounced to avoid rapid flickering from single-frame drops.
        """
        if self._state == PrivacyModeState.OFF:
            return

        if risk_level == RiskLevel.HIGH and self._auto_activate:
            self._calm_frames = 0
            if self._state != PrivacyModeState.PROTECTION_ACTIVE:
                import time
                now = time.time()
                if now - getattr(self, "_last_alert_time", 0) > 2.0:
                    self._last_alert_time = now
                    self.activate_protection(message or "High privacy risk detected")

        elif risk_level in (RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.UNKNOWN):
            if self._state == PrivacyModeState.PROTECTION_ACTIVE and self._auto_dismiss:
                self._calm_frames = getattr(self, "_calm_frames", 0) + 1
                # Require ~1.5s (45 frames) of continuous calm before auto-dismissing
                if self._calm_frames >= 45:
                    self._calm_frames = 0
                    self.dismiss_alert()
            else:
                self._calm_frames = 0

    # ------------------------------------------------------------------
    # Incident Tracking
    # ------------------------------------------------------------------

    def _log_incident(self, level: str, title: str, details: str):
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": now,
            "level": level,
            "title": title,
            "details": details,
        }
        self._incidents.insert(0, entry)
        if len(self._incidents) > 50:
            self._incidents.pop()
        self.incident_logged.emit(entry)

    def get_incidents(self) -> list[dict]:
        return list(self._incidents)

    def clear_incidents(self):
        self._incidents.clear()
        self._log_incident("INFO", "Log Cleared", "Audit log reset by user")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_auto_activate(self, enabled: bool):
        self._auto_activate = enabled
        self._settings.set("privacy_mode_auto_activate", enabled)

    def is_auto_activate(self) -> bool:
        return self._auto_activate

    def set_auto_dismiss(self, enabled: bool):
        self._auto_dismiss = enabled
        self._settings.set("privacy_mode_auto_dismiss", enabled)

    def is_auto_dismiss(self) -> bool:
        return self._auto_dismiss

    def is_active(self) -> bool:
        return self._state == PrivacyModeState.PROTECTION_ACTIVE

    def is_monitoring(self) -> bool:
        return self._state in (
            PrivacyModeState.MONITORING, PrivacyModeState.PROTECTION_ACTIVE
        )


_privacy_mgr_instance: Optional[PrivacyModeManager] = None


def get_privacy_manager() -> PrivacyModeManager:
    global _privacy_mgr_instance
    if _privacy_mgr_instance is None:
        _privacy_mgr_instance = PrivacyModeManager()
    return _privacy_mgr_instance

