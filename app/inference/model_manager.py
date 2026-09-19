"""
Model Manager for SnapGuard AI.
Selects the appropriate inference backend, handles model download/verification,
and provides a unified inference interface.
"""

import logging
import json
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import MODELS_DIR, MODEL_CONFIG_PATH, DEFAULT_MODEL_CONFIG, get_settings
from app.inference.base_backend import AIInferenceBackend, InferenceResult
from app.inference.onnx_backend import LocalONNXBackend
from app.inference.qualcomm_backend import QualcommBackend

log = logging.getLogger("SnapGuard AI")


class ModelManager:
    """
    Manages AI backend lifecycle.
    Selects backend based on config, loads model, and exposes a simple infer() API.
    """

    def __init__(self):
        self._backend: Optional[AIInferenceBackend] = None
        self._loaded: bool = False
        self._settings = get_settings()
        self._model_config: dict = self._load_model_config()

    def _load_model_config(self) -> dict:
        if MODEL_CONFIG_PATH.exists():
            try:
                with open(MODEL_CONFIG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                log.warning(f"Failed to load model_config.json: {e}")
        return dict(DEFAULT_MODEL_CONFIG)

    def get_model_path(self) -> Path:
        filename = self._model_config.get("model_file", "yolov8n.onnx")
        return MODELS_DIR / filename

    def initialize(self) -> bool:
        """
        Select backend, load model.
        Returns True if ready for inference.
        """
        backend_name = self._settings.get("ai_backend", "local_onnx")

        if backend_name == "qualcomm":
            self._backend = QualcommBackend()
            if not self._backend.is_available():
                log.warning(
                    "Qualcomm backend selected but not available. "
                    "Falling back to Local ONNX."
                )
                self._backend = LocalONNXBackend()
        else:
            self._backend = LocalONNXBackend()

        if not self._backend.is_available():
            log.error("No inference backend available. Check dependencies.")
            return False

        model_path = self.get_model_path()
        if not model_path.exists():
            log.warning(f"Model file not found at {model_path}. Run models/download_model.py")
            return False

        success = self._backend.load_model(
            str(model_path),
            confidence_threshold=float(self._settings.get("confidence_threshold", 0.5)),
            iou_threshold=float(self._settings.get("iou_threshold", 0.45)),
        )

        self._loaded = success
        if success:
            log.info(
                f"ModelManager ready | backend={self._backend.get_backend_name()} "
                f"| device={self._backend.get_device()}"
            )
        return success

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self._loaded or self._backend is None:
            return InferenceResult()
        return self._backend.infer(frame)

    def get_backend(self) -> Optional[AIInferenceBackend]:
        return self._backend

    def get_backend_name(self) -> str:
        return self._backend.get_backend_name() if self._backend else "None"

    def get_device(self) -> str:
        return self._backend.get_device() if self._backend else "None"

    def get_model_info(self) -> dict:
        if self._backend:
            return self._backend.get_model_info()
        return {"loaded": False}

    def is_loaded(self) -> bool:
        return self._loaded

    def release(self):
        if self._backend:
            self._backend.release()
        self._loaded = False

    def reload(self) -> bool:
        self.release()
        return self.initialize()
