from __future__ import annotations

from rationaleops.datahub_gateway import load_demo_context
from rationaleops.mining import mine_decision_points
from rationaleops.models import DecisionKind
from rationaleops.risk import (
    calculate_risk,
    has_active_window_glossary_conflict,
)


def test_risk_score_matches_documented_formula_and_boost() -> None:
    context = load_demo_context()
    point = next(
        point
        for point in mine_decision_points(
            context.sql,
            query_urn=context.query_urn,
            dataset_urn=context.dataset_urn,
        )
        if point.kind is DecisionKind.DATE_WINDOW
    )
    glossary = context.glossary[0].definition

    risk = calculate_risk(
        point,
        context.impact,
        glossary_conflict=has_active_window_glossary_conflict(
            point,
            glossary,
        ),
    )

    assert risk.normalized_downstream_count == 0.94
    assert risk.downstream_impact == 0.282
    assert risk.usage_criticality == 0.24
    assert risk.documentation_gap == 0.18
    assert risk.owner_bus_factor == 0.105
    assert risk.age_or_staleness == 0.055
    assert risk.total == 0.962
    assert [boost.reason for boost in risk.boosts] == [
        "glossary_conflict"
    ]
