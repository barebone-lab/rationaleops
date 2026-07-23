from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rationaleops.contracts import transition_contract
from rationaleops.datahub_gateway import load_demo_context
from rationaleops.interview import RecordedInterview
from rationaleops.mining import mine_decision_points
from rationaleops.models import (
    ContractVerification,
    DecisionContract,
    DecisionKind,
    TruthState,
)


@pytest.fixture
def completed_interview() -> RecordedInterview:
    context = load_demo_context()
    points = mine_decision_points(
        context.sql,
        query_urn=context.query_urn,
        dataset_urn=context.dataset_urn,
        dialect=context.dialect,
    )
    active_window = next(
        point for point in points if point.kind is DecisionKind.DATE_WINDOW
    )
    interview = RecordedInterview(
        session_id="interview-test",
        decision_point=active_window,
        context=context,
    )
    interview.answer(
        "Late settlement captures caused under-reporting, so Finance added "
        "a seven-day grace period."
    )
    interview.answer(
        "No. Prepaid accounts use billing_type = 'prepaid' and a 30-day window."
    )
    return interview


@pytest.fixture
def owner_stated_contract(
    completed_interview: RecordedInterview,
) -> DecisionContract:
    return completed_interview.draft_contract()


@pytest.fixture
def confirmed_contract(
    owner_stated_contract: DecisionContract,
) -> DecisionContract:
    return transition_contract(
        owner_stated_contract,
        TruthState.CONFIRMED,
        actor="urn:li:corpuser:demo-owner",
        occurred_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    )


@pytest.fixture
def verified_contract(
    confirmed_contract: DecisionContract,
) -> DecisionContract:
    payload = confirmed_contract.model_dump(mode="python")
    payload["verification"] = ContractVerification(
        tests=("test_active_window.sql",),
        passed=True,
        checked_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    ).model_dump(mode="python")
    return DecisionContract.model_validate(payload)
