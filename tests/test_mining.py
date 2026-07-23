from __future__ import annotations

import pytest

from rationaleops.datahub_gateway import load_demo_context
from rationaleops.mining import (
    DecisionPointMiningError,
    mine_decision_points,
)
from rationaleops.models import DecisionKind


def test_demo_query_produces_three_expected_decision_points() -> None:
    context = load_demo_context()

    points = mine_decision_points(
        context.sql,
        query_urn=context.query_urn,
        dataset_urn=context.dataset_urn,
        dialect=context.dialect,
    )

    assert len(points) == 3
    assert [point.kind for point in points] == [
        DecisionKind.DATE_WINDOW,
        DecisionKind.HARD_CODED_EXCLUSION,
        DecisionKind.HARD_CODED_EXCLUSION,
    ]
    assert points[0].referenced_fields == ("activity_at",)
    assert points[0].literal_values == ("37",)
    assert points[1].literal_values == ("DE",)
    assert points[2].literal_values == ("trial", "refunded")


def test_fingerprint_is_stable_across_formatting_and_interval_spelling() -> None:
    common = {
        "query_urn": "urn:li:query:test",
        "dataset_urn": (
            "urn:li:dataset:(urn:li:dataPlatform:postgres,test.table,PROD)"
        ),
    }
    first = mine_decision_points(
        "SELECT * FROM test.table "
        "WHERE activity_at >= current_date - interval '37 days'",
        **common,
    )
    second = mine_decision_points(
        "select * from TEST.TABLE where "
        "ACTIVITY_AT>=CURRENT_DATE-INTERVAL '37' DAY",
        **common,
    )

    assert first[0].normalized_sql == second[0].normalized_sql
    assert first[0].sql_fingerprint == second[0].sql_fingerprint


def test_query_without_where_has_no_candidates() -> None:
    assert (
        mine_decision_points(
            "SELECT * FROM test.table",
            query_urn="urn:li:query:test",
            dataset_urn=(
                "urn:li:dataset:"
                "(urn:li:dataPlatform:postgres,test.table,PROD)"
            ),
        )
        == []
    )


def test_invalid_sql_has_a_clear_domain_error() -> None:
    with pytest.raises(DecisionPointMiningError, match="unable to parse SQL"):
        mine_decision_points(
            "SELECT FROM WHERE",
            query_urn="urn:li:query:test",
            dataset_urn=(
                "urn:li:dataset:"
                "(urn:li:dataPlatform:postgres,test.table,PROD)"
            ),
        )
