"""
Main Window for SnapGuard AI.
Sidebar navigation shell that hosts all pages.
"""

import logging
import socket
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor, QPainter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QStatusBar, QFrame,
    QSizePolicy,
)

from app.config import APP_NAME, APP_VERSION, APP_TAGLINE, ASSETS_DIR, get_settings
from app.utils.system_info import get_system_info

log = logging.getLogger("SnapGuard AI")

NAV_ITEMS = [
    ("dashboard",       "  Dashboard"),
    ("live_protection", "  Live Protection"),
    ("privacy_mode",    "  Privacy Mode"),
    ("performance",     "  Performance"),
    ("settings",        "  Settings"),
    ("about",           "  About"),
]


class MainWindow(QMainWindow):
    """Primary application window with sidebar navigation."""

    def __init__(self):
        super().__init__()
        self._settings  = get_settings()
        self._sys_info  = get_system_info()
        self._pages     = {}
        self._nav_btns  = {}
        self._active_page = "dashboard"
        self._online_cache = False   # cached network status (updated in background)

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._start_status_timer()
        self._start_network_checker()

        # Navigate to dashboard
        self.navigate("dashboard")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        # Center on screen
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_content(), stretch=1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_status_bar()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("🛡  SnapGuard AI")
        logo.setObjectName("sidebar_logo_label")
        logo.setWordWrap(True)
        layout.addWidget(logo)

        tagline = QLabel("Your laptop. Your data. Your privacy.")
        tagline.setObjectName("sidebar_tagline")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(0,212,255,0.12); margin: 0 16px;")
        layout.addWidget(sep)
        layout.addSpacing(6)

        # Nav buttons
        for page_id, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, pid=page_id: self.navigate(pid))
            layout.addWidget(btn)
            self._nav_btns[page_id] = btn

        layout.addStretch()

        # Mode badge
        self._mode_label = QLabel()
        self._mode_label.setObjectName("mode_banner")
        self._mode_label.setWordWrap(True)
        self._mode_label.setAlignment(Qt.AlignCenter)
        self._update_mode_label()
        layout.addWidget(self._mode_label)

        return sidebar

    def _build_content(self) -> QWidget:
        container = QWidget()
        container.setObjectName("content_area")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Demo banner
        self._demo_banner = QLabel("⚠  DEMO MODE — Camera feed is simulated")
        self._demo_banner.setObjectName("demo_banner")
        self._demo_banner.setAlignment(Qt.AlignCenter)
        self._demo_banner.setVisible(self._settings.get("demo_mode", False))
        layout.addWidget(self._demo_banner)

        # Page stack
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Lazy-import pages to avoid circular deps
        self._load_pages()

        return container

    def _load_pages(self):
        from app.ui.dashboard       import DashboardPage
        from app.ui.live_protection import LiveProtectionPage
        from app.ui.privacy_mode    import PrivacyModePage
        from app.ui.performance     import PerformancePage
        from app.ui.settings        import SettingsPage
        from app.ui.about           import AboutPage

        page_classes = {
            "dashboard":       DashboardPage,
            "live_protection": LiveProtectionPage,
            "privacy_mode":    PrivacyModePage,
            "performance":     PerformancePage,
            "settings":        SettingsPage,
            "about":           AboutPage,
        }

        for page_id, cls in page_classes.items():
            try:
                page = cls(main_window=self)
                self._pages[page_id] = page
                self._stack.addWidget(page)
            except Exception as e:
                log.error(f"Failed to load page '{page_id}': {e}")
                # Placeholder page
                placeholder = QLabel(f"⚠ Page '{page_id}' failed to load:\n{e}")
                placeholder.setAlignment(Qt.AlignCenter)
                self._pages[page_id] = placeholder
                self._stack.addWidget(placeholder)

    def _connect_signals(self):
        try:
            from app.privacy.privacy_mode import get_privacy_manager
            pm = get_privacy_manager()
            pm.alert_triggered.connect(self._on_privacy_alert_triggered)
        except Exception as e:
            log.error(f"[MainWindow] Signal connect error: {e}")

    def _on_privacy_alert_triggered(self, reason: str):
        # 1. Play audible sound
        if self._settings.get("privacy_audio_alert", True):
            self._play_alert_sound()

        # 2. Direct open privacy page
        if self._settings.get("privacy_auto_open_page", True):
            log.info(f"Privacy threat detected ({reason}) — navigating directly to Privacy Mode.")
            self.navigate("privacy_mode")

    def _play_alert_sound(self):
        try:
            import platform, subprocess
            if platform.system() == "Darwin":
                subprocess.Popen(["afplay", "/System/Library/Sounds/Ping.aiff"], stderr=subprocess.DEVNULL)
            else:
                from PySide6.QtWidgets import QApplication
                QApplication.beep()
        except Exception:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()

    def apply_theme(self, theme_name: str):
        from PySide6.QtWidgets import QApplication
        qss_file = "light_theme.qss" if theme_name == "light" else "dark_theme.qss"
        qss_path = ASSETS_DIR / "styles" / qss_file
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(f.read())
            self._settings.set("theme", theme_name)
            log.info(f"Switched theme to {theme_name}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, page_id: str):
        if page_id not in self._pages:
            log.warning(f"Unknown page: {page_id}")
            return

        # Update nav button styles
        # Qt QSS requires string "true"/"false", not Python booleans
        for pid, btn in self._nav_btns.items():
            btn.setProperty("active", "true" if pid == page_id else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._stack.setCurrentWidget(self._pages[page_id])
        self._active_page = page_id

        # Notify page it became active
        page = self._pages.get(page_id)
        if hasattr(page, "on_page_activated"):
            page.on_page_activated()

    def get_page(self, page_id: str):
        return self._pages.get(page_id)

    # ------------------------------------------------------------------
    # Status bar + timer
    # ------------------------------------------------------------------

    def _start_status_timer(self):
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(2000)

    def _start_network_checker(self):
        """Check network status in a background thread every 10s to avoid blocking UI."""
        self._net_timer = QTimer(self)
        self._net_timer.timeout.connect(self._check_network_async)
        self._net_timer.start(10_000)
        # Run once immediately in background
        self._check_network_async()

    def _check_network_async(self):
        """Spawn a daemon thread so the 1-s socket timeout never blocks the UI."""
        def _check():
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=1)
                self._online_cache = True
            except OSError:
                self._online_cache = False
        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _update_status_bar(self):
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        net = "ONLINE" if self._online_cache else "OFFLINE"
        self._status_bar.showMessage(
            f"CPU: {cpu:.0f}%   RAM: {ram.percent:.0f}%   "
            f"Network: {net}   Mode: {self._sys_info.mode_label}"
        )

    def _update_mode_label(self):
        info = self._sys_info
        if info.is_development_mode:
            self._mode_label.setText("🔧 Dev / Compat Mode")
            self._mode_label.setStyleSheet(
                "background:#0C2D6B; color:#58A6FF; "
                "font-size:10px; padding:6px; border-top:1px solid #1F6FEB;"
            )
        else:
            self._mode_label.setText("⚡ Snapdragon NPU Mode")
            self._mode_label.setStyleSheet(
                "background:#0D4429; color:#3FB950; "
                "font-size:10px; padding:6px; border-top:1px solid #238636;"
            )

    def show_demo_banner(self, visible: bool):
        self._demo_banner.setVisible(visible)

    def closeEvent(self, event):
        """Clean up resources on exit."""
        log.info("Application closing — releasing resources.")
        for page in self._pages.values():
            if hasattr(page, "cleanup"):
                try:
                    page.cleanup()
                except Exception as e:
                    log.error(f"Cleanup error: {e}")
        event.accept()
