from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rationaleops.contracts import (
    ContractTransitionError,
    transition_contract,
)
from rationaleops.datahub_gateway import load_demo_context
from rationaleops.interview import RecordedInterview
from rationaleops.mining import mine_decision_points
from rationaleops.models import (
    ContractAuthority,
    DecisionContract,
    DecisionKind,
    TruthState,
)


def _new_interview() -> RecordedInterview:
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
    return RecordedInterview(
        session_id="interview-boundary",
        decision_point=point,
        context=context,
    )


def test_vague_answer_triggers_incident_probe() -> None:
    interview = _new_interview()

    follow_up = interview.answer("I think Finance requested it.")

    assert follow_up is not None
    assert "specific operational signal" in follow_up
    with pytest.raises(
        ContractTransitionError,
        match="exception boundary is not complete",
    ):
        interview.draft_contract()


def test_exception_without_signal_triggers_executable_boundary_probe() -> None:
    interview = _new_interview()
    interview.answer("Settlement captures were late and caused under-reporting.")

    follow_up = interview.answer("No, prepaid is different.")

    assert follow_up is not None
    assert "identifying field" in follow_up
    assert "exact fallback window" in follow_up


def test_contract_stays_owner_stated_until_authorized_confirmation(
    owner_stated_contract: DecisionContract,
) -> None:
    assert owner_stated_contract.status is TruthState.OWNER_STATED
    assert owner_stated_contract.authority.confirmed_by is None

    with pytest.raises(ContractTransitionError, match="not authorized"):
        transition_contract(
            owner_stated_contract,
            TruthState.CONFIRMED,
            actor="urn:li:corpuser:unrelated-user",
        )

    confirmed = transition_contract(
        owner_stated_contract,
        TruthState.CONFIRMED,
        actor="urn:li:corpuser:demo-owner",
        occurred_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    )
    assert confirmed.status is TruthState.CONFIRMED
    assert confirmed.authority.confirmed_by == ("urn:li:corpuser:demo-owner")


def test_schema_rejects_confirmation_metadata_on_owner_stated_contract(
    owner_stated_contract: DecisionContract,
) -> None:
    payload = owner_stated_contract.model_dump(mode="python")
    payload["authority"] = ContractAuthority(
        owner=owner_stated_contract.authority.owner,
        authorized_confirmers=(owner_stated_contract.authority.authorized_confirmers),
        confirmed_by="urn:li:corpuser:demo-owner",
        confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(
        ValidationError,
        match="unconfirmed contracts cannot contain",
    ):
        DecisionContract.model_validate(payload)
