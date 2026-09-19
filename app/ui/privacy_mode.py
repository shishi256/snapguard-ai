"""
Privacy Mode page for SnapGuard AI.
Provides real-time protection status, threat simulation, incident audit log,
and automated privacy defense policies.
"""

import logging
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea, QCheckBox, QApplication,
)

from app.config import get_settings
from app.privacy.privacy_mode import get_privacy_manager, PrivacyModeState

log = logging.getLogger("SnapGuard AI")


class PrivacyModePage(QWidget):
    """
    Robust Privacy Mode dashboard and control page.
    Fully synchronized with Live Protection and the core privacy engine.
    """

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._settings    = get_settings()
        self._privacy_mgr = get_privacy_manager()

        self._incident_labels = []
        self._setup_ui()
        self._connect_signals()
        self._sync_state()

    # ------------------------------------------------------------------
    # UI Layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll area for smooth, responsive viewing
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #0b0f19; width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #334155; border-radius: 4px; min-height: 24px; }"
            "QScrollBar::handle:vertical:hover { background: #00D4FF; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setObjectName("content_area")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(36, 28, 36, 36)
        self._content_layout.setSpacing(20)

        # ── Header ──────────────────────────────────────────────────
        title = QLabel("Privacy Mode")
        title.setObjectName("page_title")
        self._content_layout.addWidget(title)

        sub = QLabel("Automated visual privacy shield — real-time detection & defense")
        sub.setObjectName("page_subtitle")
        self._content_layout.addWidget(sub)

        # ── Alert Overlay Banner (shown on threat) ──────────────────
        self._alert_frame = self._build_alert_overlay()
        self._alert_frame.setVisible(False)
        self._content_layout.addWidget(self._alert_frame)

        # ── Section 1: Protection State & Controls ──────────────────
        self._content_layout.addWidget(self._build_state_card())

        # ── Section 2: Policies & Configuration ─────────────────────
        self._content_layout.addWidget(self._build_settings_card())

        # ── Section 3: Live Incident & Audit Log ────────────────────
        self._content_layout.addWidget(self._build_incident_card())

        # ── Section 4: How It Works & Architecture ──────────────────
        self._content_layout.addWidget(self._build_info_card())

        self._content_layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Card 1: Alert Overlay
    # ------------------------------------------------------------------

    def _build_alert_overlay(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("alert_overlay")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)

        icon_row = QHBoxLayout()
        icon = QLabel("⚠")
        icon.setStyleSheet("font-size: 38px; color: #FF4D6D;")
        icon_row.addStretch()
        icon_row.addWidget(icon)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        self._alert_title = QLabel("PRIVACY THREAT DETECTED")
        self._alert_title.setObjectName("alert_title")
        self._alert_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._alert_title)

        self._alert_message = QLabel("An additional observer was detected near your screen.")
        self._alert_message.setObjectName("alert_message")
        self._alert_message.setWordWrap(True)
        self._alert_message.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._alert_message)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)
        btn_row.addStretch()

        dismiss_btn = QPushButton("✓  Dismiss Shield")
        dismiss_btn.setObjectName("btn_primary")
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.clicked.connect(self._dismiss_alert)
        btn_row.addWidget(dismiss_btn)

        live_btn = QPushButton("📷  View Live Camera")
        live_btn.setObjectName("btn_danger")
        live_btn.setCursor(Qt.PointingHandCursor)
        live_btn.clicked.connect(self._navigate_live_protection)
        btn_row.addWidget(live_btn)

        settings_btn = QPushButton("⚙  Adjust Settings")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(
            lambda: self._main_window.navigate("settings") if self._main_window else None
        )
        btn_row.addWidget(settings_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return frame

    # ------------------------------------------------------------------
    # Card 2: Protection State & Action Controls
    # ------------------------------------------------------------------

    def _build_state_card(self) -> QFrame:
        self._state_card = QFrame()
        self._state_card.setObjectName("card")
        layout = QVBoxLayout(self._state_card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header = QLabel("PROTECTION STATE")
        header.setObjectName("section_header")
        header_row.addWidget(header)
        header_row.addStretch()

        self._header_pill = QLabel("INITIALIZING")
        self._header_pill.setStyleSheet(
            "font-size: 11px; font-weight: 700; padding: 3px 10px; "
            "border-radius: 12px; background: rgba(51, 65, 85, 0.4); color: #94A3B8;"
        )
        header_row.addWidget(self._header_pill)
        layout.addLayout(header_row)

        # Dynamic State Banner
        self._state_banner = QLabel("OFF")
        self._state_banner.setAlignment(Qt.AlignCenter)
        self._state_banner.setStyleSheet(
            "font-size: 20px; font-weight: 800; padding: 18px; border-radius: 10px; "
            "background: rgba(15, 23, 42, 0.6); color: #94A3B8; border: 1.5px solid #334155;"
        )
        layout.addWidget(self._state_banner)

        # Context description
        self._state_desc = QLabel("Privacy mode is disabled. Enable protection to monitor for onlookers.")
        self._state_desc.setObjectName("description_label")
        self._state_desc.setWordWrap(True)
        layout.addWidget(self._state_desc)

        # Sensor status indicator
        sensor_box = QFrame()
        sensor_box.setStyleSheet(
            "background: rgba(10, 16, 30, 0.6); border: 1px solid rgba(51, 65, 85, 0.4); "
            "border-radius: 8px; padding: 10px 14px;"
        )
        sensor_layout = QHBoxLayout(sensor_box)
        sensor_layout.setContentsMargins(0, 0, 0, 0)
        sensor_layout.setSpacing(10)

        self._sensor_dot = QLabel("●")
        self._sensor_dot.setStyleSheet("color: #64748B; font-size: 14px;")
        sensor_layout.addWidget(self._sensor_dot)

        self._sensor_status = QLabel("Camera: Checking status...")
        self._sensor_status.setStyleSheet("color: #CBD5E1; font-size: 12px; font-weight: 500;")
        sensor_layout.addWidget(self._sensor_status, stretch=1)

        layout.addWidget(sensor_box)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._toggle_btn = QPushButton("▶  Enable Protection")
        self._toggle_btn.setObjectName("btn_primary")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setMinimumHeight(40)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        btn_row.addWidget(self._toggle_btn)

        self._test_btn = QPushButton("⚡  Simulate Threat (Test)")
        self._test_btn.setObjectName("btn_blue")
        self._test_btn.setCursor(Qt.PointingHandCursor)
        self._test_btn.setMinimumHeight(40)
        self._test_btn.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(self._test_btn)

        self._cam_btn = QPushButton("📷  Live Camera")
        self._cam_btn.setCursor(Qt.PointingHandCursor)
        self._cam_btn.setMinimumHeight(40)
        self._cam_btn.clicked.connect(self._navigate_live_protection)
        btn_row.addWidget(self._cam_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return self._state_card

    # ------------------------------------------------------------------
    # Card 3: Protection Policies & Settings
    # ------------------------------------------------------------------

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QLabel("DEFENSE POLICIES & AUTOMATION")
        header.setObjectName("section_header")
        layout.addWidget(header)

        # Policy 1: Auto-activate
        self._auto_cb = QCheckBox("Auto-engage Privacy Shield upon confirmed HIGH risk")
        self._auto_cb.setChecked(self._settings.get("privacy_mode_auto_activate", True))
        self._auto_cb.toggled.connect(self._on_auto_activate_toggled)
        layout.addWidget(self._auto_cb)

        note1 = QLabel("Instantly raises the alert and activates protection when an additional presence is sustained.")
        note1.setObjectName("description_label")
        note1.setWordWrap(True)
        layout.addWidget(note1)

        layout.addSpacing(6)

        # Policy 2: Auto-dismiss
        self._auto_dismiss_cb = QCheckBox("Auto-dismiss Shield when workspace is clear again")
        self._auto_dismiss_cb.setChecked(self._settings.get("privacy_mode_auto_dismiss", True))
        self._auto_dismiss_cb.toggled.connect(self._on_auto_dismiss_toggled)
        layout.addWidget(self._auto_dismiss_cb)

        note2 = QLabel("Automatically resumes silent monitoring once observers leave your detection zone.")
        note2.setObjectName("description_label")
        note2.setWordWrap(True)
        layout.addWidget(note2)

        layout.addSpacing(6)

        # Policy 3: Audible Alert
        self._audio_cb = QCheckBox("Audible warning chime on threat confirmation")
        self._audio_cb.setChecked(self._settings.get("privacy_audio_alert", True))
        self._audio_cb.toggled.connect(self._on_audio_toggled)
        layout.addWidget(self._audio_cb)

        note3 = QLabel("Plays a subtle system notification tone when a visual privacy breach is identified.")
        note3.setObjectName("description_label")
        note3.setWordWrap(True)
        layout.addWidget(note3)

        return card

    # ------------------------------------------------------------------
    # Card 4: Incident & Audit Log
    # ------------------------------------------------------------------

    def _build_incident_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header = QLabel("REAL-TIME PRIVACY AUDIT LOG")
        header.setObjectName("section_header")
        header_row.addWidget(header)
        header_row.addStretch()

        clear_btn = QPushButton("Clear Audit Log")
        clear_btn.setStyleSheet(
            "font-size: 11px; padding: 4px 12px; background: rgba(30, 41, 59, 0.6); "
            "border: 1px solid rgba(71, 85, 105, 0.4); border-radius: 6px;"
        )
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_incidents)
        header_row.addWidget(clear_btn)

        layout.addLayout(header_row)

        self._incidents_container = QVBoxLayout()
        self._incidents_container.setSpacing(6)
        layout.addLayout(self._incidents_container)

        self._render_incidents()
        return card

    # ------------------------------------------------------------------
    # Card 5: How It Works & Architecture
    # ------------------------------------------------------------------

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        header = QLabel("HOW SNAPGUARD AI SHIELD WORKS")
        header.setObjectName("section_header")
        layout.addWidget(header)

        steps = [
            ("👁  AI Vision",        "Built-in laptop camera feeds frames into on-device YOLOv8 neural network."),
            ("🧠  Temporal Filter",  "Multi-frame temporal smoothing filters out brief motion and false positives."),
            ("🎯  Shoulder Surfing", "Proximity heuristics flag when an onlooker aligns directly with your screen."),
            ("🔒  Instant Shield",   "Engages real-time visual warning and logs the event in your local audit trail."),
            ("⚡  100% On-Device",   "Zero cloud calls. Video frames are processed in RAM only and never saved."),
        ]

        for tag, desc in steps:
            row = QHBoxLayout()
            lbl_tag = QLabel(tag)
            lbl_tag.setFixedWidth(140)
            lbl_tag.setStyleSheet("color: #00D4FF; font-weight: 700; font-size: 12px;")
            row.addWidget(lbl_tag)

            lbl_desc = QLabel(desc)
            lbl_desc.setObjectName("description_label")
            lbl_desc.setWordWrap(True)
            row.addWidget(lbl_desc, stretch=1)
            layout.addLayout(row)

        return card

    # ------------------------------------------------------------------
    # Signal Connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        try:
            self._privacy_mgr.state_changed.connect(self._on_state_changed)
            self._privacy_mgr.alert_triggered.connect(self._on_alert_triggered)
            self._privacy_mgr.alert_dismissed.connect(self._on_alert_dismissed)
            self._privacy_mgr.incident_logged.connect(self._on_incident_logged)
        except Exception as e:
            log.error(f"[PrivacyModePage] Error connecting signals: {e}")

    # ------------------------------------------------------------------
    # State Management & Handlers
    # ------------------------------------------------------------------

    def _sync_state(self):
        state = self._privacy_mgr.state
        self._on_state_changed(state.value)
        self._update_sensor_status()

    def _on_state_changed(self, state_str: str):
        try:
            state = PrivacyModeState(state_str)
        except ValueError:
            state = PrivacyModeState.OFF

        if state == PrivacyModeState.OFF:
            self._header_pill.setText("DISABLED")
            self._header_pill.setStyleSheet(
                "font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; "
                "background: rgba(30, 41, 59, 0.5); color: #64748B;"
            )
            self._state_banner.setText("○  PROTECTION DISABLED")
            self._state_banner.setStyleSheet(
                "font-size: 19px; font-weight: 800; padding: 16px; border-radius: 10px; "
                "background: rgba(15, 23, 42, 0.7); color: #94A3B8; border: 1.5px solid #334155;"
            )
            self._state_desc.setText(
                "Privacy protection is currently off. Enable monitoring to protect your display."
            )
            self._toggle_btn.setText("▶  Enable Protection")
            self._toggle_btn.setObjectName("btn_primary")
            self._toggle_btn.setEnabled(True)
            self._test_btn.setEnabled(True)
            self._alert_frame.setVisible(False)

        elif state == PrivacyModeState.MONITORING:
            self._header_pill.setText("ACTIVE")
            self._header_pill.setStyleSheet(
                "font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; "
                "background: rgba(0, 255, 136, 0.15); color: #00FF88;"
            )
            self._state_banner.setText("🟢  ACTIVE — MONITORING WORKSPACE")
            self._state_banner.setStyleSheet(
                "font-size: 19px; font-weight: 800; padding: 16px; border-radius: 10px; "
                "background: rgba(0, 255, 136, 0.08); color: #00FF88; border: 1.5px solid rgba(0, 255, 136, 0.4);"
            )
            self._state_desc.setText(
                "Continuous AI surveillance active. Shield will automatically trigger if onlookers appear."
            )
            self._toggle_btn.setText("⏹  Disable Protection")
            self._toggle_btn.setObjectName("")
            self._toggle_btn.setEnabled(True)
            self._test_btn.setEnabled(True)
            self._alert_frame.setVisible(False)

        elif state == PrivacyModeState.PROTECTION_ACTIVE:
            self._header_pill.setText("THREAT DETECTED")
            self._header_pill.setStyleSheet(
                "font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; "
                "background: rgba(255, 77, 109, 0.2); color: #FF4D6D;"
            )
            self._state_banner.setText("⚠  PROTECTION ACTIVE — THREAT CONFIRMED")
            self._state_banner.setStyleSheet(
                "font-size: 19px; font-weight: 800; padding: 16px; border-radius: 10px; "
                "background: rgba(255, 77, 109, 0.15); color: #FF4D6D; border: 1.5px solid rgba(255, 77, 109, 0.6);"
            )
            self._state_desc.setText(
                "High visual privacy risk confirmed! Threat shield is engaged."
            )
            self._toggle_btn.setText("✓  Dismiss Alert & Resume")
            self._toggle_btn.setObjectName("btn_primary")
            self._toggle_btn.setEnabled(True)
            self._test_btn.setEnabled(False)
            self._alert_frame.setVisible(True)

        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)
        self._update_sensor_status()

    def _update_sensor_status(self):
        """Check if Live Protection camera feed is active and update indicator."""
        is_cam_running = False
        if self._main_window:
            lp_page = self._main_window.get_page("live_protection")
            if lp_page and hasattr(lp_page, "_is_running"):
                is_cam_running = lp_page._is_running

        if is_cam_running:
            self._sensor_dot.setText("●")
            self._sensor_dot.setStyleSheet("color: #00FF88; font-size: 14px;")
            self._sensor_status.setText(
                "Built-in Laptop Camera: RUNNING — Real-time NPU person detection streaming"
            )
            self._sensor_status.setStyleSheet("color: #00FF88; font-size: 12px; font-weight: 600;")
        else:
            self._sensor_dot.setText("○")
            self._sensor_dot.setStyleSheet("color: #64748B; font-size: 14px;")
            self._sensor_status.setText(
                "Built-in Laptop Camera: IDLE — Open Live Camera to start real-time video detection"
            )
            self._sensor_status.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")

    # ------------------------------------------------------------------
    # Alert Handling
    # ------------------------------------------------------------------

    def show_alert(self, message: str):
        self._on_alert_triggered(message)

    def hide_alert(self):
        self._on_alert_dismissed()

    def _on_alert_triggered(self, message: str):
        self._alert_message.setText(message or "Unauthorized presence confirmed near screen.")
        self._alert_frame.setVisible(True)

        # Audible beep if configured
        if self._settings.get("privacy_audio_alert", True):
            try:
                QApplication.beep()
            except Exception:
                pass

    def _on_alert_dismissed(self):
        self._alert_frame.setVisible(False)

    def _dismiss_alert(self):
        try:
            self._privacy_mgr.dismiss_alert()
        except Exception as e:
            log.error(f"[PrivacyModePage] Error dismissing alert: {e}")

    # ------------------------------------------------------------------
    # Button Actions
    # ------------------------------------------------------------------

    def _on_toggle_clicked(self):
        try:
            current = self._privacy_mgr.state
            if current == PrivacyModeState.OFF:
                self._privacy_mgr.enable_monitoring()
            elif current == PrivacyModeState.MONITORING:
                self._privacy_mgr.disable()
            elif current == PrivacyModeState.PROTECTION_ACTIVE:
                self._privacy_mgr.dismiss_alert()
        except Exception as e:
            log.error(f"[PrivacyModePage] Toggle error: {e}")

    def _on_test_clicked(self):
        try:
            self._privacy_mgr.simulate_test_alert()
        except Exception as e:
            log.error(f"[PrivacyModePage] Simulation error: {e}")

    def _navigate_live_protection(self):
        if self._main_window:
            self._main_window.navigate("live_protection")

    # ------------------------------------------------------------------
    # Settings Checkboxes
    # ------------------------------------------------------------------

    def _on_auto_activate_toggled(self, checked: bool):
        self._privacy_mgr.set_auto_activate(checked)

    def _on_auto_dismiss_toggled(self, checked: bool):
        self._privacy_mgr.set_auto_dismiss(checked)

    def _on_audio_toggled(self, checked: bool):
        self._settings.set("privacy_audio_alert", checked)

    # ------------------------------------------------------------------
    # Incident Audit Log
    # ------------------------------------------------------------------

    def _on_incident_logged(self, entry: dict):
        self._render_incidents()

    def _clear_incidents(self):
        self._privacy_mgr.clear_incidents()
        self._render_incidents()

    def _render_incidents(self):
        # Clear layout
        while self._incidents_container.count():
            item = self._incidents_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        incidents = self._privacy_mgr.get_incidents()
        if not incidents:
            empty_lbl = QLabel("No privacy events recorded. Workspace is secure.")
            empty_lbl.setStyleSheet("color: #64748B; font-style: italic; padding: 8px 0;")
            self._incidents_container.addWidget(empty_lbl)
            return

        for item in incidents[:8]:  # Show top 8 recent incidents
            row = QFrame()
            row.setStyleSheet(
                "background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(51, 65, 85, 0.3); "
                "border-radius: 6px; padding: 6px 12px;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            # Time
            time_lbl = QLabel(item.get("time", ""))
            time_lbl.setStyleSheet(
                "color: #94A3B8; font-family: monospace; font-size: 11px; font-weight: 600;"
            )
            time_lbl.setFixedWidth(64)
            row_layout.addWidget(time_lbl)

            # Level badge
            lvl = item.get("level", "INFO")
            badge_styles = {
                "WARNING": ("background: rgba(255, 77, 109, 0.2); color: #FF4D6D;", "⚠ THREAT"),
                "INFO":    ("background: rgba(0, 212, 255, 0.12); color: #00D4FF;", "● STATUS"),
                "SAFE":    ("background: rgba(0, 255, 136, 0.15); color: #00FF88;", "✓ SAFE"),
            }
            style, text = badge_styles.get(lvl, ("background: #334155; color: #E2E8F0;", lvl))
            badge = QLabel(text)
            badge.setStyleSheet(f"font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; {style}")
            badge.setFixedWidth(74)
            row_layout.addWidget(badge)

            # Title
            title_lbl = QLabel(item.get("title", ""))
            title_lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600;")
            row_layout.addWidget(title_lbl)

            # Details
            details_lbl = QLabel(item.get("details", ""))
            details_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
            details_lbl.setWordWrap(True)
            row_layout.addWidget(details_lbl, stretch=1)

            self._incidents_container.addWidget(row)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_page_activated(self):
        """Called whenever user navigates to the Privacy Mode page."""
        self._sync_state()
        self._render_incidents()
        self._auto_cb.setChecked(self._privacy_mgr.is_auto_activate())
        self._auto_dismiss_cb.setChecked(self._privacy_mgr.is_auto_dismiss())
        self._audio_cb.setChecked(self._settings.get("privacy_audio_alert", True))
