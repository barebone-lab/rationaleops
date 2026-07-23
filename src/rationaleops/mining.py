"""Deterministic SQL decision-point extraction."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from rationaleops.models import DecisionKind, DecisionPoint


class DecisionPointMiningError(ValueError):
    """Raised when a query cannot be parsed into decision points."""


def _split_conjunction(expression: exp.Expression) -> Iterable[exp.Expression]:
    if isinstance(expression, exp.And):
        yield from _split_conjunction(expression.this)
        yield from _split_conjunction(expression.expression)
        return
    yield expression


def normalize_expression(expression: exp.Expression, *, dialect: str) -> str:
    normalized = expression.copy()
    for interval in normalized.find_all(exp.Interval):
        unit = interval.args.get("unit")
        if isinstance(unit, exp.Var):
            canonical_unit = unit.name.upper()
            if canonical_unit.endswith("S"):
                canonical_unit = canonical_unit[:-1]
            interval.set("unit", exp.Var(this=canonical_unit))
    return normalized.sql(
        dialect=dialect,
        normalize=True,
        pretty=False,
    )


def _literal_values(expression: exp.Expression) -> tuple[str, ...]:
    values: list[str] = []
    for literal in expression.find_all(exp.Literal):
        value = str(literal.this)
        if value not in values:
            values.append(value)
    return tuple(values)


def _referenced_fields(expression: exp.Expression) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(column.name.lower() for column in expression.find_all(exp.Column))
    )


def _classify(expression: exp.Expression) -> DecisionKind | None:
    if expression.find(exp.Interval):
        return DecisionKind.DATE_WINDOW
    if isinstance(expression, exp.Not) and isinstance(expression.this, exp.In):
        return DecisionKind.HARD_CODED_EXCLUSION
    if isinstance(expression, (exp.NEQ, exp.Not)):
        return DecisionKind.HARD_CODED_EXCLUSION
    if expression.find(exp.Case):
        return DecisionKind.CASE_BRANCH
    literals = tuple(expression.find_all(exp.Literal))
    if any(literal.is_number for literal in literals):
        return DecisionKind.NUMERIC_LITERAL
    if literals and isinstance(
        expression,
        (exp.EQ, exp.GT, exp.GTE, exp.In, exp.LT, exp.LTE),
    ):
        return DecisionKind.UNUSUAL_PREDICATE
    return None


def _build_decision_point(
    expression: exp.Expression,
    *,
    kind: DecisionKind,
    query_urn: str,
    dataset_urn: str,
    dialect: str,
) -> DecisionPoint:
    normalized_sql = normalize_expression(expression, dialect=dialect)
    fingerprint = f"sha256:{sha256(normalized_sql.encode()).hexdigest()}"
    point_id = f"decision-{fingerprint.removeprefix('sha256:')[:12]}"
    return DecisionPoint(
        id=point_id,
        query_urn=query_urn,
        dataset_urn=dataset_urn,
        sql_fragment=expression.sql(dialect=dialect, pretty=False),
        normalized_sql=normalized_sql,
        sql_fingerprint=fingerprint,
        ast_type=expression.key,
        kind=kind,
        referenced_fields=_referenced_fields(expression),
        literal_values=_literal_values(expression),
    )


def mine_decision_points(
    sql: str,
    *,
    query_urn: str,
    dataset_urn: str,
    dialect: str = "postgres",
) -> list[DecisionPoint]:
    """Extract auditable candidates from filters, joins, and CASE branches.

    Extraction is intentionally deterministic. It identifies syntax that merits
    an interview but never assigns a business rationale.
    """

    try:
        statement = parse_one(sql, read=dialect)
    except ParseError as exc:
        raise DecisionPointMiningError(f"unable to parse SQL: {exc}") from exc

    candidates: list[tuple[exp.Expression, DecisionKind]] = []
    for clause_name in ("where", "having"):
        clause = statement.args.get(clause_name)
        if clause is None:
            continue
        for expression in _split_conjunction(clause.this):
            kind = _classify(expression)
            if kind is not None:
                candidates.append((expression, kind))

    for join in statement.find_all(exp.Join):
        on = join.args.get("on")
        if on is None:
            continue
        for expression in _split_conjunction(on):
            if tuple(expression.find_all(exp.Literal)):
                candidates.append((expression, DecisionKind.JOIN_PREDICATE))

    for case in statement.find_all(exp.Case):
        candidates.append((case, DecisionKind.CASE_BRANCH))

    decision_points: dict[str, DecisionPoint] = {}
    for expression, kind in candidates:
        point = _build_decision_point(
            expression,
            kind=kind,
            query_urn=query_urn,
            dataset_urn=dataset_urn,
            dialect=dialect,
        )
        decision_points.setdefault(point.sql_fingerprint, point)
    return list(decision_points.values())
