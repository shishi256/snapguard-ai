"""
Privacy Risk Engine for SnapGuard AI.
Calculates risk level from detection results using temporal smoothing
to avoid false positives from single-frame noise.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from app.config import RiskLevel
from app.inference.base_backend import Detection, InferenceResult

log = logging.getLogger("SnapGuard AI")


@dataclass
class RiskAssessment:
    """Result of a privacy risk assessment for one frame."""
    risk_level: str = RiskLevel.UNKNOWN
    people_count: int = 0
    primary_user_detected: bool = False
    additional_persons: int = 0
    shoulder_surf_suspected: bool = False
    confidence: float = 0.0
    message: str = ""
    action_required: bool = False


class PrivacyRiskEngine:
    """
    Temporal privacy risk calculator.

    Rules:
    - 0 people detected      → UNKNOWN / LOW
    - 1 person detected      → SAFE
    - 2+ people detected     → MEDIUM (immediate)
    - Additional person present for > warning_delay_frames → HIGH
    - Shoulder-surfing heuristic: additional person bbox near screen center → additional flag

    Uses rolling deque buffers for temporal smoothing.
    """

    def __init__(
        self,
        warning_delay_frames: int = 15,
        cooldown_frames: int = 30,
        shoulder_surf_proximity: float = 0.25,
        smoothing_window: int = 5,
    ):
        self._warning_delay_frames    = warning_delay_frames
        self._cooldown_frames         = cooldown_frames
        self._shoulder_surf_proximity = shoulder_surf_proximity   # fraction of frame width

        # Rolling history of person counts (for smoothing)
        self._count_history: deque[int] = deque(maxlen=smoothing_window)

        # Consecutive frames with additional person
        self._additional_person_frame_count: int = 0

        # Consecutive frames with NO additional person (for cooldown)
        self._calm_frame_count: int = 0

        # Current persisted risk level
        self._current_risk: str = RiskLevel.UNKNOWN

        # Frame dimensions (set on first frame)
        self._frame_w: int = 640
        self._frame_h: int = 480

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_config(
        self,
        warning_delay_frames: Optional[int] = None,
        cooldown_frames: Optional[int] = None,
        shoulder_surf_proximity: Optional[float] = None,
    ):
        if warning_delay_frames is not None:
            self._warning_delay_frames = warning_delay_frames
        if cooldown_frames is not None:
            self._cooldown_frames = cooldown_frames
        if shoulder_surf_proximity is not None:
            self._shoulder_surf_proximity = shoulder_surf_proximity

    def assess(self, result: InferenceResult) -> RiskAssessment:
        """
        Assess privacy risk for the latest inference result.
        Returns a RiskAssessment.
        """
        if result.frame_width:
            self._frame_w = result.frame_width
            self._frame_h = result.frame_height

        # Filter to persons only
        persons = [d for d in result.detections if d.class_id == 0]
        count   = len(persons)

        # Update rolling count
        self._count_history.append(count)
        smoothed_count = round(sum(self._count_history) / len(self._count_history))

        additional = max(0, smoothed_count - 1)
        primary    = smoothed_count >= 1

        # Temporal tracking
        if additional > 0:
            self._additional_person_frame_count += 1
            self._calm_frame_count = 0
        else:
            self._calm_frame_count += 1
            if self._calm_frame_count >= self._cooldown_frames:
                self._additional_person_frame_count = 0

        # Risk determination
        risk = self._determine_risk(smoothed_count, additional)
        self._current_risk = risk

        # Shoulder-surfing check
        shoulder_surf = False
        if additional > 0 and persons:
            shoulder_surf = self._check_shoulder_surf(persons)

        # Build message
        msg, action = self._build_message(risk, smoothed_count, shoulder_surf)

        return RiskAssessment(
            risk_level=risk,
            people_count=smoothed_count,
            primary_user_detected=primary,
            additional_persons=additional,
            shoulder_surf_suspected=shoulder_surf,
            confidence=self._risk_confidence(smoothed_count),
            message=msg,
            action_required=action,
        )

    def get_current_risk(self) -> str:
        return self._current_risk

    def reset(self):
        self._count_history.clear()
        self._additional_person_frame_count = 0
        self._calm_frame_count = 0
        self._current_risk = RiskLevel.UNKNOWN

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _determine_risk(self, count: int, additional: int) -> str:
        if count == 0:
            return RiskLevel.LOW        # Nobody visible — unknown / low

        if count == 1:
            return RiskLevel.SAFE       # Only the user

        # count >= 2
        if self._additional_person_frame_count >= self._warning_delay_frames:
            return RiskLevel.HIGH       # Sustained additional presence
        else:
            return RiskLevel.MEDIUM     # Just appeared

    def _check_shoulder_surf(self, persons: list[Detection]) -> bool:
        """
        Heuristic: check if any bounding box (other than the largest one,
        which we assume is the primary user) is near the horizontal center
        of the frame — the region most likely facing the screen.
        """
        if not persons:
            return False

        # Sort by bbox area; largest assumed to be primary user
        def bbox_area(d: Detection) -> int:
            x1, y1, x2, y2 = d.bbox
            return max(0, (x2 - x1) * (y2 - y1))

        sorted_persons = sorted(persons, key=bbox_area, reverse=True)
        secondary = sorted_persons[1:]   # all except presumed primary

        cx_frame = self._frame_w / 2
        prox_px  = self._shoulder_surf_proximity * self._frame_w

        for d in secondary:
            x1, _, x2, _ = d.bbox
            cx_person = (x1 + x2) / 2
            if abs(cx_person - cx_frame) <= prox_px:
                return True

        return False

    @staticmethod
    def _risk_confidence(count: int) -> float:
        """Simple heuristic confidence value (not a calibrated probability)."""
        if count == 0:
            return 0.5
        if count == 1:
            return 0.95
        return min(0.99, 0.70 + count * 0.05)

    @staticmethod
    def _build_message(risk: str, count: int, shoulder_surf: bool) -> tuple[str, bool]:
        action = False
        if risk == RiskLevel.SAFE:
            msg = "Only you are visible. Privacy is protected."
        elif risk == RiskLevel.LOW:
            msg = "No person detected. Monitoring..."
        elif risk == RiskLevel.MEDIUM:
            msg = f"{count} people detected. Potential privacy risk."
            action = True
        elif risk == RiskLevel.HIGH:
            msg = "⚠ Sustained additional presence detected. High privacy risk!"
            if shoulder_surf:
                msg += " Potential shoulder-surfing detected."
            action = True
        else:
            msg = "Initializing..."
        return msg, action
