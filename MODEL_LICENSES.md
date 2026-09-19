# SnapGuard AI — Model Licenses

All AI models used in this project are documented below.
Please verify license compliance before commercial distribution.

---

## YOLOv8n (Primary Detection Model)

| Field | Value |
|-------|-------|
| **Model Name** | YOLOv8 Nano (yolov8n) |
| **Source** | Ultralytics — https://github.com/ultralytics/ultralytics |
| **License** | **AGPL-3.0** |
| **Download** | https://github.com/ultralytics/assets/releases |
| **Intended Usage** | Person detection for privacy protection demo |
| **Classes Used** | Person (class 0) only |
| **Input Format** | ONNX, 640×640 RGB |
| **Competition Use** | Permitted for demonstration and research |
| **Commercial Use** | Requires Ultralytics Enterprise License |

### AGPL-3.0 Summary
The AGPL-3.0 license permits:
- ✅ Personal use
- ✅ Research and academic use
- ✅ Competition demonstrations
- ⚠️ Any network-accessible service must release source code
- ❌ Closed-source commercial products (requires Enterprise license)

For competition demonstration purposes, AGPL-3.0 is acceptable.
If this project is commercialized, obtain an [Ultralytics Enterprise License](https://ultralytics.com/license).

---

## Alternative: MediaPipe Person Detection

| Field | Value |
|-------|-------|
| **Model Name** | MediaPipe BlazePose / Person Detection |
| **Source** | Google — https://developers.google.com/mediapipe |
| **License** | Apache 2.0 |
| **Intended Usage** | Alternative face/person detection |
| **Notes** | Apache 2.0 is more permissive than AGPL-3.0 |

If AGPL-3.0 is a concern, MediaPipe models (Apache 2.0) can replace YOLOv8n.
The `LocalONNXBackend` interface supports any ONNX person detection model.

---

## Qualcomm AI Hub Optimized Models

Models optimized through Qualcomm AI Hub are subject to:
- The original model's license (e.g., AGPL-3.0 for YOLOv8)
- Qualcomm AI Hub Terms of Service: https://aihub.qualcomm.com/legal/terms

---

## Attribution

This project uses the following open-source libraries. Each retains its own license.
See `requirements.txt` for versions.

| Library | License |
|---------|---------|
| PySide6 | LGPL-3.0 / GPL |
| OpenCV | Apache 2.0 |
| ONNX Runtime | MIT |
| NumPy | BSD-3-Clause |
| psutil | BSD-3-Clause |
| Pillow | HPND |
| python-dotenv | BSD-3-Clause |
| pytest | MIT |
