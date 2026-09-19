"""
Benchmark Runner for SnapGuard AI.
Runs a configurable inference benchmark and collects performance metrics.
Thread-safe execution with Qt Signals for silky-smooth UI updates.
"""

import time
import logging
import threading
from datetime import datetime
from typing import Callable, Optional

import numpy as np
import psutil
from PySide6.QtCore import QThread, Signal

from app.config import get_settings
from app.inference.base_backend import AIInferenceBackend

log = logging.getLogger("SnapGuard AI")


class BenchmarkResult:
    def __init__(self):
        self.timestamp: str = datetime.now().isoformat()
        self.backend: str = ""
        self.device: str = ""
        self.model_name: str = ""
        self.input_resolution: str = ""
        self.total_frames: int = 0
        self.duration_sec: float = 0.0
        self.avg_latency: float = 0.0
        self.min_latency: float = float("inf")
        self.max_latency: float = 0.0
        self.std_latency: float = 0.0
        self.fps: float = 0.0
        self.cpu_pct: float = 0.0
        self.ram_mb: float = 0.0
        self.notes: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp":        self.timestamp,
            "backend":          self.backend,
            "device":           self.device,
            "model_name":       self.model_name,
            "input_resolution": self.input_resolution,
            "total_frames":     self.total_frames,
            "duration_sec":     round(self.duration_sec, 2),
            "avg_latency":      round(self.avg_latency, 2),
            "min_latency":      round(self.min_latency, 2),
            "max_latency":      round(self.max_latency, 2),
            "std_latency":      round(self.std_latency, 2),
            "fps":              round(self.fps, 2),
            "cpu_pct":          round(self.cpu_pct, 2),
            "ram_mb":           round(self.ram_mb, 1),
            "notes":            self.notes,
        }

    def summary_text(self) -> str:
        return (
            f"Backend:    {self.backend} ({self.device})\n"
            f"Model:      {self.model_name}\n"
            f"Frames:     {self.total_frames} in {self.duration_sec:.1f}s\n"
            f"FPS:        {self.fps:.1f}\n"
            f"Latency:    avg={self.avg_latency:.1f}ms  "
            f"min={self.min_latency:.1f}ms  max={self.max_latency:.1f}ms\n"
            f"CPU:        {self.cpu_pct:.1f}%\n"
            f"RAM:        {self.ram_mb:.0f} MB\n"
        )


class BenchmarkThread(QThread):
    """
    QThread-based benchmark worker. Emits Qt signals safely
    to the main thread for smooth progress bar and metric updates.
    """
    progress_updated = Signal(int, float, float, int)  # frames, current_fps, current_latency, pct
    benchmark_done   = Signal(object)                 # BenchmarkResult
    error_occurred   = Signal(str)

    def __init__(
        self,
        backend: AIInferenceBackend,
        duration_sec: int = 10,
        frame_size: tuple[int, int] = (480, 640),
        parent=None,
    ):
        super().__init__(parent)
        self._backend = backend
        self._duration_sec = duration_sec
        self._frame_size = frame_size
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        latencies = []
        cpu_samples = []
        ram_samples = []

        try:
            model_info = self._backend.get_model_info()
            h, w = self._frame_size
            rng = np.random.default_rng(42)

            # Warm-up (2 frames)
            warmup_frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
            for _ in range(2):
                if not self._running:
                    return
                self._backend.infer(warmup_frame)

            t_start = time.perf_counter()
            frame_num = 0
            last_sample_time = t_start
            last_emit_time = t_start

            while self._running:
                now = time.perf_counter()
                elapsed = now - t_start
                if elapsed >= self._duration_sec:
                    break

                # Create synthetic frame
                test_frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)

                t0 = time.perf_counter()
                self._backend.infer(test_frame)
                latency = (time.perf_counter() - t0) * 1000
                latencies.append(latency)
                frame_num += 1

                # Sample system metrics at max 2 Hz to avoid system call lag
                if now - last_sample_time >= 0.5:
                    cpu_samples.append(psutil.cpu_percent(interval=None))
                    ram_samples.append(psutil.virtual_memory().used / (1024 ** 2))
                    last_sample_time = now

                # Emit progress to UI at ~15 Hz
                if now - last_emit_time >= 0.06:
                    current_fps = frame_num / max(elapsed, 0.001)
                    pct = min(99, int(elapsed / max(self._duration_sec, 1) * 100))
                    self.progress_updated.emit(frame_num, current_fps, latency, pct)
                    last_emit_time = now

            total_elapsed = time.perf_counter() - t_start
            self._running = False

            # Compile results
            result = BenchmarkResult()
            result.backend          = self._backend.get_backend_name()
            result.device           = self._backend.get_device()
            result.model_name       = model_info.get("model_name", "Unknown")
            result.input_resolution = f"{w}x{h}"
            result.total_frames     = frame_num
            result.duration_sec     = total_elapsed
            result.fps              = frame_num / max(total_elapsed, 0.001)

            if latencies:
                arr = np.array(latencies)
                result.avg_latency = float(np.mean(arr))
                result.min_latency = float(np.min(arr))
                result.max_latency = float(np.max(arr))
                result.std_latency = float(np.std(arr))

            result.cpu_pct = float(np.mean(cpu_samples)) if cpu_samples else 0.0
            result.ram_mb  = float(np.mean(ram_samples))  if ram_samples  else 0.0

            log.info(f"[Benchmark] Complete:\n{result.summary_text()}")

            # Save to SQLite database
            settings = get_settings()
            settings.save_benchmark_result(result.to_dict())

            self.benchmark_done.emit(result)

        except Exception as e:
            log.error(f"[Benchmark] Failed: {e}")
            self._running = False
            self.error_occurred.emit(str(e))


class BenchmarkRunner:
    """Legacy wrapper maintained for backwards compatibility."""

    def __init__(self, backend: AIInferenceBackend):
        self._backend = backend
        self._thread: Optional[BenchmarkThread] = None

    def run(
        self,
        duration_sec: int = 10,
        frame_size: tuple[int, int] = (480, 640),
        progress_cb: Optional[Callable[[int, int], None]] = None,
        done_cb: Optional[Callable[[BenchmarkResult], None]] = None,
    ):
        self._thread = BenchmarkThread(self._backend, duration_sec, frame_size)
        if progress_cb:
            self._thread.progress_updated.connect(lambda f, fps, lat, pct: progress_cb(f, pct))
        if done_cb:
            self._thread.benchmark_done.connect(done_cb)
        self._thread.start()

    def stop(self):
        if self._thread:
            self._thread.stop()
