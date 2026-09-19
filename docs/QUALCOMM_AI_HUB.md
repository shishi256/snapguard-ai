# Qualcomm AI Hub Integration Guide

## SnapGuard AI — Snapdragon NPU Optimization

This guide explains how to optimize SnapGuard AI's detection model
for Snapdragon-powered Windows PCs using Qualcomm AI Hub.

---

## 1. Create a Qualcomm AI Hub Account

1. Go to [https://aihub.qualcomm.com](https://aihub.qualcomm.com)
2. Sign up with your email address
3. Verify your account

---

## 2. Generate an API Token

1. Log in to Qualcomm AI Hub
2. Navigate to **Account → API Tokens**
3. Click **Create Token**
4. Copy the token — you will not see it again

**Never commit your API token to version control.**

Store it in your `.env` file:
```
QAI_HUB_API_TOKEN=your_actual_token_here
```

---

## 3. Install the Qualcomm AI Hub SDK

```bash
pip install qai-hub qai-hub-models
```

Set your API token:
```bash
export QAI_HUB_API_TOKEN=your_actual_token_here
# or on Windows:
set QAI_HUB_API_TOKEN=your_actual_token_here
```

Configure the SDK:
```bash
qai-hub configure --api_token $QAI_HUB_API_TOKEN
```

---

## 4. List Available Snapdragon Devices

```bash
qai-hub list-devices
```

Example output:
```
Snapdragon X Elite CRD
Snapdragon 8 Gen 3 HDK
Snapdragon X Plus CRD
...
```

---

## 5. Select a Target Device

For Snapdragon-powered Windows PCs, use:
```
Snapdragon X Elite CRD
```

---

## 6. Upload / Use YOLOv8n on AI Hub

### Option A: Use Pre-optimized Model from AI Hub Models

```bash
python -c "
import qai_hub_models
from qai_hub_models.models.yolov8_det import Model
model = Model.from_pretrained()
print('Model loaded:', model)
"
```

### Option B: Export and Submit for Compilation

```python
import qai_hub
from ultralytics import YOLO
import torch

# Export YOLOv8n to ONNX
model = YOLO('yolov8n.pt')
model.export(format='onnx', imgsz=640)

# Submit to AI Hub for compilation
compile_job = qai_hub.submit_compile_job(
    model='yolov8n.onnx',
    device=qai_hub.Device('Snapdragon X Elite CRD'),
    input_specs={'images': ((1, 3, 640, 640), 'float32')},
    options='--target_runtime qnn_lib_aarch64_android',  # or onnx for Windows
)
print('Job ID:', compile_job.job_id)
```

---

## 7. Monitor and Download Optimized Model

```python
# Wait for compilation (or poll status)
compile_job.wait()

# Check status
print('Status:', compile_job.get_status())

# Download optimized model
target_model = compile_job.get_target_model()
target_model.download('models/yolov8n_snapdragon.onnx')
print('Optimized model saved.')
```

---

## 8. Profile the Model on Snapdragon

```python
profile_job = qai_hub.submit_profile_job(
    model=target_model,
    device=qai_hub.Device('Snapdragon X Elite CRD'),
)
profile_job.wait()

profile_data = profile_job.download_profile()
print('Inference time:', profile_data['execution_summary']['estimated_inference_time'])
print('Target runtime: Hexagon NPU')
```

---

## 9. Use the Optimized Model in SnapGuard AI

### Method A: ONNX with QNN Execution Provider

```python
import onnxruntime as ort

providers = [
    (
        "QNNExecutionProvider",
        {
            "backend_path": "QnnHtp.dll",   # Hexagon TensorProcessor
        }
    ),
    "CPUExecutionProvider",   # fallback
]

session = ort.InferenceSession(
    'models/yolov8n_snapdragon.onnx',
    providers=providers
)
```

### Method B: Enable QualcommBackend in SnapGuard

1. Install QNN SDK on your Snapdragon PC
2. Set in Settings → AI Backend → **Qualcomm AI Runtime**
3. Place the optimized model in `models/`
4. Update `models/model_config.json`:
   ```json
   {
     "model_file": "yolov8n_snapdragon.onnx"
   }
   ```
5. Restart SnapGuard AI

The `QualcommBackend` class in `app/inference/qualcomm_backend.py`
contains clearly marked `# INTEGRATION POINT` comments for adding
QNN session initialization.

---

## 10. Integration Points in SnapGuard AI

| File | Section | Description |
|------|---------|-------------|
| `app/inference/qualcomm_backend.py` | `load_model()` | Initialize QNN session |
| `app/inference/qualcomm_backend.py` | `infer()` | Run QNN inference |
| `app/inference/model_manager.py` | `initialize()` | Backend selection |
| `app/ui/settings.py` | Backend selector | UI configuration |
| `models/model_config.json` | `model_file` | Model file path |

---

## Security Notes

- Store `QAI_HUB_API_TOKEN` in environment variables only
- Never commit `.env` files to version control
- `.gitignore` already excludes `.env`
- Use `.env.example` as a template with placeholder values only

---

## References

- [Qualcomm AI Hub Documentation](https://app.aihub.qualcomm.com/docs/)
- [YOLOv8 on AI Hub](https://aihub.qualcomm.com/models/yolov8_det)
- [QNN SDK](https://developer.qualcomm.com/software/qualcomm-neural-processing-sdk)
- [ONNX Runtime QNN Provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)
- [Snapdragon X Elite Developer Kit](https://developer.qualcomm.com/hardware/snapdragon-x-elite)
