"""
Dashboard page for SnapGuard AI — Ultra Command Center v3.0
Features live animated spatial radar sweep, real-time threat matrix LED gauge,
neural pipeline telemetry, and high-tech defense HUD.
"""

import math
import logging
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QConicalGradient,
    QRadialGradient, QFont,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea, QGridLayout,
)

from app.config import RiskLevel, APP_NAME, get_settings
from app.utils.system_info import get_system_info, get_current_metrics
from app.privacy.privacy_mode import get_privacy_manager, PrivacyModeState

log = logging.getLogger("SnapGuard AI")


# ─────────────────────────────────────────────────────────────────────────────
# Custom Widget: Live Spatial Radar & Sonar Scanner
# ─────────────────────────────────────────────────────────────────────────────

class RadarScannerWidget(QWidget):
    """
    Animated circular radar sweep showing spatial detection field of view,
    primary user sweet-spot, and detected onlooker blips in real time.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(230, 230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._settings = get_settings()
        self._angle = 0
        self._people_count = 0
        self._risk_level = RiskLevel.UNKNOWN
        self._pulse = 0.0
        self._pulse_dir = 0.06

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 FPS rotation

    def _tick(self):
        self._angle = (self._angle + 4) % 360
        self._pulse += self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -0.06
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 0.06
        self.update()

    def set_telemetry(self, count: int, risk: str):
        self._people_count = count
        self._risk_level = risk
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        radius = min(cx, cy) - 14.0
        if radius <= 15:
            return

        is_light = self._settings.get("theme", "light") == "light"
        is_threat = self._risk_level == RiskLevel.HIGH

        # Dynamic color theme selection
        if is_light:
            bg_color = QColor(255, 255, 255, 240)
            rim_color = QColor(220, 38, 38) if is_threat else QColor(2, 132, 199)
            grid_color = QColor(2, 132, 199, 45)
            sweep_rgb = (220, 38, 38) if is_threat else (2, 132, 199)
            user_color = QColor(5, 150, 105)
            threat_color = QColor(220, 38, 38)
            text_color = QColor(71, 85, 105)
        else:
            bg_color = QColor(7, 13, 31, 240)
            rim_color = QColor(255, 77, 109) if is_threat else QColor(0, 212, 255)
            grid_color = QColor(0, 212, 255, 40)
            sweep_rgb = (255, 77, 109) if is_threat else (0, 212, 255)
            user_color = QColor(0, 255, 136)
            threat_color = QColor(255, 77, 109)
            text_color = QColor(0, 212, 255)

        # 1. Base radar circle background
        painter.setBrush(QBrush(bg_color))
        rim_pen = QPen(rim_color, 2.5 if is_threat else 1.5)
        painter.setPen(rim_pen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Concentric range rings
        grid_pen = QPen(grid_color, 1, Qt.DashLine)
        painter.setPen(grid_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.35, radius * 0.35)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.70, radius * 0.70)

        # 3. Crosshair & Angle Guides
        cross_pen = QPen(grid_color, 1)
        painter.setPen(cross_pen)
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        # 4. Sweep Sector using Conical Gradient
        sweep_grad = QConicalGradient(cx, cy, -float(self._angle))
        r, g, b = sweep_rgb
        sweep_grad.setColorAt(0.0, QColor(r, g, b, 110))
        sweep_grad.setColorAt(0.15, QColor(r, g, b, 0))
        sweep_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(sweep_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 5. Sweep Beam Line
        rad = math.radians(self._angle)
        bx = cx + radius * math.cos(rad)
        by = cy - radius * math.sin(rad)
        beam_pen = QPen(QColor(r, g, b, 230), 2)
        painter.setPen(beam_pen)
        painter.drawLine(int(cx), int(cy), int(bx), int(by))

        # 6. Target Plotting: Primary User (Center/Front)
        if self._people_count >= 1:
            uy = cy + radius * 0.38
            # Pulsing radar aura
            aura = 8 + self._pulse * 6
            painter.setBrush(QColor(user_color.red(), user_color.green(), user_color.blue(), int(60 * (1.0 - self._pulse))))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, uy), aura, aura)
            # Solid core
            painter.setBrush(user_color)
            painter.drawEllipse(QPointF(cx, uy), 4.5, 4.5)

        # 7. Target Plotting: Secondary / Onlookers (Threat blips)
        if self._people_count >= 2:
            tx = cx + radius * 0.48
            ty = cy - radius * 0.32
            # Pulsing warning ring
            t_aura = 10 + self._pulse * 7
            painter.setBrush(QColor(threat_color.red(), threat_color.green(), threat_color.blue(), int(90 * (1.0 - self._pulse))))
            painter.drawEllipse(QPointF(tx, ty), t_aura, t_aura)
            painter.setBrush(threat_color)
            painter.drawEllipse(QPointF(tx, ty), 5.0, 5.0)

        if self._people_count >= 3:
            tx2 = cx - radius * 0.45
            ty2 = cy - radius * 0.36
            painter.setBrush(threat_color)
            painter.drawEllipse(QPointF(tx2, ty2), 5.0, 5.0)

        # 8. Outer Pulsing Shield on High Risk
        if is_threat:
            pulse_radius = radius + 2 + self._pulse * 5
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(220, 38, 38, int(120 * (1.0 - self._pulse))), 2))
            painter.drawEllipse(QPointF(cx, cy), pulse_radius, pulse_radius)

        # 9. Top / Bottom HUD overlays
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(QRectF(14, 10, w - 28, 16), Qt.AlignLeft, "RADAR: FOV 78°")
        painter.drawText(QRectF(14, 10, w - 28, 16), Qt.AlignRight, f"PEOPLE: {self._people_count}")

        status_msg = "AIRSPACE SECURE" if not is_threat else "⚠ THREAT LOCKED"
        painter.setPen(QColor(220, 38, 38) if is_threat else text_color)
        painter.drawText(QRectF(14, h - 22, w - 28, 16), Qt.AlignCenter, status_msg)


# ─────────────────────────────────────────────────────────────────────────────
# Custom Widget: Segmented LED Threat Matrix Gauge
# ─────────────────────────────────────────────────────────────────────────────

class ThreatMatrixGauge(QWidget):
    """
    Segmented 5-level LED status meter showing escalating threat level.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._level = 1  # 1 to 5
        self._labels = ["1: SECURE", "2: MONITORED", "3: CAUTION", "4: ELEVATED", "5: BREACH"]

    def set_risk(self, risk: str):
        mapping = {
            RiskLevel.SAFE: 1,
            RiskLevel.LOW: 2,
            RiskLevel.UNKNOWN: 2,
            RiskLevel.MEDIUM: 3,
            RiskLevel.HIGH: 5,
        }
        self._level = mapping.get(risk, 1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self._labels)
        gap = 6
        seg_w = (w - (n - 1) * gap) / float(n)

        # Level colors
        level_colors = [
            QColor(16, 185, 129),   # Level 1: Green
            QColor(2, 132, 199),    # Level 2: Blue/Cyan
            QColor(245, 158, 11),   # Level 3: Amber
            QColor(249, 115, 22),   # Level 4: Orange
            QColor(239, 68, 68),    # Level 5: Red
        ]

        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        for i in range(n):
            x = i * (seg_w + gap)
            rect = QRectF(x, 2, seg_w, h - 4)
            is_active = (i + 1) <= self._level
            col = level_colors[i]

            if is_active:
                painter.setBrush(QColor(col.red(), col.green(), col.blue(), 230))
                painter.setPen(QPen(col.darker(110), 1.5))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QColor(255, 255, 255))
            else:
                painter.setBrush(QColor(col.red(), col.green(), col.blue(), 25))
                painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 60), 1))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QColor(148, 163, 184, 120))

            painter.drawText(rect, Qt.AlignCenter, self._labels[i])


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Page Main Window
# ─────────────────────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    """
    Futuristic Command Center Dashboard.
    Combines live spatial radar, threat matrix, neural dataflow telemetry,
    and instantaneous privacy defense controls.
    """

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window  = main_window
        self._settings     = get_settings()
        self._sys_info     = get_system_info()
        self._privacy_mgr  = get_privacy_manager()
        self._online_cache = False

        self._setup_ui()
        self._start_refresh_timers()
        self._check_network_async()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Smooth Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(15,23,42,0.1); width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #94A3B8; border-radius: 4px; min-height: 24px; }"
            "QScrollBar::handle:vertical:hover { background: #0284C7; }"
        )

        content = QWidget()
        content.setObjectName("content_area")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(36, 26, 36, 36)
        self._layout.setSpacing(20)

        # ── Header Command Banner ───────────────────────────────────
        self._layout.addWidget(self._build_header_row())

        # ── Hero Section: Radar + Defense Matrix HUD ────────────────
        self._layout.addWidget(self._build_hero_hud())

        # ── Pipeline Architecture HUD ───────────────────────────────
        self._layout.addWidget(self._build_pipeline_matrix())

        # ── Real-Time Telemetry Grid ────────────────────────────────
        self._layout.addWidget(self._build_vitals_grid())

        # ── Tactical Quick Launchpad ────────────────────────────────
        self._layout.addWidget(self._build_action_deck())

        self._layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Section 1: Header Row
    # ------------------------------------------------------------------

    def _build_header_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        vbox = QVBoxLayout()
        vbox.setSpacing(2)

        title = QLabel("DEFENSE COMMAND CENTER")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 22px; font-weight: 900; letter-spacing: 0.8px;")
        vbox.addWidget(title)

        sub = QLabel("Autonomous On-Device AI Visual Privacy Shield — Real-Time Spatial Telemetry")
        sub.setObjectName("page_subtitle")
        vbox.addWidget(sub)
        layout.addLayout(vbox)

        layout.addStretch()

        # High-tech live pulsing indicator
        pill_box = QFrame()
        pill_box.setStyleSheet(
            "background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10B981; "
            "border-radius: 20px; padding: 6px 16px;"
        )
        pill_layout = QHBoxLayout(pill_box)
        pill_layout.setContentsMargins(0, 0, 0, 0)
        pill_layout.setSpacing(8)

        self._dot_indicator = QLabel("●")
        self._dot_indicator.setStyleSheet("color: #10B981; font-size: 14px;")
        pill_layout.addWidget(self._dot_indicator)

        self._clock_label = QLabel("DEFENSE MATRIX ACTIVE")
        self._clock_label.setStyleSheet("color: #059669; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        pill_layout.addWidget(self._clock_label)

        layout.addWidget(pill_box)
        return row

    # ------------------------------------------------------------------
    # Section 2: Hero HUD (Radar Scanner + Threat Vector Matrix)
    # ------------------------------------------------------------------

    def _build_hero_hud(self) -> QWidget:
        container = QFrame()
        container.setObjectName("card")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(24)

        # Left: Live Radar Canvas
        radar_box = QVBoxLayout()
        radar_box.setSpacing(10)
        radar_box.setAlignment(Qt.AlignCenter)

        radar_title = QLabel("SPATIAL AIRSPACE SCANNER")
        radar_title.setObjectName("section_header")
        radar_title.setAlignment(Qt.AlignCenter)
        radar_box.addWidget(radar_title)

        self._radar = RadarScannerWidget()
        radar_box.addWidget(self._radar)

        radar_sub = QLabel("78° Ultra-Wide Optical Angle • 3.5m Proximity Zone")
        radar_sub.setObjectName("description_label")
        radar_sub.setAlignment(Qt.AlignCenter)
        radar_box.addWidget(radar_sub)

        layout.addLayout(radar_box, stretch=2)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(148, 163, 184, 0.3);")
        layout.addWidget(sep)

        # Right: Defense Status & Threat Vectors
        hud_box = QVBoxLayout()
        hud_box.setSpacing(14)

        hud_hdr = QLabel("THREAT VECTOR & DEFENSE MATRIX")
        hud_hdr.setObjectName("section_header")
        hud_box.addWidget(hud_hdr)

        # Status Hero Banner
        self._status_banner = QLabel("🟢  DEFENSE SHIELD: ARMED & ACTIVE")
        self._status_banner.setAlignment(Qt.AlignCenter)
        self._status_banner.setStyleSheet(
            "font-size: 17px; font-weight: 800; padding: 14px; border-radius: 10px; "
            "background: rgba(16, 185, 129, 0.12); color: #059669; border: 1.5px solid #10B981;"
        )
        hud_box.addWidget(self._status_banner)

        # LED Threat Gauge
        self._threat_gauge = ThreatMatrixGauge()
        hud_box.addWidget(self._threat_gauge)

        # 4-Pod Matrix Metrics
        grid = QGridLayout()
        grid.setSpacing(10)

        def make_pod(title: str, val: str, col: str):
            f = QFrame()
            f.setStyleSheet(
                "background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.25); "
                "border-radius: 8px; padding: 8px 12px;"
            )
            vb = QVBoxLayout(f)
            vb.setContentsMargins(0, 0, 0, 0)
            vb.setSpacing(3)
            t = QLabel(title.upper())
            t.setStyleSheet("font-size: 9px; font-weight: 700; color: #64748B; letter-spacing: 1px;")
            vb.addWidget(t)
            v = QLabel(val)
            v.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {col};")
            vb.addWidget(v)
            return f, v

        pod1, self._pod_people  = make_pod("People In Zone", "0", "#0284C7")
        pod2, self._pod_risk    = make_pod("Threat Level", "SECURE", "#059669")
        pod3, self._pod_fps     = make_pod("AI Frame Rate", "— FPS", "#0284C7")
        pod4, self._pod_latency = make_pod("Inference Latency", "— ms", "#D97706")

        grid.addWidget(pod1, 0, 0)
        grid.addWidget(pod2, 0, 1)
        grid.addWidget(pod3, 1, 0)
        grid.addWidget(pod4, 1, 1)

        hud_box.addLayout(grid)
        layout.addLayout(hud_box, stretch=3)

        return container

    # ------------------------------------------------------------------
    # Section 3: Hardware Neural Pipeline Architecture
    # ------------------------------------------------------------------

    def _build_pipeline_matrix(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        hdr = QLabel("ON-DEVICE NEURAL PROCESSING PIPELINE")
        hdr.setObjectName("section_header")
        layout.addWidget(hdr)

        pipeline_row = QHBoxLayout()
        pipeline_row.setSpacing(8)

        def node(icon_title: str, sub: str, accent: str):
            box = QFrame()
            box.setStyleSheet(
                f"background: rgba(148, 163, 184, 0.08); border: 1.5px solid {accent}; "
                "border-radius: 8px; padding: 10px 14px;"
            )
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(3)
            v.setAlignment(Qt.AlignCenter)
            t = QLabel(icon_title)
            t.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {accent};")
            v.addWidget(t)
            s = QLabel(sub)
            s.setStyleSheet("font-size: 10px; color: #64748B;")
            v.addWidget(s)
            return box

        arrow_style = "font-size: 16px; font-weight: 900; color: #94A3B8;"

        n1 = node("📷 Camera Stream", "640x480 @ 30 FPS", "#0284C7")
        arr1 = QLabel("➔"); arr1.setStyleSheet(arrow_style)
        n2 = node("⚡ Hexagon NPU", "INT8 Tensor Acceleration", "#059669")
        arr2 = QLabel("➔"); arr2.setStyleSheet(arrow_style)
        n3 = node("🧠 YOLOv8 Weights", "Person Detection Engine", "#7C3AED")
        arr3 = QLabel("➔"); arr3.setStyleSheet(arrow_style)
        n4 = node("🛡 Temporal Shield", "Proximity & Defense", "#D97706")

        pipeline_row.addWidget(n1, 1)
        pipeline_row.addWidget(arr1)
        pipeline_row.addWidget(n2, 1)
        pipeline_row.addWidget(arr2)
        pipeline_row.addWidget(n3, 1)
        pipeline_row.addWidget(arr3)
        pipeline_row.addWidget(n4, 1)

        layout.addLayout(pipeline_row)
        return card

    # ------------------------------------------------------------------
    # Section 4: Telemetry & Vitals Grid
    # ------------------------------------------------------------------

    def _build_vitals_grid(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        def vitals_card(title: str, val_init: str, sub_init: str, color: str):
            c = QFrame()
            c.setObjectName("card")
            l = QVBoxLayout(c)
            l.setContentsMargins(18, 16, 18, 16)
            l.setSpacing(4)
            t = QLabel(title.upper())
            t.setObjectName("card_title")
            l.addWidget(t)
            v = QLabel(val_init)
            v.setObjectName("card_value")
            v.setStyleSheet(f"color: {color}; font-size: 24px;")
            l.addWidget(v)
            s = QLabel(sub_init)
            s.setObjectName("card_sub")
            l.addWidget(s)
            return c, v, s

        c1, self._cpu_val, self._cpu_sub = vitals_card("Host CPU Load", "—%", "Processor utilization", "#0284C7")
        c2, self._ram_val, self._ram_sub = vitals_card("Memory Footprint", "— MB", "On-device allocation", "#059669")
        c3, self._net_val, self._net_sub = vitals_card("Zero-Cloud Privacy", "AIR-GAPPED", "0 KB transmitted (offline)", "#059669")
        c4, self._mode_val, self._mode_sub = vitals_card("Execution Mode", self._sys_info.mode_label, "Qualcomm / CPU runtime", "#D97706")

        layout.addWidget(c1)
        layout.addWidget(c2)
        layout.addWidget(c3)
        layout.addWidget(c4)
        return container

    # ------------------------------------------------------------------
    # Section 5: Tactical Action Deck
    # ------------------------------------------------------------------

    def _build_action_deck(self) -> QWidget:
        container = QFrame()
        container.setObjectName("card")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        lbl = QLabel("TACTICAL ACTIONS:")
        lbl.setStyleSheet("font-weight: 800; font-size: 11px; color: #64748B; letter-spacing: 1px;")
        layout.addWidget(lbl)

        btn_live = QPushButton("📷  Live Vision Cockpit")
        btn_live.setObjectName("btn_primary")
        btn_live.setCursor(Qt.PointingHandCursor)
        btn_live.setMinimumHeight(38)
        btn_live.clicked.connect(lambda: self._navigate("live_protection"))
        layout.addWidget(btn_live)

        btn_pm = QPushButton("🛡  Privacy Shield Matrix")
        btn_pm.setObjectName("btn_blue")
        btn_pm.setCursor(Qt.PointingHandCursor)
        btn_pm.setMinimumHeight(38)
        btn_pm.clicked.connect(lambda: self._navigate("privacy_mode"))
        layout.addWidget(btn_pm)

        btn_bench = QPushButton("⚡  Run Hardware Benchmark")
        btn_bench.setCursor(Qt.PointingHandCursor)
        btn_bench.setMinimumHeight(38)
        btn_bench.clicked.connect(lambda: self._navigate("performance"))
        layout.addWidget(btn_bench)

        btn_sim = QPushButton("🚨  Simulate Threat Breach")
        btn_sim.setObjectName("btn_danger")
        btn_sim.setCursor(Qt.PointingHandCursor)
        btn_sim.setMinimumHeight(38)
        btn_sim.clicked.connect(self._simulate_threat)
        layout.addWidget(btn_sim)

        layout.addStretch()
        return container

    # ------------------------------------------------------------------
    # Telemetry Timers & Handlers
    # ------------------------------------------------------------------

    def _start_refresh_timers(self):
        self._vitals_timer = QTimer(self)
        self._vitals_timer.timeout.connect(self._refresh_system_vitals)
        self._vitals_timer.start(1500)

    def _check_network_async(self):
        import socket
        def _check():
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=1)
                self._online_cache = True
            except OSError:
                self._online_cache = False
        threading.Thread(target=_check, daemon=True).start()

    def _refresh_system_vitals(self):
        try:
            m = get_current_metrics()
            cpu = m["cpu_percent"]
            ram_used = m["ram_used_mb"]
            ram_pct = m["ram_percent"]

            cpu_color = "#059669" if cpu < 50 else "#D97706" if cpu < 80 else "#DC2626"
            self._cpu_val.setText(f"{cpu:.0f}%")
            self._cpu_val.setStyleSheet(f"color: {cpu_color}; font-size: 24px;")

            self._ram_val.setText(f"{ram_used:.0f} MB")
            self._ram_sub.setText(f"{ram_pct:.0f}% of {self._sys_info.ram_total_gb:.1f} GB allocated")

            # Check privacy mode state to update hero banner
            pm_state = self._privacy_mgr.state
            if pm_state == PrivacyModeState.PROTECTION_ACTIVE:
                self._status_banner.setText("🚨  PRIVACY BREACH: THREAT PROTECTION ACTIVE")
                self._status_banner.setStyleSheet(
                    "font-size: 17px; font-weight: 800; padding: 14px; border-radius: 10px; "
                    "background: rgba(239, 68, 68, 0.15); color: #DC2626; border: 1.5px solid #EF4444;"
                )
            elif pm_state == PrivacyModeState.MONITORING:
                self._status_banner.setText("🟢  DEFENSE SHIELD: ARMED & PATROLLING")
                self._status_banner.setStyleSheet(
                    "font-size: 17px; font-weight: 800; padding: 14px; border-radius: 10px; "
                    "background: rgba(16, 185, 129, 0.12); color: #059669; border: 1.5px solid #10B981;"
                )
            else:
                self._status_banner.setText("⚪  DEFENSE SHIELD: STANDBY / DISABLED")
                self._status_banner.setStyleSheet(
                    "font-size: 17px; font-weight: 800; padding: 14px; border-radius: 10px; "
                    "background: rgba(148, 163, 184, 0.1); color: #64748B; border: 1.5px solid #CBD5E1;"
                )

        except Exception as e:
            log.debug(f"[DashboardPage] vitals error: {e}")

    # ------------------------------------------------------------------
    # Live Data Push from Camera / Inference Worker
    # ------------------------------------------------------------------

    def update_live_stats(self, assessment, fps: float, latency_ms: float, model_loaded: bool):
        try:
            risk = assessment.risk_level if assessment else RiskLevel.UNKNOWN
            count = assessment.people_count if assessment else 0

            # Update live spatial radar
            self._radar.set_telemetry(count, risk)

            # Update LED Threat Gauge
            self._threat_gauge.set_risk(risk)

            # Update HUD Pods
            self._pod_people.setText(str(count) if count >= 0 else "0")
            self._pod_people.setStyleSheet(
                "font-size: 18px; font-weight: 800; color: #059669;" if count <= 1 else "font-size: 18px; font-weight: 800; color: #DC2626;"
            )

            risk_colors = {
                RiskLevel.SAFE:    ("#059669", "SECURE"),
                RiskLevel.LOW:     ("#64748B", "LOW RISK"),
                RiskLevel.MEDIUM:  ("#D97706", "ELEVATED"),
                RiskLevel.HIGH:    ("#DC2626", "CRITICAL"),
                RiskLevel.UNKNOWN: ("#64748B", "STARTING"),
            }
            col, label = risk_colors.get(risk, ("#64748B", "UNKNOWN"))
            self._pod_risk.setText(label)
            self._pod_risk.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {col};")

            if fps > 0:
                self._pod_fps.setText(f"{fps:.1f} FPS")
            if latency_ms > 0:
                self._pod_latency.setText(f"{latency_ms:.0f} ms")

        except Exception as e:
            log.debug(f"[DashboardPage] update error: {e}")

    # ------------------------------------------------------------------
    # Tactical Actions
    # ------------------------------------------------------------------

    def _navigate(self, page_id: str):
        if self._main_window:
            self._main_window.navigate(page_id)

    def _simulate_threat(self):
        try:
            self._privacy_mgr.simulate_test_alert()
        except Exception as e:
            log.error(f"[DashboardPage] Threat simulation error: {e}")

    def on_page_activated(self):
        self._refresh_system_vitals()
