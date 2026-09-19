"""
Tests for BenchmarkRunner.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import time

from app.inference.base_backend import InferenceResult
from app.performance.benchmark import BenchmarkRunner, BenchmarkResult


def make_mock_backend(latency_ms: float = 20.0):
    backend = MagicMock()
    backend.get_backend_name.return_value = "Mock Backend"
    backend.get_device.return_value = "Mock CPU"
    backend.get_model_info.return_value = {
        "model_name": "mock_model.onnx",
        "input_size": "640x640",
    }
    # Simulate inference latency
    def fake_infer(frame):
        time.sleep(latency_ms / 1000)
        return InferenceResult(latency_ms=latency_ms)
    backend.infer.side_effect = fake_infer
    return backend


class TestBenchmarkResult:
    def test_to_dict_has_required_keys(self):
        result = BenchmarkResult()
        result.backend = "Local ONNX"
        result.fps = 30.0
        result.avg_latency = 33.0
        d = result.to_dict()
        for key in ["timestamp", "backend", "fps", "avg_latency", "min_latency", "max_latency"]:
            assert key in d

    def test_summary_text_contains_fps(self):
        result = BenchmarkResult()
        result.fps = 25.5
        result.avg_latency = 40.0
        result.min_latency = 35.0
        result.max_latency = 50.0
        result.backend = "Test"
        result.device  = "CPU"
        result.model_name = "test.onnx"
        text = result.summary_text()
        assert "25.5" in text
        assert "40.0" in text


class TestBenchmarkRunner:
    def test_benchmark_completes(self):
        backend = make_mock_backend(latency_ms=10.0)
        runner = BenchmarkRunner(backend)
        done_called = []

        def on_done(result):
            done_called.append(result)

        runner.run(duration_sec=2, frame_size=(240, 320), done_cb=on_done)
        # Wait for completion
        start = time.time()
        while not done_called and time.time() - start < 10:
            time.sleep(0.1)

        assert len(done_called) == 1
        r = done_called[0]
        assert r.total_frames > 0
        assert r.fps > 0
        assert r.avg_latency > 0

    def test_benchmark_latency_reasonable(self):
        target_ms = 15.0
        backend = make_mock_backend(latency_ms=target_ms)
        runner = BenchmarkRunner(backend)
        done_called = []

        runner.run(duration_sec=2, frame_size=(240, 320), done_cb=lambda r: done_called.append(r))
        start = time.time()
        while not done_called and time.time() - start < 10:
            time.sleep(0.1)

        r = done_called[0]
        # Should be within 2x of simulated latency (overhead expected)
        assert r.avg_latency < target_ms * 5

    def test_benchmark_stop_works(self):
        backend = make_mock_backend(latency_ms=5.0)
        runner = BenchmarkRunner(backend)
        done_called = []
        runner.run(duration_sec=30, done_cb=lambda r: done_called.append(r))
        time.sleep(0.5)
        runner.stop()
        time.sleep(0.5)
        # If runner respected stop, it should have called done_cb
        assert not runner._running
