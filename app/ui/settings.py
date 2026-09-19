"""
Settings page for SnapGuard AI.
All configurable parameters with live save to SQLite.
"""

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QScrollArea, QMessageBox,
)

from app.config import get_settings, DEFAULT_SETTINGS

log = logging.getLogger("SnapGuard AI")


class SettingsPage(QWidget):

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._settings    = get_settings()
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(0)

        title = QLabel("Settings")
        title.setObjectName("page_title")
        outer.addWidget(title)
        sub = QLabel("Configure detection, privacy, and AI backend settings")
        sub.setObjectName("page_subtitle")
        outer.addWidget(sub)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_appearance_section())
        layout.addWidget(self._build_camera_section())
        layout.addWidget(self._build_detection_section())
        layout.addWidget(self._build_privacy_section())
        layout.addWidget(self._build_ai_backend_section())
        layout.addWidget(self._build_sensitive_content_section())
        layout.addWidget(self._build_actions_section())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _section_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        hdr = QLabel(title)
        hdr.setObjectName("section_header")
        layout.addWidget(hdr)
        return card, layout

    def _row(self, layout: QVBoxLayout, label: str, widget, desc: str = "") -> None:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(220)
        row.addWidget(lbl)
        row.addWidget(widget)
        row.addStretch()
        layout.addLayout(row)
        if desc:
            d = QLabel(desc)
            d.setObjectName("card_sub")
            d.setIndent(224)
            layout.addWidget(d)

    def _build_appearance_section(self) -> QFrame:
        card, layout = self._section_card("APPEARANCE & THEME")

        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Light Theme (Crisp)", "light")
        self._theme_combo.addItem("Dark Theme (Neon / Glass)", "dark")
        current_theme = self._settings.get("theme", "light")
        self._theme_combo.setCurrentIndex(0 if current_theme == "light" else 1)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self._row(layout, "Color Theme:", self._theme_combo,
                  "Select between Light and Dark interface styles")

        return card

    def _on_theme_changed(self, index: int):
        theme_val = self._theme_combo.currentData()
        self._settings.set("theme", theme_val)
        if self._main_window and hasattr(self._main_window, "apply_theme"):
            self._main_window.apply_theme(theme_val)

    def _build_camera_section(self) -> QFrame:
        card, layout = self._section_card("CAMERA")

        self._cam_idx = QSpinBox()
        self._cam_idx.setRange(0, 10)
        self._cam_idx.setValue(self._settings.get("camera_index", 1))
        self._cam_idx.valueChanged.connect(lambda v: self._save("camera_index", v))
        self._row(layout, "Camera Index:", self._cam_idx,
                  "1 = built-in laptop camera | 0 = iPhone Continuity Camera (macOS)")

        self._cam_w = QSpinBox()
        self._cam_w.setRange(320, 1920)
        self._cam_w.setSingleStep(160)
        self._cam_w.setValue(self._settings.get("camera_resolution_w", 640))
        self._cam_w.valueChanged.connect(lambda v: self._save("camera_resolution_w", v))
        self._row(layout, "Resolution Width:", self._cam_w)

        self._cam_h = QSpinBox()
        self._cam_h.setRange(240, 1080)
        self._cam_h.setSingleStep(120)
        self._cam_h.setValue(self._settings.get("camera_resolution_h", 480))
        self._cam_h.valueChanged.connect(lambda v: self._save("camera_resolution_h", v))
        self._row(layout, "Resolution Height:", self._cam_h)

        self._cam_fps = QSpinBox()
        self._cam_fps.setRange(5, 60)
        self._cam_fps.setValue(self._settings.get("camera_fps_target", 30))
        self._cam_fps.valueChanged.connect(lambda v: self._save("camera_fps_target", v))
        self._row(layout, "Target FPS:", self._cam_fps)

        return card

    def _build_detection_section(self) -> QFrame:
        card, layout = self._section_card("DETECTION")

        self._conf_thresh = QDoubleSpinBox()
        self._conf_thresh.setRange(0.10, 0.99)
        self._conf_thresh.setSingleStep(0.05)
        self._conf_thresh.setDecimals(2)
        self._conf_thresh.setValue(self._settings.get("confidence_threshold", 0.50))
        self._conf_thresh.valueChanged.connect(lambda v: self._save("confidence_threshold", v))
        self._row(layout, "Confidence Threshold:", self._conf_thresh,
                  "Higher = fewer but more certain detections (0.10 – 0.99)")

        self._iou_thresh = QDoubleSpinBox()
        self._iou_thresh.setRange(0.10, 0.99)
        self._iou_thresh.setSingleStep(0.05)
        self._iou_thresh.setDecimals(2)
        self._iou_thresh.setValue(self._settings.get("iou_threshold", 0.45))
        self._iou_thresh.valueChanged.connect(lambda v: self._save("iou_threshold", v))
        self._row(layout, "NMS IoU Threshold:", self._iou_thresh)

        return card

    def _build_privacy_section(self) -> QFrame:
        card, layout = self._section_card("PRIVACY RISK ENGINE & ALERTS")

        # Sound on risk
        self._audio_cb = QCheckBox("Audible warning chime on threat")
        self._audio_cb.setChecked(self._settings.get("privacy_audio_alert", True))
        self._audio_cb.toggled.connect(lambda v: self._save("privacy_audio_alert", v))
        self._row(layout, "Audible Alarm:", self._audio_cb,
                  "Play system chime immediately when high risk or shoulder-surfing is detected")

        # Auto open privacy page
        self._auto_open_cb = QCheckBox("Directly open Privacy Mode page on threat")
        self._auto_open_cb.setChecked(self._settings.get("privacy_auto_open_page", True))
        self._auto_open_cb.toggled.connect(lambda v: self._save("privacy_auto_open_page", v))
        self._row(layout, "Threat Navigation:", self._auto_open_cb,
                  "Automatically switch window view to Privacy Mode when a threat triggers")

        self._warn_delay = QSpinBox()
        self._warn_delay.setRange(1, 300)
        self._warn_delay.setValue(self._settings.get("risk_warning_delay_frames", 15))
        self._warn_delay.valueChanged.connect(lambda v: self._save("risk_warning_delay_frames", v))
        self._row(layout, "Warning Delay (frames):", self._warn_delay,
                  "Consecutive frames with additional person before HIGH risk triggers")

        self._cooldown = QSpinBox()
        self._cooldown.setRange(1, 300)
        self._cooldown.setValue(self._settings.get("risk_cooldown_frames", 30))
        self._cooldown.valueChanged.connect(lambda v: self._save("risk_cooldown_frames", v))
        self._row(layout, "Cooldown (frames):", self._cooldown,
                  "Frames of calm before risk de-escalates")

        self._shoulder_prox = QDoubleSpinBox()
        self._shoulder_prox.setRange(0.05, 0.50)
        self._shoulder_prox.setSingleStep(0.05)
        self._shoulder_prox.setDecimals(2)
        self._shoulder_prox.setValue(self._settings.get("shoulder_surf_proximity", 0.25))
        self._shoulder_prox.valueChanged.connect(lambda v: self._save("shoulder_surf_proximity", v))
        self._row(layout, "Shoulder-surf Proximity:", self._shoulder_prox,
                  "Fraction of frame width — how close counts as center-facing")

        return card

    def _build_ai_backend_section(self) -> QFrame:
        card, layout = self._section_card("AI BACKEND")

        self._backend_combo = QComboBox()
        self._backend_combo.addItem("Local ONNX (CPU/GPU)", "local_onnx")
        self._backend_combo.addItem("Qualcomm AI Runtime  [Snapdragon PC required]", "qualcomm")
        current = self._settings.get("ai_backend", "local_onnx")
        idx = 0 if current == "local_onnx" else 1
        self._backend_combo.setCurrentIndex(idx)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        self._row(layout, "AI Backend:", self._backend_combo)

        self._target_combo = QComboBox()
        self._target_combo.addItem("Development (this machine)", "development")
        self._target_combo.addItem("Snapdragon PC (target)", "snapdragon_pc")
        current_target = self._settings.get("target_device", "development")
        self._target_combo.setCurrentIndex(0 if current_target == "development" else 1)
        self._target_combo.currentIndexChanged.connect(
            lambda i: self._save("target_device", self._target_combo.currentData())
        )
        self._row(layout, "Target Device:", self._target_combo)

        note = QLabel(
            "⚠ Qualcomm AI Runtime requires: Snapdragon PC + QNN SDK + qai-hub package.\n"
            "See docs/QUALCOMM_AI_HUB.md for setup instructions."
        )
        note.setObjectName("card_sub")
        note.setWordWrap(True)
        layout.addWidget(note)

        return card

    def _build_sensitive_content_section(self) -> QFrame:
        card, layout = self._section_card("SENSITIVE CONTENT DETECTION  (Experimental)")

        self._sens_cb = QCheckBox("Enable sensitive content detection")
        self._sens_cb.setChecked(self._settings.get("sensitive_content_detection", False))
        self._sens_cb.toggled.connect(lambda v: self._save("sensitive_content_detection", v))
        layout.addWidget(self._sens_cb)

        note = QLabel(
            "⚠ Experimental feature. Requires Tesseract OCR installed separately.\n"
            "Analyzes camera frames in-memory for patterns such as credit card numbers,\n"
            "email addresses, passwords, and ID-like documents.\n"
            "Frames are NOT saved to disk by this feature."
        )
        note.setObjectName("card_sub")
        note.setWordWrap(True)
        layout.addWidget(note)

        return card

    def _build_actions_section(self) -> QFrame:
        card, layout = self._section_card("ACTIONS")

        btn_row = QHBoxLayout()

        reset_btn = QPushButton("↺  Reset to Defaults")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return card

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save(self, key: str, value):
        self._settings.set(key, value)

    def _on_backend_changed(self, index: int):
        value = self._backend_combo.currentData()
        self._save("ai_backend", value)
        if value == "qualcomm":
            from app.inference.qualcomm_backend import QualcommBackend
            qb = QualcommBackend()
            if not qb.is_available():
                QMessageBox.warning(
                    self, "Qualcomm Backend Unavailable",
                    "Qualcomm AI Runtime is not available on this machine.\n\n"
                    "Requirements:\n"
                    "• Windows PC with Snapdragon processor\n"
                    "• Qualcomm AI Hub SDK (pip install qai-hub)\n"
                    "• QNN Runtime libraries\n\n"
                    "See docs/QUALCOMM_AI_HUB.md for full setup instructions.\n\n"
                    "The application will fall back to Local ONNX for now."
                )

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._settings.reset_to_defaults()
            # Reload widgets
            self._cam_idx.setValue(DEFAULT_SETTINGS["camera_index"])
            self._cam_w.setValue(DEFAULT_SETTINGS["camera_resolution_w"])
            self._cam_h.setValue(DEFAULT_SETTINGS["camera_resolution_h"])
            self._cam_fps.setValue(DEFAULT_SETTINGS["camera_fps_target"])
            self._conf_thresh.setValue(DEFAULT_SETTINGS["confidence_threshold"])
            self._iou_thresh.setValue(DEFAULT_SETTINGS["iou_threshold"])
            self._warn_delay.setValue(DEFAULT_SETTINGS["risk_warning_delay_frames"])
            self._cooldown.setValue(DEFAULT_SETTINGS["risk_cooldown_frames"])
            self._shoulder_prox.setValue(DEFAULT_SETTINGS["shoulder_surf_proximity"])
            self._backend_combo.setCurrentIndex(0)
            self._target_combo.setCurrentIndex(0)
            self._sens_cb.setChecked(False)

    def on_page_activated(self):
        pass
