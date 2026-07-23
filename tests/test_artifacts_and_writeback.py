from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rationaleops.artifacts import (
    ArtifactGenerationError,
    generate_active_window_test,
    run_sql_acceptance_test,
)
from rationaleops.datahub_gateway import (
    DataHubSdkWriter,
    FixtureDataHubGateway,
    WriteBackError,
)
from rationaleops.models import (
    DecisionContract,
    MutationApproval,
)


def _approval(
    *,
    contract_id: str,
    actor: str = "urn:li:corpuser:demo-owner",
) -> MutationApproval:
    return MutationApproval(
        contract_id=contract_id,
        approved_by=actor,
        approved_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    )


def test_unconfirmed_contract_cannot_generate_executable_artifact(
    owner_stated_contract: DecisionContract,
) -> None:
    with pytest.raises(
        ArtifactGenerationError,
        match="requires a CONFIRMED contract",
    ):
        generate_active_window_test(owner_stated_contract)


def test_generated_active_window_test_passes(
    confirmed_contract: DecisionContract,
) -> None:
    sql = generate_active_window_test(confirmed_contract)

    result = run_sql_acceptance_test(sql)

    assert result.passed is True
    assert result.failing_rows == ()


def test_boundary_regression_is_detected(
    confirmed_contract: DecisionContract,
) -> None:
    sql = generate_active_window_test(confirmed_contract)
    broken_sql = sql.replace(
        "THEN INTERVAL 30 DAY",
        "THEN INTERVAL 31 DAY",
    )

    result = run_sql_acceptance_test(broken_sql)

    assert result.passed is False
    assert result.failing_rows[0][0] == "prepaid_day_31"


def test_fixture_writeback_requires_confirmation_and_separate_approval(
    owner_stated_contract: DecisionContract,
    confirmed_contract: DecisionContract,
    verified_contract: DecisionContract,
) -> None:
    gateway = FixtureDataHubGateway()

    with pytest.raises(
        WriteBackError,
        match="only confirmed or historically confirmed expired contracts",
    ):
        gateway.write_contract(
            owner_stated_contract,
            _approval(contract_id=owner_stated_contract.id),
        )
    with pytest.raises(WriteBackError, match="does not match"):
        gateway.write_contract(
            verified_contract,
            _approval(contract_id="different-contract"),
        )
    with pytest.raises(WriteBackError, match="passing deterministic"):
        gateway.write_contract(
            confirmed_contract,
            _approval(contract_id=confirmed_contract.id),
        )

    receipt = gateway.write_contract(
        verified_contract,
        _approval(contract_id=verified_contract.id),
    )
    assert receipt.retrievable is True
    assert gateway.read_contract(verified_contract.id) is not None


def test_live_writer_payload_contains_verified_contract_identity(
    verified_contract: DecisionContract,
) -> None:
    properties = DataHubSdkWriter._contract_properties(verified_contract)

    assert properties["rationaleops.contract_id"] == verified_contract.id
    assert properties["rationaleops.status"] == "CONFIRMED"
    assert properties["rationaleops.verification_passed"] == "true"
