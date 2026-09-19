"""
Live Protection page for SnapGuard AI.
Left: real-time camera feed with bounding boxes.
Right: detection status panel.
Uses QThread worker for non-blocking frame processing.
"""

import logging
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMutex, QMutexLocker
from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QMessageBox, QScrollArea,
)

from app.config import RiskLevel, RISK_COLORS, get_settings
from app.camera.camera_manager import CameraManager
from app.inference.model_manager import ModelManager
from app.inference.base_backend import InferenceResult, Detection
from app.privacy.privacy_engine import PrivacyRiskEngine, RiskAssessment
from app.privacy.privacy_mode import get_privacy_manager, PrivacyModeState

log = logging.getLogger("SnapGuard AI")


# ─────────────────────────────────────────────────────────────────────────────
# Inference worker thread
# ─────────────────────────────────────────────────────────────────────────────

class InferenceWorker(QThread):
    """
    Runs AI inference on frames received from CameraWorker.
    Emits results back to the UI thread.
    """
    result_ready = Signal(object, object)   # (np.ndarray frame, InferenceResult)

    def __init__(self, model_manager: ModelManager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager
        self._frame_queue: deque = deque(maxlen=2)  # drop old frames
        self._mutex = QMutex()
        self._running = False

    def push_frame(self, frame: np.ndarray):
        with QMutexLocker(self._mutex):
            self._frame_queue.append(frame.copy())

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            frame = None
            with QMutexLocker(self._mutex):
                if self._frame_queue:
                    frame = self._frame_queue.popleft()

            if frame is not None:
                try:
                    result = self._model_manager.infer(frame)
                    self.result_ready.emit(frame, result)
                except Exception as e:
                    log.error(f"[InferenceWorker] error: {e}")
            else:
                time.sleep(0.005)


# ─────────────────────────────────────────────────────────────────────────────
# Live Protection Page
# ─────────────────────────────────────────────────────────────────────────────

class LiveProtectionPage(QWidget):

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._settings    = get_settings()

        self._camera_mgr  = CameraManager()
        self._model_mgr   = ModelManager()
        self._risk_engine = PrivacyRiskEngine(
            warning_delay_frames  = self._settings.get("risk_warning_delay_frames", 15),
            cooldown_frames       = self._settings.get("risk_cooldown_frames", 30),
            shoulder_surf_proximity = self._settings.get("shoulder_surf_proximity", 0.25),
        )
        self._privacy_mode = get_privacy_manager()
        self._inf_worker: Optional[InferenceWorker] = None

        self._current_fps     = 0.0
        self._current_latency = 0.0
        self._last_assessment: Optional[RiskAssessment] = None
        self._model_loaded    = False
        self._is_running      = False
        self._is_demo         = False

        self._setup_ui()
        self._connect_privacy_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(0)

        # Page title
        title = QLabel("Live Protection")
        title.setObjectName("page_title")
        outer.addWidget(title)
        sub = QLabel("Real-time person detection and privacy monitoring")
        sub.setObjectName("page_subtitle")
        outer.addWidget(sub)

        # ── Inline privacy alert banner (hidden by default) ─────────
        self._alert_banner = QFrame()
        self._alert_banner.setObjectName("alert_overlay")
        alert_layout = QHBoxLayout(self._alert_banner)
        alert_layout.setContentsMargins(16, 10, 16, 10)
        self._alert_icon  = QLabel("⚠")
        self._alert_icon.setStyleSheet("font-size:18px; color:#F85149;")
        self._alert_text  = QLabel("Privacy alert")
        self._alert_text.setObjectName("alert_message")
        self._alert_text.setWordWrap(True)
        self._alert_dismiss = QPushButton("✕ Dismiss")
        self._alert_dismiss.setObjectName("btn_danger")
        self._alert_dismiss.setFixedWidth(100)
        self._alert_dismiss.setCursor(Qt.PointingHandCursor)
        self._alert_dismiss.clicked.connect(self._on_alert_dismiss_btn_clicked)
        alert_layout.addWidget(self._alert_icon)
        alert_layout.addWidget(self._alert_text, stretch=1)
        alert_layout.addWidget(self._alert_dismiss)
        self._alert_banner.setVisible(False)
        outer.addWidget(self._alert_banner)
        outer.addSpacing(8)

        # Main content: camera | info panel
        content = QHBoxLayout()
        content.setSpacing(20)
        content.addWidget(self._build_camera_panel(), 3)
        content.addWidget(self._build_info_panel(),   2)
        outer.addLayout(content, stretch=1)

        # Bottom controls
        outer.addSpacing(16)
        outer.addLayout(self._build_controls())

    def _build_camera_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Camera label
        self._camera_label = QLabel()
        self._camera_label.setObjectName("camera_frame")
        self._camera_label.setAlignment(Qt.AlignCenter)
        self._camera_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._camera_label.setMinimumSize(420, 320)
        self._camera_label.setText("📷\n\nCamera not started\nPress 'Start Protection'")
        self._camera_label.setStyleSheet(
            "background:#010409; border:2px solid #21262D; border-radius:8px;"
            "color:#484F58; font-size:14px;"
        )
        layout.addWidget(self._camera_label, stretch=1)

        # FPS overlay row
        fps_row = QHBoxLayout()
        self._fps_badge = QLabel("FPS: —")
        self._fps_badge.setObjectName("fps_overlay")
        fps_row.addWidget(self._fps_badge)

        self._latency_badge = QLabel("Latency: — ms")
        self._latency_badge.setObjectName("fps_overlay")
        fps_row.addWidget(self._latency_badge)

        self._camera_status = QLabel("⚫  Camera Off")
        self._camera_status.setStyleSheet("color:#8B949E; font-size:11px;")
        fps_row.addStretch()
        fps_row.addWidget(self._camera_status)
        layout.addLayout(fps_row)

        return panel

    def _build_info_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QLabel("DETECTION STATUS")
        header.setObjectName("section_header")
        layout.addWidget(header)

        # People count
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("People detected:"))
        self._people_count = QLabel("—")
        self._people_count.setObjectName("value_label")
        row1.addStretch()
        row1.addWidget(self._people_count)
        layout.addLayout(row1)

        # Primary user
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Primary user:"))
        self._primary_user = QLabel("—")
        self._primary_user.setObjectName("value_label")
        row2.addStretch()
        row2.addWidget(self._primary_user)
        layout.addLayout(row2)

        # Additional person
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Additional person:"))
        self._additional_person = QLabel("—")
        self._additional_person.setObjectName("value_label")
        row3.addStretch()
        row3.addWidget(self._additional_person)
        layout.addLayout(row3)

        # Shoulder surf
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Shoulder-surfing:"))
        self._shoulder_surf = QLabel("—")
        row4.addStretch()
        row4.addWidget(self._shoulder_surf)
        layout.addLayout(row4)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        layout.addWidget(sep1)

        # Risk level
        risk_row = QHBoxLayout()
        risk_row.addWidget(QLabel("Privacy risk:"))
        self._risk_badge = QLabel("—")
        self._risk_badge.setObjectName("badge_neutral")
        risk_row.addStretch()
        risk_row.addWidget(self._risk_badge)
        layout.addLayout(risk_row)

        # Message
        self._risk_message = QLabel("Waiting for camera...")
        self._risk_message.setObjectName("description_label")
        self._risk_message.setWordWrap(True)
        layout.addWidget(self._risk_message)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        # Protection mode
        pm_header = QLabel("PROTECTION")
        pm_header.setObjectName("section_header")
        layout.addWidget(pm_header)

        self._protection_status = QLabel("OFF")
        self._protection_status.setObjectName("badge_neutral")
        layout.addWidget(self._protection_status)

        self._pm_toggle_btn = QPushButton("Enable Monitoring")
        self._pm_toggle_btn.setObjectName("btn_primary")
        self._pm_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._pm_toggle_btn.clicked.connect(self._toggle_privacy_mode)
        layout.addWidget(self._pm_toggle_btn)

        layout.addStretch()

        # Model info
        sep3 = QFrame(); sep3.setFrameShape(QFrame.HLine)
        layout.addWidget(sep3)

        self._model_info_label = QLabel("Model: Loading...")
        self._model_info_label.setObjectName("card_sub")
        self._model_info_label.setWordWrap(True)
        layout.addWidget(self._model_info_label)

        return panel

    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._start_btn = QPushButton("▶  Start Protection")
        self._start_btn.setObjectName("btn_primary")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.clicked.connect(self._start_protection)
        row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.clicked.connect(self._stop_protection)
        self._stop_btn.setEnabled(False)
        row.addWidget(self._stop_btn)

        self._demo_btn = QPushButton("🎬  Demo Mode")
        self._demo_btn.setCursor(Qt.PointingHandCursor)
        self._demo_btn.clicked.connect(self._start_demo)
        row.addWidget(self._demo_btn)

        row.addStretch()

        self._backend_label = QLabel("Backend: —")
        self._backend_label.setObjectName("card_sub")
        row.addWidget(self._backend_label)

        return row

    # ------------------------------------------------------------------
    # Privacy mode
    # ------------------------------------------------------------------

    def _connect_privacy_signals(self):
        self._privacy_mode.state_changed.connect(self._on_privacy_state_changed)
        self._privacy_mode.alert_triggered.connect(self._show_privacy_alert)
        self._privacy_mode.alert_dismissed.connect(self._hide_privacy_alert)

    def _toggle_privacy_mode(self):
        if self._privacy_mode.state == PrivacyModeState.OFF:
            self._privacy_mode.enable_monitoring()
        else:
            self._privacy_mode.disable()

    def _on_privacy_state_changed(self, state_str: str):
        state = PrivacyModeState(state_str)
        if state == PrivacyModeState.OFF:
            self._protection_status.setText("OFF")
            self._protection_status.setObjectName("badge_neutral")
            self._pm_toggle_btn.setText("Enable Monitoring")
        elif state == PrivacyModeState.MONITORING:
            self._protection_status.setText("MONITORING")
            self._protection_status.setObjectName("badge_info")
            self._pm_toggle_btn.setText("Disable Monitoring")
        elif state == PrivacyModeState.PROTECTION_ACTIVE:
            self._protection_status.setText("⚠  PROTECTION ACTIVE")
            self._protection_status.setObjectName("badge_danger")
            self._pm_toggle_btn.setText("Dismiss Alert")
        self._protection_status.style().unpolish(self._protection_status)
        self._protection_status.style().polish(self._protection_status)

    def _show_privacy_alert(self, message: str):
        """Show an inline alert banner above the camera feed — no page navigation."""
        self._alert_text.setText(f"⚠  PRIVACY RISK DETECTED — {message}")
        self._alert_banner.setVisible(True)
        # Also notify the privacy_mode page in case user navigates there
        if self._main_window:
            pm_page = self._main_window.get_page("privacy_mode")
            if pm_page and hasattr(pm_page, "show_alert"):
                pm_page.show_alert(message)

    def _hide_privacy_alert(self):
        self._alert_banner.setVisible(False)
        if self._main_window:
            pm_page = self._main_window.get_page("privacy_mode")
            if pm_page and hasattr(pm_page, "hide_alert"):
                pm_page.hide_alert()

    def _on_alert_dismiss_btn_clicked(self):
        self._privacy_mode.dismiss_alert()
        self._hide_privacy_alert()

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def _start_protection(self, demo: bool = False):
        if self._is_running:
            return

        self._is_demo = demo
        self._model_loaded = self._model_mgr.initialize()

        if not self._model_loaded:
            self._model_info_label.setText(
                "⚠ Model not loaded. Run scripts/download_model.py first.\n"
                "Detection will run without AI — showing camera only."
            )
            self._risk_message.setText(
                "Model file missing. Download YOLOv8n.onnx to models/ directory."
            )

        # Start camera (Default index 1 = built-in laptop camera on macOS)
        cam_idx   = self._settings.get("camera_index", 1)
        res_w     = self._settings.get("camera_resolution_w", 640)
        res_h     = self._settings.get("camera_resolution_h", 480)
        fps_t     = self._settings.get("camera_fps_target", 30)

        demo_path = None
        if demo:
            from app.config import ROOT_DIR
            demo_path_candidate = ROOT_DIR / "assets" / "demo_video.mp4"
            if demo_path_candidate.exists():
                demo_path = str(demo_path_candidate)
            else:
                self._generate_demo_frames()
                demo_path = None  # fall back to live camera for demo

        worker = self._camera_mgr.start(
            camera_index    = cam_idx,
            target_fps      = fps_t,
            resolution      = (res_w, res_h),
            demo_video_path = demo_path,
        )
        worker.frame_ready.connect(self._on_frame)
        worker.error.connect(self._on_camera_error)
        worker.fps_updated.connect(self._on_fps_updated)

        # Start inference worker
        self._inf_worker = InferenceWorker(self._model_mgr)
        self._inf_worker.result_ready.connect(self._on_inference_result)
        if self._model_loaded:
            self._inf_worker.start()

        self._is_running = True
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._demo_btn.setEnabled(not demo)
        self._camera_status.setText("🟢  Camera Active")
        self._camera_status.setStyleSheet("color:#3FB950; font-size:11px;")

        if demo:
            self._camera_status.setText("🎬  DEMO MODE")
            self._camera_status.setStyleSheet("color:#E3B341; font-size:11px;")
            if self._main_window:
                self._main_window.show_demo_banner(True)

        # Backend info
        if self._model_loaded:
            info = self._model_mgr.get_model_info()
            self._model_info_label.setText(
                f"Model: {info.get('model_name','?')} | "
                f"Backend: {info.get('backend','?')} | "
                f"Device: {info.get('device','?')}"
            )
            self._backend_label.setText(
                f"Backend: {self._model_mgr.get_backend_name()} "
                f"({self._model_mgr.get_device()})"
            )

    def _start_demo(self):
        self._settings.set("demo_mode", True)
        self._start_protection(demo=True)

    def _stop_protection(self):
        if not self._is_running:
            return

        if self._inf_worker:
            self._inf_worker.stop()
            self._inf_worker.wait(2000)
            self._inf_worker = None

        self._camera_mgr.stop()
        self._is_running = False
        self._model_loaded = False
        self._settings.set("demo_mode", False)

        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._demo_btn.setEnabled(True)
        self._camera_label.clear()
        self._camera_label.setText("📷\n\nCamera stopped\nPress 'Start Protection'")
        self._camera_status.setText("⚫  Camera Off")
        self._camera_status.setStyleSheet("color:#8B949E; font-size:11px;")
        self._risk_engine.reset()
        if self._main_window:
            self._main_window.show_demo_banner(False)
        self._model_mgr.release()

    # ------------------------------------------------------------------
    # Frame handling
    # ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray):
        """Called from camera thread — push to inference worker or display directly."""
        if self._model_loaded and self._inf_worker:
            self._inf_worker.push_frame(frame)
        else:
            # No model — just display raw frame
            self._display_frame(frame, [])

    def _on_inference_result(self, frame: np.ndarray, result: InferenceResult):
        """Called from inference worker thread with annotated results."""
        if not self._is_running:
            return

        self._current_latency = result.latency_ms

        # Risk assessment
        assessment = self._risk_engine.assess(result)
        self._last_assessment = assessment

        # Feed privacy mode
        self._privacy_mode.process_risk(assessment.risk_level, assessment.message)

        # Update UI
        self._update_info_panel(assessment)
        self._display_frame(frame, result.detections)

        # Push to dashboard
        if self._main_window:
            dash = self._main_window.get_page("dashboard")
            if dash and hasattr(dash, "update_live_stats"):
                dash.update_live_stats(
                    assessment, self._current_fps,
                    self._current_latency, self._model_loaded
                )

        # Update latency badge
        self._latency_badge.setText(f"Latency: {result.latency_ms:.0f} ms")

    def _on_fps_updated(self, fps: float):
        self._current_fps = fps
        self._fps_badge.setText(f"FPS: {fps:.1f}")

    def _on_camera_error(self, message: str):
        self._is_running = False
        if self._inf_worker:
            self._inf_worker.stop()
            self._inf_worker = None
        self._model_loaded = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._camera_label.setText(f"⚠ Camera Error\n\n{message}")
        self._camera_status.setText("🔴  Camera Error")
        self._camera_status.setStyleSheet("color:#EF4444; font-size:11px;")
        log.error(f"Camera error: {message}")

    # ------------------------------------------------------------------
    # Frame rendering with bounding boxes
    # ------------------------------------------------------------------

    def _display_frame(self, frame: np.ndarray, detections: list[Detection]):
        """Convert frame to QPixmap with drawn bounding boxes."""
        if not self._is_running:
            return

        annotated = frame.copy()
        self._draw_detections(annotated, detections)

        # Convert BGR → RGB → QImage (with deep copy for Qt memory safety)
        h, w, ch = annotated.shape
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

        # Scale to fit label preserving aspect ratio.
        # Use a minimum fallback size so early frames (before first paint) still display.
        label_size = self._camera_label.size()
        if label_size.width() < 10 or label_size.height() < 10:
            label_size = self._camera_label.minimumSize()
        pixmap = QPixmap.fromImage(qimg).scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._camera_label.setPixmap(pixmap)

    def _draw_detections(self, frame: np.ndarray, detections: list[Detection]):
        """Draw color-coded bounding boxes and labels on frame."""
        risk = self._last_assessment.risk_level if self._last_assessment else RiskLevel.UNKNOWN

        # Choose box color based on risk
        color_map = {
            RiskLevel.SAFE:    (56, 185, 80),
            RiskLevel.LOW:     (139, 148, 158),
            RiskLevel.MEDIUM:  (249, 115, 22),
            RiskLevel.HIGH:    (239, 68, 68),
            RiskLevel.UNKNOWN: (139, 148, 158),
        }
        box_color = color_map.get(risk, (139, 148, 158))

        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det.bbox
            label = f"Person {i+1}  {det.confidence:.0%}"

            # Draw box
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            # Label background
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), box_color, -1)

            # Label text
            cv2.putText(
                frame, label,
                (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA
            )

        # Risk watermark
        if risk in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            msg = "⚠ PRIVACY RISK" if risk == RiskLevel.HIGH else "! MONITORING"
            cv2.putText(
                frame, msg,
                (10, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (239, 68, 68) if risk == RiskLevel.HIGH else (249, 115, 22),
                2, cv2.LINE_AA
            )

    # ------------------------------------------------------------------
    # Info panel update
    # ------------------------------------------------------------------

    def _update_info_panel(self, a: RiskAssessment):
        self._people_count.setText(str(a.people_count))
        self._primary_user.setText("✅ Detected" if a.primary_user_detected else "❌ Not detected")
        self._additional_person.setText(
            f"⚠ {a.additional_persons} detected" if a.additional_persons > 0 else "✅ None"
        )
        self._shoulder_surf.setText(
            "⚠ Potential risk" if a.shoulder_surf_suspected else "✅ Not detected"
        )
        self._shoulder_surf.setStyleSheet(
            "color:#EF4444;" if a.shoulder_surf_suspected else "color:#3FB950;"
        )

        # Risk badge
        badge_map = {
            RiskLevel.SAFE:    ("badge_safe",    "🟢 SAFE"),
            RiskLevel.LOW:     ("badge_neutral",  "⚪ LOW"),
            RiskLevel.MEDIUM:  ("badge_warning",  "🟡 MEDIUM"),
            RiskLevel.HIGH:    ("badge_danger",   "🔴 HIGH"),
            RiskLevel.UNKNOWN: ("badge_neutral",  "— UNKNOWN"),
        }
        obj_name, badge_text = badge_map.get(a.risk_level, ("badge_neutral", "—"))
        self._risk_badge.setText(badge_text)
        self._risk_badge.setObjectName(obj_name)
        self._risk_badge.style().unpolish(self._risk_badge)
        self._risk_badge.style().polish(self._risk_badge)

        self._risk_message.setText(a.message)

    # ------------------------------------------------------------------
    # Demo frame generator (fallback if no video file)
    # ------------------------------------------------------------------

    def _generate_demo_frames(self):
        """No-op: demo will use live camera if no video file present."""
        log.info("No demo video found — demo mode will use live camera feed.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_page_activated(self):
        pass

    def cleanup(self):
        self._stop_protection()
