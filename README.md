# 🛡 SnapGuard AI

### On-Device AI Privacy Protection for Snapdragon-Powered PCs

> *"Your laptop. Your data. Your privacy."*

**Snapdragon AI Lab Build & Present Challenge Entry**

---

## 🎯 Problem

Modern laptops are used in open environments — cafés, airports, offices, co-working spaces.
Shoulder-surfing (someone reading your screen over your shoulder) is a real and growing privacy threat.

**Existing solutions:**
- Privacy screen filters (physical, inflexible)
- Manual screen locking (reactive, slow)
- No AI-powered, real-time, local solution exists

---

## 💡 Solution

**SnapGuard AI** uses on-device computer vision to continuously monitor the area around the user
via webcam. When additional people are detected near the user's workspace, the system immediately
alerts the user and can automatically activate privacy protection — all without sending a single
frame to the cloud.

```
Webcam → Frame capture → On-device AI → Person detection → Privacy risk engine → Alert
```

---

## ✨ Features

| Feature | Status |
|---------|--------|
| Real-time person detection | ✅ |
| Privacy risk assessment | ✅ |
| Shoulder-surfing heuristic | ✅ |
| Temporal smoothing (no false positives) | ✅ |
| Privacy Mode with auto-activation | ✅ |
| Local ONNX inference (CPU) | ✅ |
| Qualcomm AI Hub integration interface | ✅ |
| Snapdragon NPU backend (stub, ready to activate) | ✅ |
| Performance benchmark | ✅ |
| Offline operation | ✅ |
| Demo mode | ✅ |
| SQLite settings persistence | ✅ |
| Sensitive content detection (experimental) | ✅ |
| Professional dark UI | ✅ |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SnapGuard AI                              │
├─────────────────────────────────────────────────────────────────┤
│  Webcam (OpenCV)                                                 │
│      ↓                                                           │
│  CameraWorker (QThread)  ──→  InferenceWorker (QThread)          │
│                                    ↓                             │
│             ┌──────────────────────────────────┐                 │
│             │      AIInferenceBackend           │                 │
│             │  ┌─────────────┐  ┌────────────┐ │                 │
│             │  │LocalONNX    │  │Qualcomm    │ │                 │
│             │  │Backend      │  │Backend     │ │                 │
│             │  │(ONNX Runtime│  │(QNN/NPU)   │ │                 │
│             │  │CPU/GPU)     │  │            │ │                 │
│             │  └─────────────┘  └────────────┘ │                 │
│             └──────────────────────────────────┘                 │
│                          ↓                                       │
│              YOLOv8n Person Detection                            │
│                          ↓                                       │
│              PrivacyRiskEngine                                   │
│              (temporal smoothing + shoulder-surf heuristic)      │
│                          ↓                                       │
│              PrivacyModeManager                                  │
│                          ↓                                       │
│              PySide6 UI (dark theme, real-time updates)          │
└─────────────────────────────────────────────────────────────────┘
```

### Qualcomm AI Hub Model Flow

```
YOLOv8n (source model)
        ↓
  Qualcomm AI Hub
  ┌──────────────────────────┐
  │ • Compilation            │
  │ • Optimization           │
  │ • Profiling              │
  │ • Quantization           │
  └──────────────────────────┘
        ↓
  Snapdragon-optimized ONNX
        ↓
  QNN Execution Provider / QAIRT
        ↓
  Local inference on Snapdragon NPU
        ↓
  SnapGuard AI (QualcommBackend)
```

---

## 🧰 Technology Stack

| Component | Technology |
|-----------|-----------|
| GUI | PySide6 (Qt for Python) |
| Computer Vision | OpenCV |
| AI Inference | ONNX Runtime |
| Detection Model | YOLOv8n (ONNX) |
| Qualcomm Integration | Qualcomm AI Hub + QNN |
| Data Storage | SQLite |
| System Monitoring | psutil |
| Language | Python 3.11+ |

---

## 🤖 AI Model

**YOLOv8n** — Ultralytics YOLO v8 Nano

- Architecture: CSPDarknet + SPPF + PANet
- Input: 640×640 RGB
- Model size: ~6 MB (ONNX)
- Inference: CPU ~30-80ms, Snapdragon NPU ~5-15ms (estimated)
- License: AGPL-3.0 (see MODEL_LICENSES.md)
- Qualcomm AI Hub ID: `yolov8_det`

Only the **person class (class 0)** is used for privacy detection.

---

## ⚡ Qualcomm AI Hub Integration

The application is architecturally ready for Snapdragon NPU acceleration.

**Current state (dev machine):**
- `LocalONNXBackend` — ONNX Runtime on CPU
- Clearly labeled as "Development / Compatibility Mode"

**On Snapdragon PC:**
- `QualcommBackend` — QNN Execution Provider → Hexagon NPU
- Expected latency: ~5-15ms vs ~50ms on CPU
- See `docs/QUALCOMM_AI_HUB.md` for complete setup guide

**The QualcommBackend contains clearly marked `# INTEGRATION POINT` comments**
so activating Snapdragon NPU requires only filling in the QNN session code —
not rewriting the entire application.

---

## 🔒 Privacy Architecture

| Aspect | Implementation |
|--------|---------------|
| Frame processing | 100% local, on-device |
| Frame storage | Never saved by default |
| Cloud upload | Zero — no frames ever sent |
| Internet requirement | Only for initial model download |
| Offline operation | Full functionality after setup |
| Settings | SQLite (local only) |
| API tokens | Environment variables only, never in code |

---

## 📦 Installation

### Requirements
- Python 3.11+
- pip / venv
- Webcam (built-in or USB)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/snapguard-ai
cd snapguard-ai

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate     # macOS/Linux
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download the AI model
python scripts/download_model.py
```

---

## ▶ Running the Application

```bash
# Normal mode
python app/main.py

# Demo mode (shows simulated threat scenario)
python app/main.py --demo

# Open directly on performance page
python app/main.py --page performance

# Open directly on settings
python app/main.py --page settings
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_privacy_engine.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

---

## ⚡ Benchmarking

Run from the Performance page in the app, or programmatically:

```python
from app.inference.model_manager import ModelManager
from app.performance.benchmark import BenchmarkRunner

mgr = ModelManager()
mgr.initialize()
runner = BenchmarkRunner(mgr.get_backend())
runner.run(duration_sec=10, done_cb=lambda r: print(r.summary_text()))
```

---

## 🗂 Project Structure

```
snapguard-ai/
├── app/
│   ├── main.py                    # Entry point
│   ├── config.py                  # Settings, paths, constants
│   ├── ui/
│   │   ├── main_window.py         # Sidebar nav shell
│   │   ├── dashboard.py           # Status cards
│   │   ├── live_protection.py     # Camera + detection
│   │   ├── privacy_mode.py        # Privacy alerts
│   │   ├── performance.py         # Metrics + benchmark
│   │   ├── settings.py            # Configuration
│   │   └── about.py               # App info + privacy statement
│   ├── camera/
│   │   └── camera_manager.py      # Non-blocking QThread camera
│   ├── inference/
│   │   ├── base_backend.py        # Abstract AIInferenceBackend
│   │   ├── onnx_backend.py        # LocalONNXBackend (ONNX Runtime)
│   │   ├── qualcomm_backend.py    # QualcommBackend (Snapdragon NPU stub)
│   │   └── model_manager.py       # Backend selector + model loader
│   ├── privacy/
│   │   ├── privacy_engine.py      # Risk calculation + temporal smoothing
│   │   ├── sensitive_content.py   # OCR-based sensitive content detector
│   │   └── privacy_mode.py        # State machine + actions
│   ├── performance/
│   │   └── benchmark.py           # Inference benchmark runner
│   └── utils/
│       ├── logging.py             # Rotating file logger
│       └── system_info.py         # Hardware detection
├── models/
│   ├── model_config.json          # Model configuration
│   └── yolov8n.onnx               # [Downloaded separately]
├── assets/styles/
│   └── dark_theme.qss             # Dark Qt stylesheet
├── docs/
│   └── QUALCOMM_AI_HUB.md         # Snapdragon integration guide
├── scripts/
│   └── download_model.py          # Model downloader
├── tests/
│   ├── test_privacy_engine.py
│   ├── test_inference.py
│   └── test_benchmark.py
├── requirements.txt
├── .env.example
├── .gitignore
├── MODEL_LICENSES.md
├── LICENSE
└── README.md
```

---

## 🚀 Future Improvements

- [ ] Windows OS-level screen privacy (using Windows Security APIs)
- [ ] Gaze estimation model for precise shoulder-surf detection
- [ ] Face recognition to learn "trusted" faces
- [ ] Snapdragon X Elite NPU benchmark comparison
- [ ] macOS Screen Recording API integration
- [ ] Mobile companion app (Android/iOS)
- [ ] Enterprise policy management
- [ ] Encrypted local event log
- [ ] Model quantization (INT8) for further speed improvement

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

YOLOv8n model: AGPL-3.0 by Ultralytics — see [MODEL_LICENSES.md](MODEL_LICENSES.md)

---

## 🏆 Competition

**Snapdragon AI Lab Build & Present Challenge**

SnapGuard AI demonstrates how Qualcomm Snapdragon AI technology enables
privacy-preserving, on-device computer vision — protecting users without
ever compromising their data.
