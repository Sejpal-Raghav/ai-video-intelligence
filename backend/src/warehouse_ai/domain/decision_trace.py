from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PredicateEvaluation(BaseModel):
    """Evaluation result for a specific predicate (Section 9.2 & 13)."""
    model_config = ConfigDict(extra="forbid")

    name: str
    evaluated_value: float | bool | str | None
    threshold: float | bool | str | None
    passed: bool
    contributing_track_ids: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StateTransition(BaseModel):
    """State machine transition record."""
    model_config = ConfigDict(extra="forbid")

    from_state: str
    to_state: str
    timestamp_ms: int
    reason: str
    predicates: list[PredicateEvaluation] = Field(default_factory=list)


class DecisionTrace(BaseModel):
    """Complete, proof-carrying deterministic decision trace for an event (Section 2.2 & 13)."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "decision-trace.v1"
    event_type: str
    primary_track_id: int
    associated_track_ids: list[int] = Field(default_factory=list)
    start_ms: int
    end_ms: int
    keyframe_ms: int

    # Quality indicators
    track_coverage: float
    interpolation_fraction: float
    median_detection_confidence: float
    track_quality: float
    evidence_quality: float

    # Kinematics & measurements
    measured_facts: dict[str, Any] = Field(default_factory=dict)
    state_transitions: list[StateTransition] = Field(default_factory=list)
    evaluations: list[PredicateEvaluation] = Field(default_factory=list)

    # Risk explanation factors
    risk_score: int
    risk_tier: str
    explanation: str
    formula_breakdown: dict[str, int] = Field(default_factory=dict)
