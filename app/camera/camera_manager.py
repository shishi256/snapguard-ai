"""
Camera Manager for SnapGuard AI.
Non-blocking webcam capture using QThread so the UI never freezes.
Supports live camera and demo (video file) modes.
"""

import time
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

log = logging.getLogger("SnapGuard AI")


class CameraWorker(QThread):
    """
    Background thread that continuously reads frames from a camera or video file.

    Signals:
        frame_ready(np.ndarray)  — emitted for every new frame
        error(str)               — emitted on fatal camera errors
        fps_updated(float)       — emitted ~once/second with current FPS
    """

    frame_ready = Signal(object)   # np.ndarray
    error       = Signal(str)
    fps_updated = Signal(float)

    def __init__(
        self,
        camera_index: int = 0,
        target_fps: int = 30,
        resolution: tuple[int, int] = (640, 480),
        demo_video_path: Optional[str] = None,
    ):
        super().__init__()
        self._camera_index   = camera_index
        self._target_fps     = target_fps
        self._resolution     = resolution
        self._demo_video_path = demo_video_path
        self._running        = False
        self._paused         = False
        self._mutex          = QMutex()
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_demo        = bool(demo_video_path)

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False

    def pause(self):
        with QMutexLocker(self._mutex):
            self._paused = True

    def resume(self):
        with QMutexLocker(self._mutex):
            self._paused = False

    def is_demo(self) -> bool:
        return self._is_demo

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self):
        self._running = True

        if self._is_demo and self._demo_video_path:
            cap = cv2.VideoCapture(self._demo_video_path)
            log.info(f"[CameraWorker] Demo mode — {self._demo_video_path}")
        else:
            cap = cv2.VideoCapture(self._camera_index)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
                cap.set(cv2.CAP_PROP_FPS, self._target_fps)
                log.info(
                    f"[CameraWorker] Camera {self._camera_index} opened | "
                    f"res={self._resolution} fps={self._target_fps}"
                )
                # macOS requires a short warm-up before the first frame is ready
                time.sleep(0.8)

        if not cap.isOpened():
            msg = (
                f"Cannot open {'demo video' if self._is_demo else f'camera {self._camera_index}'}."
                " Check that the camera is connected and not in use by another app."
            )
            log.error(msg)
            self.error.emit(msg)
            return

        self._cap = cap
        frame_count  = 0
        fps_timer    = time.perf_counter()
        frame_delay  = 1.0 / max(self._target_fps, 1)

        try:
            while True:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break
                    paused = self._paused

                if paused:
                    time.sleep(0.05)
                    continue

                t_start = time.perf_counter()
                ret, frame = cap.read()

                if not ret:
                    if self._is_demo:
                        # Loop demo video
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        log.error("[CameraWorker] Frame read failed.")
                        self.error.emit("Camera disconnected or frame read failed.")
                        break

                self.frame_ready.emit(frame)
                frame_count += 1

                # FPS calculation
                elapsed = time.perf_counter() - fps_timer
                if elapsed >= 1.0:
                    self.fps_updated.emit(frame_count / elapsed)
                    frame_count = 0
                    fps_timer   = time.perf_counter()

                # Rate limiting
                proc_time = time.perf_counter() - t_start
                sleep_for = frame_delay - proc_time
                if sleep_for > 0:
                    time.sleep(sleep_for)

        finally:
            cap.release()
            self._cap = None
            log.info("[CameraWorker] Camera released.")


class CameraManager:
    """
    High-level camera manager.
    Creates and controls the CameraWorker thread.
    """

    def __init__(self):
        self._worker: Optional[CameraWorker] = None

    def start(
        self,
        camera_index: int = 0,
        target_fps: int = 30,
        resolution: tuple[int, int] = (640, 480),
        demo_video_path: Optional[str] = None,
    ) -> CameraWorker:
        self.stop()
        self._worker = CameraWorker(
            camera_index=camera_index,
            target_fps=target_fps,
            resolution=resolution,
            demo_video_path=demo_video_path,
        )
        self._worker.start()
        return self._worker

    def stop(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)  # wait up to 3s

    def pause(self):
        if self._worker:
            self._worker.pause()

    def resume(self):
        if self._worker:
            self._worker.resume()

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def get_worker(self) -> Optional[CameraWorker]:
        return self._worker

    @staticmethod
    def list_cameras(max_check: int = 5) -> list[int]:
        """Return list of available camera indices."""
        available = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
