"""
Sensitive Content Detector for SnapGuard AI.
Performs basic local pattern matching to identify potentially sensitive
text patterns in captured frames.

Note: This is an experimental feature. Accuracy depends on
image quality and OCR capabilities.
"""

import re
import logging
from typing import Optional

import numpy as np

log = logging.getLogger("SnapGuard AI")

# Regular expressions for common sensitive patterns
SENSITIVE_PATTERNS = {
    "credit_card": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"        # Visa
        r"5[1-5][0-9]{14}|"                       # Mastercard
        r"3[47][0-9]{13}|"                        # Amex
        r"(?:6011|65[0-9]{2})[0-9]{12})\b"       # Discover
    ),
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "phone": re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "password_like": re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|token|api[_\-]?key)\s*[:=]\s*\S+"
    ),
    "ssn": re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
    ),
    "ip_address": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
}

PATTERN_LABELS = {
    "credit_card":    "Credit Card Number",
    "email":          "Email Address",
    "phone":          "Phone Number",
    "password_like":  "Password / API Key",
    "ssn":            "Social Security Number",
    "ip_address":     "IP Address",
}


class SensitiveContentDetector:
    """
    Experimental sensitive content detector.
    Uses OCR + regex to flag potentially sensitive text in camera frames.

    Requires: pytesseract + Tesseract binary (optional).
    Falls back gracefully if Tesseract is not installed.
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self._tesseract_available = self._check_tesseract()
        if enabled and not self._tesseract_available:
            log.warning(
                "[SensitiveContent] Tesseract not found. "
                "Install Tesseract OCR for sensitive content detection. "
                "Feature will be disabled."
            )

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def is_available(self) -> bool:
        return self._tesseract_available

    def analyze_frame(self, frame: np.ndarray) -> dict:
        """
        Analyze a camera frame for sensitive content.
        Returns a dict with findings.

        NOTE: Frames are processed in memory only.
        Frames are NOT saved to disk by this function.
        """
        result = {
            "enabled": self._enabled,
            "sensitive_detected": False,
            "patterns_found": [],
            "raw_text_length": 0,
            "error": None,
        }

        if not self._enabled:
            return result

        if not self._tesseract_available:
            result["error"] = "Tesseract OCR not available"
            return result

        try:
            import pytesseract
            from PIL import Image

            # Downsample for speed
            import cv2
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            pil_img = Image.fromarray(gray)

            text = pytesseract.image_to_string(pil_img, config="--psm 6")
            result["raw_text_length"] = len(text)

            for pattern_key, pattern_re in SENSITIVE_PATTERNS.items():
                if pattern_re.search(text):
                    result["patterns_found"].append(PATTERN_LABELS[pattern_key])
                    result["sensitive_detected"] = True

        except Exception as e:
            log.debug(f"[SensitiveContent] OCR error: {e}")
            result["error"] = str(e)

        return result
