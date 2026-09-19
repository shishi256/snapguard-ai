"""
Local ONNX Runtime backend for SnapGuard AI.
Uses YOLOv8n ONNX model for person detection.
Runs entirely on CPU (or GPU via ONNX Runtime GPU providers if available).
"""

import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from app.inference.base_backend import AIInferenceBackend, Detection, InferenceResult

log = logging.getLogger("SnapGuard AI")

# COCO class names (we only care about person = 0, but keep full list for future)
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]


class LocalONNXBackend(AIInferenceBackend):
    """
    ONNX Runtime inference backend.
    Designed to run YOLOv8n for real-time person detection.
    """

    def __init__(self):
        self._session = None
        self._model_path: Optional[str] = None
        self._input_name: str = ""
        self._input_shape: tuple = (1, 3, 640, 640)
        self._input_size: tuple[int, int] = (640, 640)   # (h, w)
        self._conf_threshold: float = 0.50
        self._iou_threshold: float = 0.45
        self._last_latency_ms: float = 0.0
        self._loaded: bool = False
        self._providers: list[str] = []

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            import onnxruntime  # noqa
            return True
        except ImportError:
            return False

    def load_model(self, model_path: str, **kwargs) -> bool:
        if not self.is_available():
            log.error("ONNX Runtime is not installed.")
            return False

        import onnxruntime as ort

        path = Path(model_path)
        if not path.exists():
            log.error(f"Model file not found: {model_path}")
            return False

        self._conf_threshold = kwargs.get("confidence_threshold", 0.50)
        self._iou_threshold   = kwargs.get("iou_threshold", 0.45)

        try:
            # Prefer GPU providers if available, fall back to CPU
            available = ort.get_available_providers()
            preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._providers = [p for p in preferred if p in available]
            if not self._providers:
                self._providers = ["CPUExecutionProvider"]

            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = 4

            self._session = ort.InferenceSession(
                str(path), sess_options=opts, providers=self._providers
            )
            self._input_name = self._session.get_inputs()[0].name
            shape = self._session.get_inputs()[0].shape
            # shape: [batch, C, H, W]  e.g. [1, 3, 640, 640]
            if len(shape) == 4:
                self._input_size = (int(shape[2]), int(shape[3]))  # (H, W)

            self._model_path = model_path
            self._loaded = True
            log.info(
                f"[LocalONNXBackend] Loaded '{path.name}' | "
                f"input={self._input_size} | providers={self._providers}"
            )
            return True

        except Exception as e:
            log.error(f"[LocalONNXBackend] Failed to load model: {e}")
            return False

    def infer(self, frame: np.ndarray) -> InferenceResult:
        if not self._loaded or self._session is None:
            return InferenceResult()

        h, w = frame.shape[:2]
        t0 = time.perf_counter()

        try:
            blob = self._preprocess(frame)
            outputs = self._session.run(None, {self._input_name: blob})
            detections = self._postprocess(outputs, orig_w=w, orig_h=h)
        except Exception as e:
            log.warning(f"[LocalONNXBackend] Inference error: {e}")
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
        return "Local ONNX"

    def get_device(self) -> str:
        if not self._providers:
            return "CPU"
        if "CUDAExecutionProvider" in self._providers:
            return "GPU (CUDA)"
        return "CPU"

    def release(self):
        self._session = None
        self._loaded = False
        log.info("[LocalONNXBackend] Released.")

    def get_model_info(self) -> dict:
        return {
            "model_name": Path(self._model_path).name if self._model_path else "None",
            "input_size": f"{self._input_size[1]}x{self._input_size[0]}",
            "backend": self.get_backend_name(),
            "device": self.get_device(),
            "providers": self._providers,
            "loaded": self._loaded,
            "conf_threshold": self._conf_threshold,
        }

    # ------------------------------------------------------------------
    # Internal helpers — YOLOv8 preprocessing / postprocessing
    # ------------------------------------------------------------------

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize + normalize BGR frame to model input tensor."""
        import cv2
        h_in, w_in = self._input_size  # (H, W)
        resized = cv2.resize(frame, (w_in, h_in), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0          # [H, W, C] 0-1
        blob = np.transpose(blob, (2, 0, 1))            # [C, H, W]
        blob = np.expand_dims(blob, axis=0)             # [1, C, H, W]
        return blob

    def _postprocess(
        self, outputs: list, orig_w: int, orig_h: int
    ) -> list[Detection]:
        """
        Parse YOLOv8 ONNX output.
        YOLOv8 ONNX exports shape: [1, 84, 8400]
        (84 = 4 bbox + 80 classes)
        """
        raw = outputs[0]  # shape [1, 84, 8400]
        if raw.ndim == 3:
            raw = raw[0]  # [84, 8400]

        # Transpose to [8400, 84]
        preds = raw.T  # [8400, 84]

        bboxes   = preds[:, :4]          # cx, cy, w, h (normalized to input size)
        scores   = preds[:, 4:]          # class scores [8400, 80]

        class_ids   = np.argmax(scores, axis=1)
        class_confs = np.max(scores, axis=1)

        # Filter by confidence and person class only
        mask = (class_confs >= self._conf_threshold) & (class_ids == 0)
        bboxes      = bboxes[mask]
        class_confs = class_confs[mask]
        class_ids   = class_ids[mask]

        if len(bboxes) == 0:
            return []

        # Scale from input size to original frame size
        sx = orig_w / self._input_size[1]
        sy = orig_h / self._input_size[0]

        # Convert cx,cy,w,h → x1,y1,x2,y2
        x1 = (bboxes[:, 0] - bboxes[:, 2] / 2) * sx
        y1 = (bboxes[:, 1] - bboxes[:, 3] / 2) * sy
        x2 = (bboxes[:, 0] + bboxes[:, 2] / 2) * sx
        y2 = (bboxes[:, 1] + bboxes[:, 3] / 2) * sy

        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1).astype(int)

        # NMS
        import cv2
        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_xyxy.tolist(),
            scores=class_confs.tolist(),
            score_threshold=self._conf_threshold,
            nms_threshold=self._iou_threshold,
        )

        detections: list[Detection] = []
        if len(indices) > 0:
            # OpenCV NMSBoxes returns a flat array in newer versions
            if hasattr(indices, "flatten"):
                indices = indices.flatten()
            for i in indices:
                x1_, y1_, x2_, y2_ = boxes_xyxy[i]
                cid = int(class_ids[i])
                detections.append(Detection(
                    bbox=(int(x1_), int(y1_), int(x2_), int(y2_)),
                    confidence=float(class_confs[i]),
                    class_id=cid,
                    class_name=COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else "unknown",
                ))

        return detections
