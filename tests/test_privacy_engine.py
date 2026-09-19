"""
Tests for PrivacyRiskEngine — covers all risk scenarios and temporal smoothing.
"""
import pytest
from unittest.mock import MagicMock

from app.inference.base_backend import Detection, InferenceResult
from app.privacy.privacy_engine import PrivacyRiskEngine, RiskAssessment
from app.config import RiskLevel


def _make_result(person_count: int, w: int = 640, h: int = 480) -> InferenceResult:
    """Helper: build an InferenceResult with N persons detected."""
    detections = []
    for i in range(person_count):
        x1 = 50 + i * 150
        detections.append(Detection(
            bbox=(x1, 50, x1 + 100, 300),
            confidence=0.9,
            class_id=0,
            class_name="person",
        ))
    return InferenceResult(
        detections=detections,
        latency_ms=20.0,
        frame_width=w,
        frame_height=h,
    )


@pytest.fixture
def engine():
    return PrivacyRiskEngine(
        warning_delay_frames=5,
        cooldown_frames=10,
        shoulder_surf_proximity=0.25,
        smoothing_window=1,   # disable smoothing for deterministic tests
    )


class TestNoPersonDetected:
    def test_risk_is_low(self, engine):
        result = engine.assess(_make_result(0))
        assert result.risk_level == RiskLevel.LOW

    def test_people_count_is_zero(self, engine):
        result = engine.assess(_make_result(0))
        assert result.people_count == 0

    def test_primary_user_not_detected(self, engine):
        result = engine.assess(_make_result(0))
        assert result.primary_user_detected is False


class TestSinglePersonDetected:
    def test_risk_is_safe(self, engine):
        result = engine.assess(_make_result(1))
        assert result.risk_level == RiskLevel.SAFE

    def test_people_count_is_one(self, engine):
        result = engine.assess(_make_result(1))
        assert result.people_count == 1

    def test_primary_user_detected(self, engine):
        result = engine.assess(_make_result(1))
        assert result.primary_user_detected is True

    def test_no_additional_persons(self, engine):
        result = engine.assess(_make_result(1))
        assert result.additional_persons == 0

    def test_no_action_required(self, engine):
        result = engine.assess(_make_result(1))
        assert result.action_required is False


class TestMultiplePersonsDetected:
    def test_two_persons_medium_risk_initially(self, engine):
        result = engine.assess(_make_result(2))
        assert result.risk_level == RiskLevel.MEDIUM

    def test_additional_person_count(self, engine):
        result = engine.assess(_make_result(2))
        assert result.additional_persons == 1

    def test_action_required_medium(self, engine):
        result = engine.assess(_make_result(2))
        assert result.action_required is True

    def test_three_persons_multiple_additional(self, engine):
        result = engine.assess(_make_result(3))
        assert result.additional_persons == 2


class TestRiskEscalation:
    def test_escalates_to_high_after_delay(self, engine):
        """Additional person must be present for warning_delay_frames before HIGH."""
        for _ in range(4):
            r = engine.assess(_make_result(2))
            assert r.risk_level == RiskLevel.MEDIUM  # not yet

        r = engine.assess(_make_result(2))
        assert r.risk_level == RiskLevel.HIGH   # 5th frame → HIGH

    def test_high_risk_action_required(self, engine):
        for _ in range(5):
            result = engine.assess(_make_result(2))
        assert result.action_required is True


class TestRiskCooldown:
    def test_risk_de_escalates_after_cooldown(self, engine):
        # Escalate to HIGH
        for _ in range(5):
            engine.assess(_make_result(2))

        # Person leaves — wait cooldown
        for _ in range(10):
            engine.assess(_make_result(1))

        # Should now be SAFE
        result = engine.assess(_make_result(1))
        assert result.risk_level == RiskLevel.SAFE

    def test_counter_resets_on_person_return(self, engine):
        # Escalate
        for _ in range(5):
            engine.assess(_make_result(2))
        # Brief calm (not enough for cooldown)
        for _ in range(3):
            engine.assess(_make_result(1))
        # Person returns — should stay HIGH quickly
        result = engine.assess(_make_result(2))
        # After only 1 frame with person, medium
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


class TestReset:
    def test_reset_clears_state(self, engine):
        for _ in range(5):
            engine.assess(_make_result(2))
        engine.reset()
        result = engine.assess(_make_result(2))
        assert result.risk_level == RiskLevel.MEDIUM   # back to initial
