"""End-to-end orchestration for the first documented vertical slice."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rationaleops.artifacts import (
    generate_active_window_test,
    run_sql_acceptance_test,
    write_artifact,
)
from rationaleops.contracts import transition_contract
from rationaleops.datahub_gateway import FixtureDataHubGateway
from rationaleops.interview import RecordedInterview
from rationaleops.mining import mine_decision_points
from rationaleops.models import (
    ContractVerification,
    DecisionContract,
    DecisionKind,
    MutationApproval,
    RankedDecisionPoint,
    TruthState,
)
from rationaleops.risk import (
    calculate_risk,
    has_active_window_glossary_conflict,
)

_RECORDED_CONFIRMATION_TIME = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


class WorkflowValidationError(RuntimeError):
    """Raised when a deterministic gate fails during orchestration."""


def _attach_test(
    contract: DecisionContract,
    artifact_path: str,
    *,
    passed: bool,
) -> DecisionContract:
    payload = contract.model_dump(mode="python")
    payload["verification"] = ContractVerification(
        tests=(artifact_path,),
        passed=passed,
        checked_at=_RECORDED_CONFIRMATION_TIME,
    ).model_dump(mode="python")
    return DecisionContract.model_validate(payload)


def _rank_fixture_decisions(
    gateway: FixtureDataHubGateway,
) -> tuple[RankedDecisionPoint, ...]:
    context = gateway.get_query_context()
    glossary_text = " ".join(item.definition for item in context.glossary)
    points = mine_decision_points(
        context.sql,
        query_urn=context.query_urn,
        dataset_urn=context.dataset_urn,
        dialect=context.dialect,
    )
    ranked = [
        RankedDecisionPoint(
            decision_point=point,
            risk=calculate_risk(
                point,
                context.impact,
                glossary_conflict=has_active_window_glossary_conflict(
                    point,
                    glossary_text,
                ),
            ),
        )
        for point in points
    ]
    return tuple(
        sorted(ranked, key=lambda item: item.risk.total, reverse=True)
    )


def run_recorded_vertical_slice(
    *,
    output_dir: Path,
    approve_writeback: bool,
    as_of_date: date = date(2026, 7, 23),
) -> dict[str, Any]:
    """Run the 37-day workflow without an LLM key or DataHub instance."""

    gateway = FixtureDataHubGateway()
    context = gateway.get_query_context()
    ranked = _rank_fixture_decisions(gateway)
    active_window = next(
        item
        for item in ranked
        if item.decision_point.kind is DecisionKind.DATE_WINDOW
        and "37" in item.decision_point.literal_values
    )

    interview = RecordedInterview(
        session_id="interview-001",
        decision_point=active_window.decision_point,
        context=context,
    )
    interview.answer(
        "Finance added a seven-day settlement grace period after late card "
        "captures caused monthly under-reporting."
    )
    interview.answer(
        "No. Prepaid accounts are identified by billing_type = 'prepaid' "
        "and remain on a 30-day window."
    )
    owner_stated_contract = interview.draft_contract()
    confirmed_contract = transition_contract(
        owner_stated_contract,
        TruthState.CONFIRMED,
        actor="urn:li:corpuser:demo-owner",
        occurred_at=_RECORDED_CONFIRMATION_TIME,
    )

    test_relative_path = "test_active_window.sql"
    test_path = output_dir / test_relative_path
    test_sql = generate_active_window_test(
        confirmed_contract,
        as_of_date=as_of_date,
    )
    write_artifact(test_path, test_sql)
    test_check = run_sql_acceptance_test(
        test_sql,
        artifact_path=str(test_path),
    )
    if not test_check.passed:
        raise WorkflowValidationError(
            "generated SQL acceptance test failed; write-back blocked"
        )
    contract_with_test = _attach_test(
        confirmed_contract,
        test_relative_path,
        passed=test_check.passed,
    )

    receipt = None
    if approve_writeback:
        approval = MutationApproval(
            contract_id=contract_with_test.id,
            approved_by="urn:li:corpuser:demo-owner",
            approved_at=_RECORDED_CONFIRMATION_TIME,
        )
        receipt = gateway.write_contract(contract_with_test, approval)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_artifact(
        output_dir / "decision-contract.json",
        contract_with_test.model_dump_json(indent=2) + "\n",
    )
    write_artifact(
        output_dir / "interview.json",
        json.dumps(
            [turn.model_dump(mode="json") for turn in interview.turns],
            indent=2,
        )
        + "\n",
    )

    summary: dict[str, Any] = {
        "mode": "recorded-fixture",
        "decision_points_found": len(ranked),
        "selected_decision_point": active_window.decision_point.id,
        "selected_sql_fragment": active_window.decision_point.sql_fragment,
        "downstream_count": context.impact.downstream_count,
        "knowledge_risk": active_window.risk.model_dump(mode="json"),
        "adaptive_follow_up": interview.turns[2].content,
        "contract_status": contract_with_test.status.value,
        "generated_test_passes": test_check.passed,
        "unconfirmed_rationale_published": 0,
        "writeback_approved": approve_writeback,
        "datahub_write_back_visible": bool(
            receipt and receipt.retrievable
        ),
        "writeback_receipt": (
            receipt.model_dump(mode="json") if receipt else None
        ),
    }
    write_artifact(
        output_dir / "summary.json",
        json.dumps(summary, indent=2) + "\n",
    )
    return summary
