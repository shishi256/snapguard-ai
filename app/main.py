"""
SnapGuard AI — Entry Point
"Your laptop. Your data. Your privacy."

Usage:
    python app/main.py
    python app/main.py --demo          # start in demo mode
    python app/main.py --page perf     # open directly on performance page
"""

import sys
import os
import argparse
import logging

# ── macOS: must be set before any cv2 import so OpenCV skips in-thread auth ──
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFontDatabase, QFont

from app.utils.logging import setup_logger
from app.config import APP_NAME, APP_VERSION, ASSETS_DIR, get_settings

log = setup_logger()


def load_stylesheet(app: QApplication) -> None:
    settings = get_settings()
    theme = settings.get("theme", "light")
    qss_filename = "light_theme.qss" if theme == "light" else "dark_theme.qss"
    qss_path = ASSETS_DIR / "styles" / qss_filename
    if not qss_path.exists():
        qss_path = ASSETS_DIR / "styles" / "light_theme.qss"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        log.info(f"Stylesheet ({theme}) loaded from {qss_path}")
    else:
        log.warning(f"Stylesheet not found at {qss_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — On-Device AI Privacy Protection"
    )
    parser.add_argument("--demo",  action="store_true", help="Start in demo mode")
    parser.add_argument("--page",  default="dashboard",
                        choices=["dashboard", "live_protection", "privacy_mode",
                                 "performance", "settings", "about"],
                        help="Open on a specific page")
    return parser.parse_args()


def _prime_camera_on_main_thread(camera_index: int = 1) -> None:
    """
    macOS requires camera authorization to be requested from the main thread.
    OpenCV's AVFoundation backend cannot do this from a QThread, so we open
    the camera briefly here (on the main thread) to trigger the permission
    dialog and warm up the driver.  The QThread camera worker then starts
    cleanly with OPENCV_AVFOUNDATION_SKIP_AUTH=1 already set.

    camera_index=1 → built-in laptop FaceTime camera (index 0 is iPhone
    Continuity Camera on macOS when an iPhone is nearby).
    """
    import cv2
    import time

    log.info(f"[main] Priming camera {camera_index} on main thread (macOS auth workaround)…")
    cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        time.sleep(0.8)   # let macOS AVFoundation driver initialise
        cap.read()        # consume one frame to confirm access is granted
        cap.release()
        log.info(f"[main] Camera {camera_index} primed successfully.")
    else:
        log.warning(f"[main] Camera {camera_index} prime failed — trying index 0 as fallback…")
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            time.sleep(0.8)
            cap.read()
            cap.release()
            log.info("[main] Fallback camera 0 primed.")


def main():
    args = parse_args()

    # Apply demo mode setting before UI loads
    settings = get_settings()
    if args.demo:
        settings.set("demo_mode", True)

    # ── Qt application ─────────────────────────────────────────────
    QCoreApplication.setOrganizationName("SnapGuard")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(APP_VERSION)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # Font
    app.setFont(QFont("Segoe UI", 10))

    # Stylesheet
    load_stylesheet(app)

    # ── Prime camera on main thread (macOS permission + warm-up) ───
    # Use the saved camera_index so we prime the correct device
    if not args.demo:
        _prime_camera_on_main_thread(camera_index=get_settings().get("camera_index", 1))

    # ── Main window ────────────────────────────────────────────────
    from app.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    # Navigate to requested page
    if args.page != "dashboard":
        window.navigate(args.page)

    # Auto-start demo if requested
    if args.demo:
        lp_page = window.get_page("live_protection")
        if lp_page and hasattr(lp_page, "_start_demo"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, lp_page._start_demo)
            window.navigate("live_protection")

    log.info(f"{'='*50}")
    log.info(f"  {APP_NAME} v{APP_VERSION} started")
    log.info(f"{'='*50}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
