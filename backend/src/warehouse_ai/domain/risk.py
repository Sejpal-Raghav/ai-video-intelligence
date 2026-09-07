import math
from dataclasses import dataclass
from typing import Any

from warehouse_ai.domain.enums import EventType, RiskTier, ZoneSeverity
from warehouse_ai.domain.models import RiskPolicyConfig


def round_half_up(val: float) -> int:
    """Round to nearest integer with exact halves rounded upward (Section 11)."""
    return int(math.floor(val + 0.5))


def clamp(val: int, low: int = 0, high: int = 100) -> int:
    """Clamp integer value between low and high."""
    return min(high, max(low, val))


@dataclass(frozen=True)
class RiskCalculationResult:
    score: int
    tier: RiskTier
    base: int
    motion_bonus: int
    duration_bonus: int
    support_bonus: int
    zone_bonus: int
    explanation: str
    formula_breakdown: dict[str, int]


class RiskEngine:
    """Deterministic risk calculation and explanation policy (Section 11)."""

    def __init__(self, policy: RiskPolicyConfig) -> None:
        self.policy = policy

    def score_tier(self, score: int) -> RiskTier:
        for tier_name, (low, high) in self.policy.tiers.items():
            if low <= score <= high:
                return RiskTier(tier_name)
        if score < 0:
            return RiskTier.LOW
        return RiskTier.CRITICAL

    def calculate(
        self,
        event_type: EventType | str,
        peak_speed_hps: float = 0.0,
        duration_seconds: float = 0.0,
        outside_fraction: float = 0.0,
        zone_severity: ZoneSeverity | str = ZoneSeverity.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> RiskCalculationResult:
        ev_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        base = self.policy.bases.get(ev_type_str, 40)

        motion_bonus = 0
        duration_bonus = 0
        support_bonus = 0
        zone_bonus = 0

        # Zone severity bonus
        zone_str = zone_severity.value if isinstance(zone_severity, ZoneSeverity) else zone_severity
        zone_bonus = self.policy.zone_bonus.get(zone_str, 0)

        # Event-specific bonuses
        if ev_type_str in (EventType.DROP.value, EventType.FORCEFUL_RELEASE.value):
            motion_bonus = min(25, round_half_up(10.0 * max(0.0, peak_speed_hps - 1.25)))
        elif ev_type_str == EventType.DRAGGING.value:
            duration_bonus = min(25, round_half_up(17.0 * max(0.0, duration_seconds - 0.8)))
        elif ev_type_str in (EventType.PROHIBITED_ZONE.value, EventType.VISIBLE_SUPPORT_OVERHANG.value):
            duration_bonus = min(15, round_half_up(3.0 * max(0.0, duration_seconds - 1.0)))
            if ev_type_str == EventType.VISIBLE_SUPPORT_OVERHANG.value:
                if 0.20 <= outside_fraction < 0.40:
                    support_bonus = 10
                elif outside_fraction >= 0.40:
                    support_bonus = 25

        total_score = clamp(base + motion_bonus + duration_bonus + support_bonus + zone_bonus, 0, 100)
        tier = self.score_tier(total_score)

        breakdown = {
            "base": base,
            "motion_bonus": motion_bonus,
            "duration_bonus": duration_bonus,
            "support_bonus": support_bonus,
            "zone_bonus": zone_bonus,
            "total": total_score,
        }

        explanation = self._build_explanation(
            ev_type_str=ev_type_str,
            base=base,
            motion_bonus=motion_bonus,
            duration_bonus=duration_bonus,
            support_bonus=support_bonus,
            zone_bonus=zone_bonus,
            total_score=total_score,
            peak_speed_hps=peak_speed_hps,
            duration_seconds=duration_seconds,
            outside_fraction=outside_fraction,
            zone_severity=zone_str,
            metadata=metadata or {},
        )

        return RiskCalculationResult(
            score=total_score,
            tier=tier,
            base=base,
            motion_bonus=motion_bonus,
            duration_bonus=duration_bonus,
            support_bonus=support_bonus,
            zone_bonus=zone_bonus,
            explanation=explanation,
            formula_breakdown=breakdown,
        )

    def _build_explanation(
        self,
        ev_type_str: str,
        base: int,
        motion_bonus: int,
        duration_bonus: int,
        support_bonus: int,
        zone_bonus: int,
        total_score: int,
        peak_speed_hps: float,
        duration_seconds: float,
        outside_fraction: float,
        zone_severity: str,
        metadata: dict[str, Any],
    ) -> str:
        parts: list[str] = [f"Base {base}"]
        if motion_bonus > 0:
            parts.append(f"motion {motion_bonus}")
        if duration_bonus > 0:
            parts.append(f"duration {duration_bonus}")
        if support_bonus > 0:
            parts.append(f"support-overhang {support_bonus}")
        if zone_bonus > 0:
            parts.append(f"{zone_severity.lower()}-zone {zone_bonus}")
        formula_str = f"{' + '.join(parts)} = {total_score}"

        # Context details
        if ev_type_str == EventType.FORCEFUL_RELEASE.value:
            h_disp = metadata.get("horizontal_displacement_w", 0.0)
            return (
                f"Potential forceful lateral release (throw-like motion): package reached {peak_speed_hps:.1f} package-heights/s, "
                f"moved {h_disp:.1f} package-widths laterally, and settled after impact candidate. {formula_str}."
            )
        elif ev_type_str == EventType.DROP.value:
            v_disp = metadata.get("vertical_displacement_h", 0.0)
            return (
                f"Drop event: package released and dropped {v_disp:.1f} package-heights, "
                f"reached {peak_speed_hps:.1f} package-heights/s downward velocity before impact and settle. {formula_str}."
            )
        elif ev_type_str == EventType.DRAGGING.value:
            return (
                f"Dragging event: package sustained continuous floor-level contact while handled for {duration_seconds:.1f}s without equipment support. {formula_str}."
            )
        elif ev_type_str == EventType.VISIBLE_SUPPORT_OVERHANG.value:
            return (
                f"Visible support overhang: package contact footprint outside calibrated support surface by {outside_fraction * 100:.0f}% for {duration_seconds:.1f}s. {formula_str}."
            )
        elif ev_type_str == EventType.PROHIBITED_ZONE.value:
            return (
                f"Prohibited zone violation: stationary package remained inside marked prohibited boundary for {duration_seconds:.1f}s. {formula_str}."
            )
        elif ev_type_str == EventType.STANDING_ON_PRODUCT.value:
            return (
                f"Standing on product: person ankle contact maintained inside package boundary for {duration_seconds:.1f}s. {formula_str}."
            )

        return f"{ev_type_str}: {formula_str}."
