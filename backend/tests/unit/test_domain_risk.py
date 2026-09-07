import pytest

from warehouse_ai.domain.enums import EventType, RiskTier, ZoneSeverity
from warehouse_ai.domain.models import RiskPolicyConfig
from warehouse_ai.domain.risk import RiskEngine, round_half_up


@pytest.fixture
def risk_policy() -> RiskPolicyConfig:
    return RiskPolicyConfig(
        schema_version="risk-policy.v1",
        bases={
            "DROP": 45,
            "FORCEFUL_RELEASE": 55,
            "DRAGGING": 40,
            "VISIBLE_SUPPORT_OVERHANG": 35,
            "PROHIBITED_ZONE": 50,
            "STANDING_ON_PRODUCT": 45,
        },
        tiers={
            "LOW": (0, 39),
            "MEDIUM": (40, 59),
            "HIGH": (60, 79),
            "CRITICAL": (80, 100),
        },
        zone_bonus={"NORMAL": 0, "SENSITIVE": 10, "CRITICAL": 20},
    )


def test_round_half_up():
    assert round_half_up(8.4) == 8
    assert round_half_up(8.5) == 9
    assert round_half_up(8.6) == 9
    assert round_half_up(0.0) == 0


def test_blueprint_example_risk_calculation(risk_policy):
    """Test exact example from Section 11: Base 55 + motion 9 + critical-zone 20 = 84."""
    engine = RiskEngine(risk_policy)
    res = engine.calculate(
        event_type=EventType.FORCEFUL_RELEASE,
        peak_speed_hps=2.1,
        zone_severity=ZoneSeverity.CRITICAL,
        metadata={"horizontal_displacement_w": 1.2},
    )
    assert res.base == 55
    assert res.motion_bonus == 9  # 10 * (2.1 - 1.25) = 8.5 -> rounded half-up to 9
    assert res.zone_bonus == 20
    assert res.score == 84
    assert res.tier == RiskTier.CRITICAL
    assert "Base 55 + motion 9 + critical-zone 20 = 84" in res.explanation


def test_dragging_risk_calculation(risk_policy):
    engine = RiskEngine(risk_policy)
    # Drag for 2.5 seconds: duration bonus = round(17 * (2.5 - 0.8)) = round(28.9) -> capped at 25
    res = engine.calculate(
        event_type=EventType.DRAGGING,
        duration_seconds=2.5,
    )
    assert res.base == 40
    assert res.duration_bonus == 25
    assert res.score == 65
    assert res.tier == RiskTier.HIGH


def test_support_overhang_risk_calculation(risk_policy):
    engine = RiskEngine(risk_policy)
    # Outside fraction 0.30 -> bonus 10
    res = engine.calculate(
        event_type=EventType.VISIBLE_SUPPORT_OVERHANG,
        duration_seconds=1.5,
        outside_fraction=0.30,
    )
    assert res.base == 35
    assert res.support_bonus == 10
    assert res.duration_bonus == 2  # round(3 * 0.5) = 2
    assert res.score == 47
    assert res.tier == RiskTier.MEDIUM


def test_score_clamping(risk_policy):
    engine = RiskEngine(risk_policy)
    res = engine.calculate(
        event_type=EventType.FORCEFUL_RELEASE,
        peak_speed_hps=10.0,
        zone_severity=ZoneSeverity.CRITICAL,
    )
    # 55 + 25 + 20 = 100
    assert res.score == 100
    assert res.tier == RiskTier.CRITICAL
