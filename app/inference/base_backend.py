"""
Abstract base class for all AI inference backends.
All backends must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class Detection:
    """A single detected object from the AI model."""
    bbox: tuple[int, int, int, int]   # (x1, y1, x2, y2) in pixel coords
    confidence: float
    class_id: int
    class_name: str = "person"
    track_id: Optional[int] = None


@dataclass
class InferenceResult:
    """Complete result from one inference call."""
    detections: list[Detection] = field(default_factory=list)
    latency_ms: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    backend_name: str = ""
    device: str = ""


class AIInferenceBackend(ABC):
    """
    Abstract interface for AI inference backends.

    Implementations:
    - LocalONNXBackend   → ONNX Runtime on CPU/GPU
    - QualcommBackend    → Qualcomm AI Runtime / QNN / AI Hub optimized model
    """

    @abstractmethod
    def load_model(self, model_path: str, **kwargs) -> bool:
        """
        Load/initialize the model.
        Returns True on success, False on failure.
        """
        ...

    @abstractmethod
    def infer(self, frame: np.ndarray) -> InferenceResult:
        """
        Run inference on a BGR frame (OpenCV format).
        Returns InferenceResult with all detections.
        """
        ...

    @abstractmethod
    def get_latency(self) -> float:
        """Return the last inference latency in milliseconds."""
        ...

    @abstractmethod
    def get_backend_name(self) -> str:
        """Human-readable backend name (e.g. 'Local ONNX', 'Qualcomm AI Runtime')."""
        ...

    @abstractmethod
    def get_device(self) -> str:
        """Hardware device being used (e.g. 'CPU', 'Snapdragon NPU')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current machine."""
        ...

    @abstractmethod
    def release(self):
        """Release model resources and clean up."""
        ...

    @abstractmethod
    def get_model_info(self) -> dict:
        """Return metadata about the loaded model."""
        ...
