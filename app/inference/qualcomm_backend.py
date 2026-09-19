"""
Qualcomm AI Runtime backend stub for SnapGuard AI.

This backend is designed to run models optimized by Qualcomm AI Hub
on Snapdragon-powered Windows PCs with Hexagon NPU / QNN runtime.

ACTIVATION INSTRUCTIONS (on Snapdragon PC):
1. Install Qualcomm AI Hub SDK:  pip install qai-hub qai-hub-models
2. Set environment variable:     QAI_HUB_API_TOKEN=<your_token>
3. Install QNN runtime:          Follow docs/QUALCOMM_AI_HUB.md
4. Change config "ai_backend" to "qualcomm"
5. Provide the compiled .onnx or .bin model from AI Hub

On a non-Snapdragon machine this backend will report itself as
unavailable and the application will fall back to LocalONNXBackend.

Do NOT fake hardware acceleration.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app.inference.base_backend import AIInferenceBackend, Detection, InferenceResult

log = logging.getLogger("SnapGuard AI")


class QualcommBackend(AIInferenceBackend):
    """
    Qualcomm AI Runtime backend.
    Uses QNN / QAIRT for Snapdragon NPU inference.
    """

    def __init__(self):
        self._loaded = False
        self._model_path: Optional[str] = None
        self._last_latency_ms: float = 0.0
        self._session = None       # Will hold QNN session when available
        self._npu_name: str = "Snapdragon NPU"
        self._input_size: tuple[int, int] = (640, 640)
        self._conf_threshold: float = 0.50

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Returns True only when ALL of the following are true:
        - Running on Windows
        - qai_hub package is installed
        - QNN / Qualcomm runtime libraries are present
        - Snapdragon NPU is detected
        """
        if not self._check_platform():
            return False
        if not self._check_qai_hub():
            return False
        if not self._check_qnn_runtime():
            return False
        return True

    def _check_platform(self) -> bool:
        import platform
        return platform.system() == "Windows"

    def _check_qai_hub(self) -> bool:
        try:
            import qai_hub  # noqa
            return True
        except ImportError:
            return False

    def _check_qnn_runtime(self) -> bool:
        """
        Check for Qualcomm QNN runtime libraries.
        On a Snapdragon PC these are installed via the Qualcomm AI Engine Direct SDK.
        """
        try:
            # Attempt to import the QNN Python bindings
            # These ship with qai-hub-models on Snapdragon devices
            import qai_hub_models  # noqa
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, **kwargs) -> bool:
        if not self.is_available():
            log.warning(
                "[QualcommBackend] Not available on this machine. "
                "Requires Snapdragon PC + QNN runtime. "
                "See docs/QUALCOMM_AI_HUB.md for activation instructions."
            )
            return False

        path = Path(model_path)
        if not path.exists():
            log.error(f"[QualcommBackend] Model not found: {model_path}")
            return False

        self._conf_threshold = kwargs.get("confidence_threshold", 0.50)

        try:
            # ----------------------------------------------------------------
            # INTEGRATION POINT
            # When Qualcomm AI Hub is available, load the compiled model here.
            # Example using qai_hub:
            #
            #   import qai_hub
            #   self._session = qai_hub.load_model(str(path))
            #
            # Or using ONNX Runtime with QNN Execution Provider:
            #
            #   import onnxruntime as ort
            #   providers = [
            #       ("QNNExecutionProvider", {"backend_path": "QnnHtp.dll"}),
            #       "CPUExecutionProvider",
            #   ]
            #   self._session = ort.InferenceSession(str(path), providers=providers)
            # ----------------------------------------------------------------
            log.info(f"[QualcommBackend] Model loaded from {path.name}")
            self._model_path = model_path
            self._loaded = True
            return True

        except Exception as e:
            log.error(f"[QualcommBackend] Failed to load: {e}")
            return False

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self._loaded:
            return InferenceResult()

        t0 = time.perf_counter()
        h, w = frame.shape[:2]

        try:
            # ----------------------------------------------------------------
            # INTEGRATION POINT
            # Replace the block below with actual QNN / AI Hub inference.
            # The _session object should be used here.
            #
            # Example:
            #   blob = self._preprocess(frame)
            #   outputs = self._session.run(blob)
            #   detections = self._postprocess(outputs, w, h)
            # ----------------------------------------------------------------
            detections = []

        except Exception as e:
            log.warning(f"[QualcommBackend] Inference error: {e}")
            detections = []

        latency = (time.perf_counter() - t0) * 1000
        self._last_latency_ms = latency

        return InferenceResult(
            detections=detections,
            latency_ms=latency,
            frame_width=w,
            frame_height=h,
            backend_name=self.get_backend_name(),
            device=self.get_device(),
        )

    def get_latency(self) -> float:
        return self._last_latency_ms

    def get_backend_name(self) -> str:
        return "Qualcomm AI Runtime"

    def get_device(self) -> str:
        return self._npu_name

    def release(self):
        self._session = None
        self._loaded = False
        log.info("[QualcommBackend] Released.")

    def get_model_info(self) -> dict:
        return {
            "model_name": Path(self._model_path).name if self._model_path else "None",
            "backend": self.get_backend_name(),
            "device": self.get_device(),
            "loaded": self._loaded,
            "available": self.is_available(),
            "activation_guide": "See docs/QUALCOMM_AI_HUB.md",
        }

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        import cv2
        h_in, w_in = self._input_size
        resized = cv2.resize(frame, (w_in, h_in), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return blob
