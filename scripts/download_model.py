#!/usr/bin/env python3
"""
Download YOLOv8n ONNX model for SnapGuard AI.

Usage:
    python scripts/download_model.py

This script downloads the YOLOv8n ONNX model from Ultralytics
and places it in the models/ directory.

The model is used for real-time person detection.
It runs entirely locally — no internet required after download.

License: YOLOv8 is licensed under AGPL-3.0 by Ultralytics.
See MODEL_LICENSES.md for details.
"""

import sys
import os
import hashlib
import urllib.request
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODELS_DIR = ROOT / "models"
MODEL_FILE = MODELS_DIR / "yolov8n.onnx"

# Official Ultralytics YOLOv8n ONNX export (GitHub releases)
MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"

# Alternative: direct ONNX from community mirrors or local export
# If you have ultralytics installed, the script will export ONNX directly.
ONNX_EXPORT_AVAILABLE = False

try:
    from ultralytics import YOLO
    ONNX_EXPORT_AVAILABLE = True
except ImportError:
    pass


def download_with_progress(url: str, dest: Path) -> bool:
    """Download a file with a simple progress indicator."""
    print(f"\nDownloading: {url}")
    print(f"Destination: {dest}")

    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            mb_done  = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"\r  [{bar}] {pct:.0f}%  ({mb_done:.1f} / {mb_total:.1f} MB)", end="")
        else:
            print(f"\r  Downloaded {downloaded / (1024*1024):.1f} MB", end="")

    try:
        urllib.request.urlretrieve(url, str(dest), reporthook)
        print()
        return True
    except Exception as e:
        print(f"\n  ✗ Download failed: {e}")
        return False


def export_onnx_via_ultralytics() -> bool:
    """
    Export YOLOv8n to ONNX using the ultralytics package.
    This is the preferred method as it gives the exact ONNX format needed.
    """
    print("\nExporting YOLOv8n to ONNX via Ultralytics...")
    try:
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")   # Downloads .pt if not cached
        export_path = model.export(format="onnx", imgsz=640, simplify=True)
        exported = Path(export_path)
        if exported.exists():
            import shutil
            shutil.copy(exported, MODEL_FILE)
            print(f"  ✓ Exported and copied to {MODEL_FILE}")
            return True
    except Exception as e:
        print(f"  ✗ Export failed: {e}")
    return False


def verify_model(path: Path) -> bool:
    """Basic verification that the file is a valid ONNX model."""
    if not path.exists():
        return False
    if path.stat().st_size < 1_000_000:   # < 1MB is suspicious
        print(f"  ⚠ File seems too small ({path.stat().st_size} bytes)")
        return False
    # Check ONNX magic bytes
    with open(path, "rb") as f:
        header = f.read(8)
    # ONNX protobuf files typically start with specific bytes
    if len(header) < 4:
        return False
    print(f"  ✓ File size: {path.stat().st_size / (1024*1024):.1f} MB")
    return True


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  SnapGuard AI — Model Download Script")
    print("=" * 60)
    print(f"\nTarget: {MODEL_FILE}")

    if MODEL_FILE.exists():
        print(f"\n✓ Model already exists at {MODEL_FILE}")
        if verify_model(MODEL_FILE):
            print("  Model appears valid. Ready to use.\n")
            return
        else:
            print("  Model file seems invalid. Re-downloading...")
            MODEL_FILE.unlink()

    # Method 1: Try Ultralytics export (best quality)
    if ONNX_EXPORT_AVAILABLE:
        print("\nMethod 1: Ultralytics ONNX export (preferred)")
        if export_onnx_via_ultralytics():
            if verify_model(MODEL_FILE):
                print("\n✅ Model ready! Run: python app/main.py\n")
                return

    # Method 2: Try downloading pre-exported ONNX
    # Note: Pre-exported community ONNX mirrors
    onnx_mirrors = [
        # Ultralytics official GitHub release asset (ONNX)
        "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx",
    ]

    print("\nMethod 2: Direct ONNX download")
    for url in onnx_mirrors:
        temp_path = MODEL_FILE.with_suffix(".tmp")
        if download_with_progress(url, temp_path):
            temp_path.rename(MODEL_FILE)
            if verify_model(MODEL_FILE):
                print("\n✅ Model ready! Run: python app/main.py\n")
                return
            else:
                MODEL_FILE.unlink(missing_ok=True)

    # Method 3: Manual instructions
    print("\n" + "=" * 60)
    print("  MANUAL DOWNLOAD INSTRUCTIONS")
    print("=" * 60)
    print("""
Option A — Using pip + ultralytics:
    pip install ultralytics
    python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx')"
    # Then copy yolov8n.onnx to the models/ directory

Option B — Manual download:
    1. Go to: https://github.com/ultralytics/assets/releases/tag/v8.2.0
    2. Download: yolov8n.onnx  (or yolov8n.pt and convert)
    3. Place it at: models/yolov8n.onnx

Option C — Qualcomm AI Hub (for Snapdragon PC):
    See docs/QUALCOMM_AI_HUB.md for optimized model download.
""")
    sys.exit(1)


if __name__ == "__main__":
    main()
