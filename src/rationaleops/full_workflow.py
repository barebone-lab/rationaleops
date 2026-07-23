"""Deterministic three-outcome hero workflow."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rationaleops.artifacts import (
    generate_active_window_test,
    generate_glossary_update,
    generate_remove_predicate_patch,
    run_sql_acceptance_test,
    validate_context_update,
    validate_germany_patch,
    write_artifact,
)
from rationaleops.contracts import transition_contract
from rationaleops.datahub_gateway import FixtureDataHubGateway
from rationaleops.interview import (
    GermanyRecordedInterview,
    RecordedInterview,
    StatusRecordedInterview,
)
from rationaleops.mining import mine_decision_points
from rationaleops.models import (
    ActionApproval,
    ActionArtifact,
    ArtifactKind,
    ArtifactStatus,
    ContractVerification,
    DecisionContract,
    DecisionKind,
    GraphEdge,
    GraphNode,
    ImpactGraph,
    MutationApproval,
    RankedDecisionPoint,
    TruthState,
)
from rationaleops.risk import (
    calculate_risk,
    has_active_window_glossary_conflict,
)


class FullWorkflowValidationError(RuntimeError):
    """Raised when any golden-demo deterministic invariant fails."""


def _recorded_time(as_of_date: date) -> datetime:
    return datetime(
        as_of_date.year,
        as_of_date.month,
        as_of_date.day,
        12,
        0,
        tzinfo=UTC,
    )


def _attach_verification(
    contract: DecisionContract,
    *,
    artifact_path: str,
    kind: ArtifactKind,
    passed: bool,
    checked_at: datetime,
) -> DecisionContract:
    payload = contract.model_dump(mode="python")
    payload["verification"] = ContractVerification(
        tests=(artifact_path,) if kind is ArtifactKind.SQL_TEST else (),
        artifacts=(artifact_path,),
        passed=passed,
        checked_at=checked_at,
    ).model_dump(mode="python")
    return DecisionContract.model_validate(payload)


def _rank_decisions(
    gateway: FixtureDataHubGateway,
) -> tuple[RankedDecisionPoint, ...]:
    context = gateway.get_query_context()
    glossary = " ".join(item.definition for item in context.glossary)
    points = mine_decision_points(
        context.sql,
        query_urn=context.query_urn,
        dataset_urn=context.dataset_urn,
        dialect=context.dialect,
    )
    ranked: list[RankedDecisionPoint] = []
    for point in points:
        is_status_rule = {"trial", "refunded"}.issubset(set(point.literal_values))
        ranked.append(
            RankedDecisionPoint(
                decision_point=point,
                risk=calculate_risk(
                    point,
                    context.impact,
                    glossary_conflict=(
                        has_active_window_glossary_conflict(point, glossary)
                        or is_status_rule
                    ),
                    temporary_marker="DE" in point.literal_values,
                ),
            )
        )
    return tuple(sorted(ranked, key=lambda item: item.risk.total, reverse=True))


def build_recorded_impact_graph() -> ImpactGraph:
    root = "revenue_daily"
    sample_downstream = (
        ("executive_revenue", "Executive Active Revenue", "dashboard", True),
        ("monthly_close", "Finance Monthly Close", "dataset", True),
        ("active_revenue_kpi", "Active Revenue KPI", "chart", True),
        ("growth_scorecard", "Growth Scorecard", "dashboard", False),
        ("board_pack", "Board Revenue Pack", "dashboard", True),
        ("forecast_inputs", "Forecast Inputs", "dataset", False),
        ("regional_revenue", "Regional Revenue", "dataset", False),
        ("plus_40", "+40 downstream assets", "summary", False),
    )
    nodes = [
        GraphNode(id="raw_activity", label="Raw Activity", kind="source"),
        GraphNode(id=root, label="revenue_daily", kind="dataset", critical=True),
    ]
    edges = [GraphEdge(source="raw_activity", target=root)]
    for node_id, label, kind, critical in sample_downstream:
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                kind=kind,
                critical=critical,
            )
        )
        edges.append(GraphEdge(source=root, target=node_id))
    return ImpactGraph(nodes=tuple(nodes), edges=tuple(edges))


def _write_json(path: Path, value: Any) -> None:
    write_artifact(path, json.dumps(value, indent=2) + "\n")


def run_recorded_full_demo(
    *,
    output_dir: Path,
    approve_actions: bool,
    approve_writeback: bool,
    as_of_date: date = date(2026, 7, 23),
) -> dict[str, Any]:
    """Run all three hero outcomes with deterministic evidence and checks."""

    gateway = FixtureDataHubGateway()
    context = gateway.get_query_context()
    ranked = _rank_decisions(gateway)
    if len(ranked) != 3:
        raise FullWorkflowValidationError("expected exactly three decision points")

    active_ranked = next(
        item for item in ranked if item.decision_point.kind is DecisionKind.DATE_WINDOW
    )
    germany_ranked = next(
        item for item in ranked if "DE" in item.decision_point.literal_values
    )
    status_ranked = next(
        item for item in ranked if "trial" in item.decision_point.literal_values
    )
    recorded_at = _recorded_time(as_of_date)
    confirmer = "urn:li:corpuser:demo-owner"

    active_interview = RecordedInterview(
        session_id="interview-active-window",
        decision_point=active_ranked.decision_point,
        context=context,
    )
    active_interview.answer(
        "Finance added a seven-day settlement grace period after late card "
        "captures caused monthly under-reporting."
    )
    active_interview.answer(
        "No. Prepaid accounts are identified by billing_type = 'prepaid' "
        "and remain on a 30-day window."
    )
    active_contract = transition_contract(
        active_interview.draft_contract(),
        TruthState.CONFIRMED,
        actor=confirmer,
        occurred_at=recorded_at,
    )
    active_path = "active_window/test_active_window.sql"
    active_sql = generate_active_window_test(
        active_contract,
        as_of_date=as_of_date,
    )
    active_check = run_sql_acceptance_test(
        active_sql,
        artifact_path=active_path,
    )
    active_contract = _attach_verification(
        active_contract,
        artifact_path=active_path,
        kind=ArtifactKind.SQL_TEST,
        passed=active_check.passed,
        checked_at=recorded_at,
    )

    germany_interview = GermanyRecordedInterview(
        session_id="interview-germany-hold",
        decision_point=germany_ranked.decision_point,
        context=context,
    )
    germany_interview.answer(
        "It was a temporary legal hold during the EU billing migration."
    )
    germany_interview.answer(
        "The migration completed on 2026-06-30, so the hold ended that day."
    )
    germany_contract = transition_contract(
        germany_interview.draft_contract(),
        TruthState.CONFIRMED,
        actor=confirmer,
        occurred_at=recorded_at,
    )
    if not germany_contract.lifecycle.expires_at:
        raise FullWorkflowValidationError("expired decision lacks an expiry date")
    if germany_contract.lifecycle.expires_at >= as_of_date:
        raise FullWorkflowValidationError("Germany workaround has not expired")
    germany_contract = transition_contract(
        germany_contract,
        TruthState.EXPIRED,
        occurred_at=recorded_at,
    )
    patched_sql, patch = generate_remove_predicate_patch(
        germany_contract,
        original_sql=context.sql,
        decision_point=germany_ranked.decision_point,
        dialect=context.dialect,
    )
    germany_path = "germany/remove_germany_filter.patch"
    germany_check = validate_germany_patch(
        original_sql=context.sql,
        patched_sql=patched_sql,
        artifact_path=germany_path,
        as_of_date=as_of_date,
    )
    germany_contract = _attach_verification(
        germany_contract,
        artifact_path=germany_path,
        kind=ArtifactKind.SQL_PATCH,
        passed=germany_check.passed,
        checked_at=recorded_at,
    )

    status_interview = StatusRecordedInterview(
        session_id="interview-status-rule",
        decision_point=status_ranked.decision_point,
        context=context,
    )
    status_interview.answer(
        "Yes. It is the official definition: trial and refunded accounts "
        "are not active revenue customers."
    )
    status_interview.answer(
        "account_status identifies both values and there are no customer-type "
        "exceptions."
    )
    status_contract = transition_contract(
        status_interview.draft_contract(),
        TruthState.CONFIRMED,
        actor=confirmer,
        occurred_at=recorded_at,
    )
    glossary_path = "status/glossary_update.diff"
    glossary_update = generate_glossary_update(
        status_contract,
        current_definition=context.glossary[0].definition,
    )
    glossary_check = validate_context_update(
        glossary_update,
        artifact_path=glossary_path,
    )
    status_contract = _attach_verification(
        status_contract,
        artifact_path=glossary_path,
        kind=ArtifactKind.CONTEXT_UPDATE,
        passed=glossary_check.passed,
        checked_at=recorded_at,
    )

    contracts = (active_contract, germany_contract, status_contract)
    raw_artifacts = (
        ActionArtifact(
            id="artifact-active-window-test",
            contract_id=active_contract.id,
            kind=ArtifactKind.SQL_TEST,
            status=ArtifactStatus.VALIDATED,
            title="Prepaid activity-window acceptance test",
            content=active_sql,
            path=active_path,
            check=active_check,
        ),
        ActionArtifact(
            id="artifact-germany-patch",
            contract_id=germany_contract.id,
            kind=ArtifactKind.SQL_PATCH,
            status=ArtifactStatus.VALIDATED,
            title="Remove expired Germany filter",
            content=patch,
            path=germany_path,
            check=germany_check,
        ),
        ActionArtifact(
            id="artifact-glossary-update",
            contract_id=status_contract.id,
            kind=ArtifactKind.CONTEXT_UPDATE,
            status=ArtifactStatus.VALIDATED,
            title="Update active-customer glossary definition",
            content=glossary_update,
            path=glossary_path,
            check=glossary_check,
        ),
    )
    checks = (active_check, germany_check, glossary_check)
    if not all(check.passed for check in checks):
        raise FullWorkflowValidationError(
            "an artifact failed deterministic validation; publication blocked"
        )
    approvals: list[ActionApproval] = []
    artifacts: list[ActionArtifact] = []
    for artifact in raw_artifacts:
        if approve_actions:
            approvals.append(
                ActionApproval(
                    artifact_id=artifact.id,
                    approved_by=confirmer,
                    approved_at=recorded_at,
                )
            )
            artifacts.append(
                artifact.model_copy(update={"status": ArtifactStatus.APPROVED})
            )
        else:
            artifacts.append(artifact)

    receipts = []
    if approve_writeback:
        for contract in contracts:
            receipts.append(
                gateway.write_contract(
                    contract,
                    MutationApproval(
                        contract_id=contract.id,
                        approved_by=confirmer,
                        approved_at=recorded_at,
                    ),
                )
            )

    write_artifact(output_dir / active_path, active_sql)
    write_artifact(output_dir / germany_path, patch)
    write_artifact(output_dir / "germany/revenue_daily_patched.sql", patched_sql)
    write_artifact(output_dir / glossary_path, glossary_update)
    for contract in contracts:
        _write_json(
            output_dir / "contracts" / f"{contract.id}.json",
            contract.model_dump(mode="json"),
        )
    transcripts = (
        ("active-window", active_interview.turns),
        ("germany-hold", germany_interview.turns),
        ("status-rule", status_interview.turns),
    )
    for name, turns in transcripts:
        _write_json(
            output_dir / "interviews" / f"{name}.json",
            [turn.model_dump(mode="json") for turn in turns],
        )

    graph = build_recorded_impact_graph()
    _write_json(output_dir / "impact-graph.json", graph.model_dump(mode="json"))
    _write_json(
        output_dir / "actions.json",
        {
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
            "approvals": [item.model_dump(mode="json") for item in approvals],
        },
    )

    cards = []
    for ranked_item, contract, artifact in (
        (active_ranked, active_contract, artifacts[0]),
        (germany_ranked, germany_contract, artifacts[1]),
        (status_ranked, status_contract, artifacts[2]),
    ):
        cards.append(
            {
                "decision_point": ranked_item.decision_point.model_dump(mode="json"),
                "risk": ranked_item.risk.model_dump(mode="json"),
                "outcome": contract.outcome.value if contract.outcome else None,
                "contract_status": contract.status.value,
                "contract_id": contract.id,
                "artifact_id": artifact.id,
                "artifact_status": artifact.status.value,
            }
        )

    summary: dict[str, Any] = {
        "mode": "recorded-fixture",
        "as_of_date": as_of_date.isoformat(),
        "decision_points_found": len(ranked),
        "downstream_count": context.impact.downstream_count,
        "outcomes": [
            "CONFIRMED_RULE",
            "EXPIRED_WORKAROUND",
            "DOCUMENTATION_DRIFT",
        ],
        "decision_cards": cards,
        "generated_test_passes": active_check.passed,
        "expired_workaround_patch_passes": germany_check.passed,
        "documentation_update_valid": glossary_check.passed,
        "unconfirmed_rationale_published": 0,
        "actions_approved": approve_actions,
        "writeback_approved": approve_writeback,
        "datahub_write_back_visible": (
            len(receipts) == 3 and all(item.retrievable for item in receipts)
        ),
        "writeback_receipts": [item.model_dump(mode="json") for item in receipts],
    }
    _write_json(output_dir / "summary.json", summary)
    return summary
