"""Executable artifact generation and deterministic validation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from rationaleops.models import (
    ArtifactCheck,
    DecisionContract,
    TruthState,
)


class ArtifactGenerationError(ValueError):
    """Raised when evidence is not authoritative enough for an artifact."""


def generate_active_window_test(
    contract: DecisionContract,
    *,
    as_of_date: date = date(2026, 7, 23),
) -> str:
    """Generate a self-contained dbt-style singular SQL acceptance test."""

    if contract.status is not TruthState.CONFIRMED:
        raise ArtifactGenerationError(
            "an executable artifact requires a CONFIRMED contract"
        )
    if not contract.exceptions:
        raise ArtifactGenerationError(
            "the active-window artifact requires an explicit exception"
        )

    postpaid_day_37 = as_of_date - timedelta(days=37)
    postpaid_day_38 = as_of_date - timedelta(days=38)
    prepaid_day_30 = as_of_date - timedelta(days=30)
    prepaid_day_31 = as_of_date - timedelta(days=31)

    return f"""-- Generated from Decision Contract: {contract.id}
-- A dbt singular test passes when this query returns zero rows.
WITH cases(case_id, activity_at, billing_type, expected_active) AS (
    VALUES
        ('postpaid_day_37', DATE '{postpaid_day_37}', 'postpaid', TRUE),
        ('postpaid_day_38', DATE '{postpaid_day_38}', 'postpaid', FALSE),
        ('prepaid_day_30',  DATE '{prepaid_day_30}', 'prepaid',  TRUE),
        ('prepaid_day_31',  DATE '{prepaid_day_31}', 'prepaid',  FALSE)
),
evaluated AS (
    SELECT
        case_id,
        expected_active,
        activity_at >= DATE '{as_of_date.isoformat()}' -
            CASE
                WHEN billing_type = 'prepaid' THEN INTERVAL 30 DAY
                ELSE INTERVAL 37 DAY
            END AS actual_active
    FROM cases
)
SELECT case_id, expected_active, actual_active
FROM evaluated
WHERE actual_active IS DISTINCT FROM expected_active;
"""


def run_sql_acceptance_test(
    sql: str,
    *,
    artifact_path: str = "<memory>",
) -> ArtifactCheck:
    """Run a read-only generated test in an isolated in-memory DuckDB."""

    connection = duckdb.connect(":memory:")
    try:
        rows = connection.execute(sql).fetchall()
    finally:
        connection.close()
    failing_rows = tuple(tuple(str(value) for value in row) for row in rows)
    return ArtifactCheck(
        artifact_path=artifact_path,
        passed=not failing_rows,
        failing_rows=failing_rows,
    )


def write_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
