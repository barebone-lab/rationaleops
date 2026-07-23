"""Executable artifact generation and deterministic validation."""

from __future__ import annotations

import re
from datetime import date, timedelta
from difflib import unified_diff
from pathlib import Path

import duckdb
from sqlglot import exp, parse_one

from rationaleops.mining import normalize_expression
from rationaleops.models import (
    ArtifactCheck,
    DecisionContract,
    DecisionPoint,
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


def remove_decision_predicate(
    sql: str,
    decision_point: DecisionPoint,
    *,
    dialect: str = "postgres",
) -> str:
    """Remove one exact fingerprinted top-level predicate from a query."""

    statement = parse_one(sql, read=dialect)
    where = statement.args.get("where")
    if where is None:
        raise ArtifactGenerationError("query has no WHERE clause to patch")

    def split_and(expression: exp.Expression) -> list[exp.Expression]:
        if isinstance(expression, exp.And):
            return split_and(expression.this) + split_and(expression.expression)
        return [expression]

    predicates = split_and(where.this)
    remaining = [
        predicate
        for predicate in predicates
        if normalize_expression(predicate, dialect=dialect)
        != decision_point.normalized_sql
    ]
    if len(remaining) != len(predicates) - 1:
        raise ArtifactGenerationError(
            "the patch target must match exactly one WHERE predicate"
        )
    combined = remaining[0]
    for predicate in remaining[1:]:
        combined = exp.and_(combined, predicate, copy=False)
    statement.set("where", exp.Where(this=combined))
    return statement.sql(dialect=dialect, pretty=True) + ";\n"


def generate_remove_predicate_patch(
    contract: DecisionContract,
    *,
    original_sql: str,
    decision_point: DecisionPoint,
    dialect: str = "postgres",
) -> tuple[str, str]:
    """Generate the expired Germany-filter SQL and a reviewable diff."""

    if contract.status is not TruthState.EXPIRED:
        raise ArtifactGenerationError(
            "predicate removal requires a confirmed EXPIRED contract"
        )
    patched_sql = remove_decision_predicate(
        original_sql,
        decision_point,
        dialect=dialect,
    )
    original = original_sql.rstrip() + "\n"
    patch = "".join(
        unified_diff(
            original.splitlines(keepends=True),
            patched_sql.splitlines(keepends=True),
            fromfile="models/revenue_daily.sql",
            tofile="models/revenue_daily.sql",
        )
    )
    return patched_sql, patch


def validate_germany_patch(
    *,
    original_sql: str,
    patched_sql: str,
    artifact_path: str,
    as_of_date: date,
) -> ArtifactCheck:
    """Verify that the patch adds only the expected German active record."""

    recent = as_of_date - timedelta(days=2)
    rows = (
        ("us-active", recent, "postpaid", "US", "active"),
        ("de-active", recent, "postpaid", "DE", "active"),
        ("de-trial", recent, "postpaid", "DE", "trial"),
        ("fr-refunded", recent, "postpaid", "FR", "refunded"),
    )
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("CREATE SCHEMA analytics")
        connection.execute(
            """
            CREATE TABLE analytics.revenue_daily(
                customer_id VARCHAR,
                activity_at DATE,
                billing_type VARCHAR,
                country_code VARCHAR,
                account_status VARCHAR
            )
            """
        )
        connection.executemany(
            "INSERT INTO analytics.revenue_daily VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        current_date = f"DATE '{as_of_date.isoformat()}'"
        original_for_check = re.sub(
            r"\bcurrent_date\b",
            current_date,
            original_sql,
            flags=re.IGNORECASE,
        )
        patched_for_check = re.sub(
            r"\bcurrent_date\b",
            current_date,
            patched_sql,
            flags=re.IGNORECASE,
        )
        original_ids = {
            str(row[0]) for row in connection.execute(original_for_check).fetchall()
        }
        patched_ids = {
            str(row[0]) for row in connection.execute(patched_for_check).fetchall()
        }
    finally:
        connection.close()

    added = patched_ids - original_ids
    removed = original_ids - patched_ids
    passed = added == {"de-active"} and not removed
    failures: tuple[tuple[str, ...], ...] = ()
    if not passed:
        failures = (
            ("unexpected_added", ",".join(sorted(added))),
            ("unexpected_removed", ",".join(sorted(removed))),
        )
    return ArtifactCheck(
        artifact_path=artifact_path,
        passed=passed,
        failing_rows=failures,
    )


def generate_glossary_update(
    contract: DecisionContract,
    *,
    current_definition: str,
) -> str:
    """Generate the documentation-drift proposal as a reviewable diff."""

    if contract.status is not TruthState.CONFIRMED:
        raise ArtifactGenerationError(
            "context generation requires a CONFIRMED contract"
        )
    proposed = (
        "A customer with qualifying activity within the applicable activity "
        "window. Trial and refunded accounts, identified by account_status, "
        "are excluded from active-customer reporting.\n"
    )
    current = current_definition.rstrip() + "\n"
    return "".join(
        unified_diff(
            current.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile="glossary/active-customer.md",
            tofile="glossary/active-customer.md",
        )
    )


def validate_context_update(
    content: str,
    *,
    artifact_path: str,
) -> ArtifactCheck:
    required = ("trial", "refunded", "account_status")
    missing = tuple(value for value in required if value not in content.lower())
    return ArtifactCheck(
        artifact_path=artifact_path,
        passed=not missing,
        failing_rows=(missing,) if missing else (),
    )


def write_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
