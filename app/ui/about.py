"""
About page for SnapGuard AI.
Shows app info, privacy statement, Qualcomm AI Hub info, and system details.
"""

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)

from app.config import APP_NAME, APP_VERSION, APP_TAGLINE, APP_AUTHOR, COMPETITION
from app.utils.system_info import get_system_info

log = logging.getLogger("SnapGuard AI")


class AboutPage(QWidget):

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._sys_info    = get_system_info()
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(0)

        title = QLabel("About")
        title.setObjectName("page_title")
        outer.addWidget(title)
        sub = QLabel("SnapGuard AI — On-Device Privacy Protection")
        sub.setObjectName("page_subtitle")
        outer.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_app_card())
        layout.addWidget(self._build_privacy_card())
        layout.addWidget(self._build_qualcomm_card())
        layout.addWidget(self._build_system_card())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _section_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        hdr = QLabel(title)
        hdr.setObjectName("section_header")
        layout.addWidget(hdr)
        return card, layout

    def _build_app_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        name = QLabel(f"🛡  {APP_NAME}")
        name.setStyleSheet("font-size:24px; font-weight:700; color:#58A6FF;")
        layout.addWidget(name)

        tagline = QLabel(f'"{APP_TAGLINE}"')
        tagline.setStyleSheet("font-size:14px; color:#8B949E; font-style:italic;")
        layout.addWidget(tagline)

        layout.addSpacing(4)

        for label, value in [
            ("Version", APP_VERSION),
            ("Author",  APP_AUTHOR),
            ("Competition", COMPETITION),
            ("License", "MIT"),
        ]:
            row = QHBoxLayout()
            key_lbl = QLabel(f"{label}:")
            key_lbl.setFixedWidth(100)
            key_lbl.setObjectName("card_title")
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet("color:#E6EDF3;")
            row.addWidget(key_lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            layout.addLayout(row)

        return card

    def _build_privacy_card(self) -> QFrame:
        card, layout = self._section_card("🔒  PRIVACY STATEMENT")

        statements = [
            ("Camera Processing", "All camera frames are processed locally on your device."),
            ("No Upload", "Camera frames are never uploaded to any server or cloud service."),
            ("No Storage", "Camera frames are not saved to disk by default."),
            ("Local AI", "AI inference runs entirely on-device using ONNX Runtime."),
            ("Settings", "Only configuration settings and benchmark results are stored locally (SQLite)."),
            ("Camera Control", "You can stop the camera at any time. A clear indicator shows when the camera is active."),
            ("Sensitive Content", "The optional sensitive content detector processes frames in-memory only."),
        ]

        for label, desc in statements:
            row = QHBoxLayout()
            row.setSpacing(12)
            icon = QLabel("✓")
            icon.setFixedWidth(20)
            icon.setStyleSheet("color:#3FB950; font-weight:700; font-size:14px;")
            key = QLabel(f"{label}:")
            key.setFixedWidth(160)
            key.setStyleSheet("color:#8B949E; font-size:12px;")
            val = QLabel(desc)
            val.setObjectName("description_label")
            val.setWordWrap(True)
            row.addWidget(icon)
            row.addWidget(key)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        note = QLabel(
            "\nNote: SnapGuard processes camera data locally whenever supported. "
            "Camera frames are not uploaded by the application. "
            "Accuracy of sensitive content detection may vary based on image quality."
        )
        note.setObjectName("card_sub")
        note.setWordWrap(True)
        layout.addWidget(note)

        return card

    def _build_qualcomm_card(self) -> QFrame:
        card, layout = self._section_card("⚡  QUALCOMM AI HUB INTEGRATION")

        intro = QLabel(
            "SnapGuard AI is designed for the Snapdragon AI Lab Build & Present Challenge. "
            "The architecture supports Qualcomm AI Hub model optimization for deployment on "
            "Snapdragon-powered Windows PCs with Hexagon NPU acceleration."
        )
        intro.setObjectName("description_label")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        si = self._sys_info
        for label, value, color in [
            ("Qualcomm AI Hub",  "Installed" if si.qai_hub_available  else "Not installed", "#3FB950" if si.qai_hub_available  else "#8B949E"),
            ("Snapdragon NPU",   si.qualcomm_npu_name if si.qualcomm_npu_available else "Not detected", "#3FB950" if si.qualcomm_npu_available else "#8B949E"),
            ("Current Mode",     si.mode_label, "#3FB950" if not si.is_development_mode else "#E3B341"),
        ]:
            row = QHBoxLayout()
            key = QLabel(f"{label}:")
            key.setFixedWidth(160)
            key.setStyleSheet("color:#8B949E;")
            val = QLabel(value)
            val.setStyleSheet(f"color:{color}; font-weight:600;")
            row.addWidget(key)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)

        guide_btn = QPushButton("📄  View Qualcomm AI Hub Setup Guide")
        guide_btn.setCursor(Qt.PointingHandCursor)
        guide_btn.clicked.connect(self._open_qualcomm_guide)
        layout.addWidget(guide_btn)

        return card

    def _build_system_card(self) -> QFrame:
        card, layout = self._section_card("💻  SYSTEM INFORMATION")

        si = self._sys_info
        rows = [
            ("OS",             f"{si.os_name}"),
            ("CPU",            si.cpu_name),
            ("CPU Cores",      f"{si.cpu_cores_physical} physical / {si.cpu_cores_logical} logical"),
            ("RAM",            f"{si.ram_total_gb:.1f} GB"),
            ("Python",         si.python_version),
            ("PySide6",        si.pyside6_version if si.pyside6_available else "Not found"),
            ("OpenCV",         si.opencv_version  if si.opencv_available  else "Not found"),
            ("ONNX Runtime",   si.onnxruntime_version if si.onnxruntime_available else "Not installed"),
            ("Qualcomm AI Hub",si.qai_hub_version  if si.qai_hub_available  else "Not installed"),
        ]

        for label, value in rows:
            row = QHBoxLayout()
            key = QLabel(f"{label}:")
            key.setFixedWidth(160)
            key.setStyleSheet("color:#8B949E; font-size:12px;")
            val = QLabel(value)
            val.setStyleSheet("color:#E6EDF3; font-size:12px;")
            val.setWordWrap(True)
            row.addWidget(key)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        return card

    def _open_qualcomm_guide(self):
        from app.config import DOCS_DIR
        guide_path = DOCS_DIR / "QUALCOMM_AI_HUB.md"
        import subprocess, sys
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(guide_path)])
            elif sys.platform == "win32":
                subprocess.run(["start", str(guide_path)], shell=True)
            else:
                subprocess.run(["xdg-open", str(guide_path)])
        except Exception as e:
            log.warning(f"Could not open guide: {e}")

    def on_page_activated(self):
        pass
