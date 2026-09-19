"""
Tests for AI inference backends and ModelManager.
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.inference.base_backend import Detection, InferenceResult
from app.inference.onnx_backend import LocalONNXBackend
from app.inference.qualcomm_backend import QualcommBackend


class TestLocalONNXBackend:
    def test_backend_name(self):
        backend = LocalONNXBackend()
        assert backend.get_backend_name() == "Local ONNX"

    def test_device_default_cpu(self):
        backend = LocalONNXBackend()
        # Before loading, providers are empty
        assert "CPU" in backend.get_device() or backend.get_device() == "CPU"

    def test_is_available(self):
        backend = LocalONNXBackend()
        # ONNX Runtime must be installed for tests to work
        assert backend.is_available() is True

    def test_load_model_missing_file(self):
        backend = LocalONNXBackend()
        result = backend.load_model("/nonexistent/path/model.onnx")
        assert result is False

    def test_infer_without_loading_returns_empty(self):
        backend = LocalONNXBackend()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)
        assert isinstance(result, InferenceResult)
        assert result.detections == []

    def test_get_latency_initial_zero(self):
        backend = LocalONNXBackend()
        assert backend.get_latency() == 0.0

    def test_get_model_info_unloaded(self):
        backend = LocalONNXBackend()
        info = backend.get_model_info()
        assert info["loaded"] is False

    def test_release_safe_without_loading(self):
        backend = LocalONNXBackend()
        backend.release()   # Should not raise


class TestQualcommBackend:
    def test_backend_name(self):
        backend = QualcommBackend()
        assert backend.get_backend_name() == "Qualcomm AI Runtime"

    def test_device_name(self):
        backend = QualcommBackend()
        assert "Snapdragon" in backend.get_device() or "NPU" in backend.get_device()

    def test_not_available_on_dev_machine(self):
        """On a non-Snapdragon dev machine, Qualcomm backend should not be available."""
        import platform
        if platform.system() != "Windows":
            backend = QualcommBackend()
            assert backend.is_available() is False

    def test_load_model_unavailable_returns_false(self):
        backend = QualcommBackend()
        if not backend.is_available():
            result = backend.load_model("/some/model.onnx")
            assert result is False

    def test_infer_without_loading_returns_empty(self):
        backend = QualcommBackend()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)
        assert isinstance(result, InferenceResult)
        assert result.detections == []

    def test_model_info_includes_activation_guide(self):
        backend = QualcommBackend()
        info = backend.get_model_info()
        assert "activation_guide" in info


class TestDetectionDataclass:
    def test_detection_creation(self):
        det = Detection(bbox=(10, 20, 100, 200), confidence=0.85, class_id=0)
        assert det.class_id == 0
        assert det.confidence == pytest.approx(0.85)
        assert det.bbox == (10, 20, 100, 200)

    def test_inference_result_empty(self):
        result = InferenceResult()
        assert result.detections == []
        assert result.latency_ms == 0.0


@pytest.mark.skipif(
    not Path("models/yolov8n.onnx").exists(),
    reason="YOLOv8n model not downloaded — run scripts/download_model.py"
)
class TestLiveInference:
    def test_inference_on_blank_frame(self):
        backend = LocalONNXBackend()
        assert backend.load_model("models/yolov8n.onnx")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)
        assert isinstance(result, InferenceResult)
        assert result.latency_ms > 0
        assert result.frame_width == 640
        backend.release()

    def test_inference_returns_persons_only(self):
        backend = LocalONNXBackend()
        assert backend.load_model("models/yolov8n.onnx")
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)
        for det in result.detections:
            assert det.class_id == 0   # person only
        backend.release()
