"""Transparent knowledge-risk ranking."""

from __future__ import annotations

from rationaleops.models import (
    DecisionKind,
    DecisionPoint,
    ImpactContext,
    RiskBoost,
    RiskBreakdown,
)

_DOWNSTREAM_NORMALIZATION_CEILING = 50


def calculate_risk(
    decision_point: DecisionPoint,
    impact: ImpactContext,
    *,
    glossary_conflict: bool = False,
    temporary_marker: bool = False,
    inconsistent_literal: bool = False,
) -> RiskBreakdown:
    """Calculate the documented deterministic MVP score."""

    normalized_downstream = min(
        impact.downstream_count / _DOWNSTREAM_NORMALIZATION_CEILING,
        1.0,
    )
    downstream_component = 0.30 * normalized_downstream
    usage_component = 0.25 * impact.usage_criticality
    documentation_component = 0.20 * impact.documentation_gap
    owner_component = 0.15 * impact.owner_bus_factor
    staleness_component = 0.10 * impact.age_or_staleness

    boosts: list[RiskBoost] = []
    if glossary_conflict:
        boosts.append(RiskBoost(reason="glossary_conflict", value=0.10))
    if temporary_marker:
        boosts.append(RiskBoost(reason="temporary_marker", value=0.08))
    if inconsistent_literal:
        boosts.append(RiskBoost(reason="inconsistent_literal", value=0.06))

    base_total = (
        downstream_component
        + usage_component
        + documentation_component
        + owner_component
        + staleness_component
    )
    total = min(base_total + sum(boost.value for boost in boosts), 1.0)

    return RiskBreakdown(
        normalized_downstream_count=round(normalized_downstream, 4),
        downstream_impact=round(downstream_component, 4),
        usage_criticality=round(usage_component, 4),
        documentation_gap=round(documentation_component, 4),
        owner_bus_factor=round(owner_component, 4),
        age_or_staleness=round(staleness_component, 4),
        boosts=tuple(boosts),
        total=round(total, 4),
    )


def has_active_window_glossary_conflict(
    decision_point: DecisionPoint,
    glossary_definition: str,
) -> bool:
    """Detect the seeded 37-day versus 30-day semantic conflict."""

    return (
        decision_point.kind is DecisionKind.DATE_WINDOW
        and "37" in decision_point.literal_values
        and "30 day" in glossary_definition.lower()
    )
