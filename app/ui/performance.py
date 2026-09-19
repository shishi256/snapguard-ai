"""
Performance page for SnapGuard AI.
Displays live metrics and runs configurable, high-performance AI inference benchmarks.
Thread-safe and optimized for smooth UI responsiveness.
"""

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QProgressBar,
    QSizePolicy, QSpinBox, QScrollArea,
)

from app.config import get_settings
from app.utils.system_info import get_system_info, get_current_metrics
from app.inference.model_manager import ModelManager
from app.performance.benchmark import BenchmarkThread, BenchmarkResult

log = logging.getLogger("SnapGuard AI")


class PerformancePage(QWidget):

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main_window  = main_window
        self._settings     = get_settings()
        self._sys_info     = get_system_info()
        self._model_mgr    = ModelManager()
        self._bench_thread: Optional[BenchmarkThread] = None
        self._model_info_cached = None

        self._setup_ui()
        self._start_metrics_timer()
        self._load_cached_backend_info()

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
            "QScrollBar:vertical { background: #f1f5f9; width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 24px; }"
            "QScrollBar::handle:vertical:hover { background: #0284C7; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setObjectName("content_area")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(36, 28, 36, 36)
        self._content_layout.setSpacing(20)

        # ── Header ──────────────────────────────────────────────────
        title = QLabel("Performance & Benchmarks")
        title.setObjectName("page_title")
        self._content_layout.addWidget(title)

        sub = QLabel("Hardware acceleration telemetry and on-device AI throughput benchmarking")
        sub.setObjectName("page_subtitle")
        self._content_layout.addWidget(sub)

        # ── Top: live metrics & hardware info ───────────────────────
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(16)
        metrics_row.addWidget(self._build_metrics_card(), stretch=1)
        metrics_row.addWidget(self._build_backend_card(), stretch=1)
        self._content_layout.addLayout(metrics_row)

        # ── Benchmark control ───────────────────────────────────────
        self._content_layout.addWidget(self._build_benchmark_card())

        # ── Results table ───────────────────────────────────────────
        self._content_layout.addWidget(self._build_results_table())

        self._content_layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _build_metrics_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        header = QLabel("LIVE SYSTEM TELEMETRY")
        header.setObjectName("section_header")
        layout.addWidget(header)

        def metric_row(label: str) -> QLabel:
            row = QHBoxLayout()
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #64748B; font-weight: 500;")
            lbl.setFixedWidth(130)
            val = QLabel("—")
            val.setObjectName("value_label")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)
            return val

        self._cpu_lbl  = metric_row("CPU Load")
        self._ram_lbl  = metric_row("Memory Used")
        self._fps_lbl  = metric_row("Camera FPS")
        self._lat_lbl  = metric_row("Live Latency")

        # CPU load progress bar
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setValue(0)
        layout.addWidget(self._cpu_bar)

        return card

    def _build_backend_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header = QLabel("AI ACCELERATION BACKEND")
        header.setObjectName("section_header")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_backend_info)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        def info_row(label: str) -> QLabel:
            row = QHBoxLayout()
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #64748B; font-weight: 500;")
            lbl.setFixedWidth(140)
            val = QLabel("—")
            val.setObjectName("value_label")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)
            return val

        self._backend_lbl    = info_row("Backend Runtime")
        self._device_lbl     = info_row("Hardware Target")
        self._model_lbl      = info_row("Loaded Model")
        self._resolution_lbl = info_row("Input Resolution")
        self._hw_accel_lbl   = info_row("NPU Acceleration")

        return card

    def _build_benchmark_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QLabel("SYNTHETIC INFERENCE BENCHMARK")
        header.setObjectName("section_header")
        layout.addWidget(header)

        desc = QLabel(
            "Execute a controlled on-device AI inference benchmark to measure real sustained throughput "
            "(FPS), average latency, and resource footprint on this machine."
        )
        desc.setObjectName("description_label")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        config_row = QHBoxLayout()
        config_row.setSpacing(14)

        lbl_dur = QLabel("Benchmark Duration:")
        lbl_dur.setStyleSheet("font-weight: 600; color: #334155;")
        config_row.addWidget(lbl_dur)

        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(3, 60)
        self._duration_spin.setValue(self._settings.get("benchmark_duration_sec", 10))
        self._duration_spin.setSuffix(" sec")
        config_row.addWidget(self._duration_spin)

        self._run_bench_btn = QPushButton("⚡  Start Benchmark")
        self._run_bench_btn.setObjectName("btn_blue")
        self._run_bench_btn.setCursor(Qt.PointingHandCursor)
        self._run_bench_btn.clicked.connect(self._run_benchmark)
        config_row.addWidget(self._run_bench_btn)

        self._stop_bench_btn = QPushButton("⏹  Stop")
        self._stop_bench_btn.setCursor(Qt.PointingHandCursor)
        self._stop_bench_btn.clicked.connect(self._stop_benchmark)
        self._stop_bench_btn.setEnabled(False)
        config_row.addWidget(self._stop_bench_btn)

        config_row.addStretch()
        layout.addLayout(config_row)

        # Progress bar
        self._bench_progress = QProgressBar()
        self._bench_progress.setRange(0, 100)
        self._bench_progress.setValue(0)
        self._bench_progress.setVisible(False)
        layout.addWidget(self._bench_progress)

        # Status label
        self._bench_status = QLabel("")
        self._bench_status.setObjectName("description_label")
        layout.addWidget(self._bench_status)

        # Result summary box
        self._bench_result_frame = QFrame()
        self._bench_result_frame.setObjectName("alert_overlay")
        self._bench_result_frame.setVisible(False)
        res_layout = QVBoxLayout(self._bench_result_frame)
        res_layout.setContentsMargins(16, 12, 16, 12)
        res_layout.setSpacing(6)

        self._bench_result_title = QLabel("✅ BENCHMARK RESULTS")
        self._bench_result_title.setStyleSheet("font-weight: 800; font-size: 13px; color: #059669;")
        res_layout.addWidget(self._bench_result_title)

        self._bench_result_label = QLabel("")
        self._bench_result_label.setStyleSheet("color: #0F172A; font-weight: 600; font-size: 13px;")
        self._bench_result_label.setWordWrap(True)
        res_layout.addWidget(self._bench_result_label)

        layout.addWidget(self._bench_result_frame)

        return card

    def _build_results_table(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header = QLabel("BENCHMARK HISTORY")
        header.setObjectName("section_header")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄  Refresh Table")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        refresh_btn.clicked.connect(self._load_benchmark_history)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self._results_table = QTableWidget()
        self._results_table.setColumnCount(7)
        self._results_table.setHorizontalHeaderLabels([
            "Timestamp", "Backend", "Throughput (FPS)", "Avg Latency", "Min Latency", "Max Latency", "CPU Load"
        ])
        self._results_table.horizontalHeader().setStretchLastSection(True)
        self._results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.setMinimumHeight(180)
        layout.addWidget(self._results_table)

        self._load_benchmark_history()
        return card

    # ------------------------------------------------------------------
    # Telemetry Timer
    # ------------------------------------------------------------------

    def _start_metrics_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        self._timer.start(1000)

    def _update_metrics(self):
        try:
            m = get_current_metrics()
            cpu = m["cpu_percent"]
            self._cpu_lbl.setText(f"{cpu:.1f}%")
            self._ram_lbl.setText(f"{m['ram_used_mb']:.0f} MB ({m['ram_percent']:.0f}%)")
            self._cpu_bar.setValue(int(cpu))

            if self._main_window:
                lp = self._main_window.get_page("live_protection")
                if lp and hasattr(lp, "_current_fps"):
                    fps = lp._current_fps
                    lat = lp._current_latency
                    self._fps_lbl.setText(f"{fps:.1f} FPS" if fps > 0 else "Camera Idle")
                    self._lat_lbl.setText(f"{lat:.0f} ms" if lat > 0 else "—")
        except Exception as e:
            log.debug(f"[PerformancePage] metrics error: {e}")

    # ------------------------------------------------------------------
    # Backend Info (Cached to avoid disk/model thrashing)
    # ------------------------------------------------------------------

    def _load_cached_backend_info(self):
        si = self._sys_info
        backend_name = "Qualcomm AI Runtime" if si.qai_hub_available else "Local ONNX"
        device_name  = si.qualcomm_npu_name if si.qualcomm_npu_available else "CPU (Development Mode)"
        hw_accel     = "Snapdragon NPU Active" if si.qualcomm_npu_available else "CPU (Fallback Mode)"
        hw_color     = "#059669" if si.qualcomm_npu_available else "#64748B"

        self._backend_lbl.setText(backend_name)
        self._device_lbl.setText(device_name)
        self._hw_accel_lbl.setText(hw_accel)
        self._hw_accel_lbl.setStyleSheet(f"color: {hw_color}; font-weight: 700;")
        self._model_lbl.setText("YOLOv8n Person Detector")
        self._resolution_lbl.setText("640 x 640 x 3")

    def _refresh_backend_info(self):
        self._sys_info = get_system_info(refresh=True)
        self._load_cached_backend_info()

    # ------------------------------------------------------------------
    # Benchmark Runner (Thread-safe via BenchmarkThread)
    # ------------------------------------------------------------------

    def _run_benchmark(self):
        if self._bench_thread and self._bench_thread.isRunning():
            return

        duration = self._duration_spin.value()
        self._settings.set("benchmark_duration_sec", duration)

        # Initialize model manager once
        if not self._model_mgr.initialize():
            self._bench_status.setText("⚠ Model file missing. Please ensure YOLOv8n is present.")
            return

        backend = self._model_mgr.get_backend()
        if not backend:
            self._bench_status.setText("⚠ Backend unavailable.")
            return

        self._run_bench_btn.setEnabled(False)
        self._stop_bench_btn.setEnabled(True)
        self._bench_progress.setVisible(True)
        self._bench_progress.setValue(0)
        self._bench_result_frame.setVisible(False)
        self._bench_status.setText(f"Initializing benchmark for {duration} seconds...")

        self._bench_thread = BenchmarkThread(backend, duration_sec=duration, parent=self)
        self._bench_thread.progress_updated.connect(self._on_bench_progress)
        self._bench_thread.benchmark_done.connect(self._on_bench_done)
        self._bench_thread.error_occurred.connect(self._on_bench_error)
        self._bench_thread.start()

    def _on_bench_progress(self, frame_num: int, current_fps: float, latency_ms: float, pct: int):
        self._bench_progress.setValue(pct)
        self._bench_status.setText(
            f"Benchmarking... Frame: {frame_num} | Throughput: {current_fps:.1f} FPS | Latency: {latency_ms:.1f} ms"
        )

    def _on_bench_done(self, result: BenchmarkResult):
        self._run_bench_btn.setEnabled(True)
        self._stop_bench_btn.setEnabled(False)
        self._bench_progress.setValue(100)
        self._bench_status.setText("✅ Benchmark finished successfully. Results persisted to database.")

        summary = (
            f"Throughput: {result.fps:.1f} FPS    |    "
            f"Avg Latency: {result.avg_latency:.1f} ms    |    "
            f"Min/Max: {result.min_latency:.1f} / {result.max_latency:.1f} ms    |    "
            f"CPU Load: {result.cpu_pct:.1f}%    |    "
            f"RAM: {result.ram_mb:.0f} MB"
        )
        self._bench_result_label.setText(summary)
        self._bench_result_frame.setVisible(True)

        self._load_benchmark_history()
        self._model_mgr.release()

    def _on_bench_error(self, err_msg: str):
        self._run_bench_btn.setEnabled(True)
        self._stop_bench_btn.setEnabled(False)
        self._bench_status.setText(f"❌ Benchmark failed: {err_msg}")
        self._model_mgr.release()

    def _stop_benchmark(self):
        if self._bench_thread and self._bench_thread.isRunning():
            self._bench_thread.stop()
            self._bench_status.setText("Stopping benchmark...")
        self._run_bench_btn.setEnabled(True)
        self._stop_bench_btn.setEnabled(False)

    def _load_benchmark_history(self):
        try:
            results = get_settings().get_benchmark_results(limit=12)
            self._results_table.setRowCount(len(results))
            for row, r in enumerate(results):
                ts = r.get("timestamp", "")[:19].replace("T", " ")
                self._results_table.setItem(row, 0, QTableWidgetItem(ts))
                self._results_table.setItem(row, 1, QTableWidgetItem(r.get("backend", "")))
                self._results_table.setItem(row, 2, QTableWidgetItem(f"{r.get('fps', 0):.1f} FPS"))
                self._results_table.setItem(row, 3, QTableWidgetItem(f"{r.get('avg_latency', 0):.1f} ms"))
                self._results_table.setItem(row, 4, QTableWidgetItem(f"{r.get('min_latency', 0):.1f} ms"))
                self._results_table.setItem(row, 5, QTableWidgetItem(f"{r.get('max_latency', 0):.1f} ms"))
                self._results_table.setItem(row, 6, QTableWidgetItem(f"{r.get('cpu_pct', 0):.1f}%"))
            self._results_table.resizeColumnsToContents()
        except Exception as e:
            log.debug(f"[PerformancePage] history error: {e}")

    def on_page_activated(self):
        # Refresh telemetry without loading model
        self._load_benchmark_history()
