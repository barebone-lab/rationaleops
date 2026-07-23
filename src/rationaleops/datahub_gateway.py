"""DataHub context fixtures and approval-gated write-back adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any

from rationaleops.models import (
    DecisionContract,
    MutationApproval,
    QueryContext,
    TruthState,
    WriteBackReceipt,
)


class WriteBackError(ValueError):
    """Raised when a proposed DataHub mutation violates an approval guard."""


def _validate_write_approval(
    contract: DecisionContract,
    approval: MutationApproval,
) -> None:
    if contract.status not in {TruthState.CONFIRMED, TruthState.EXPIRED}:
        raise WriteBackError(
            "only confirmed or historically confirmed expired contracts "
            "may be written back"
        )
    if approval.contract_id != contract.id:
        raise WriteBackError("approval does not match the contract")
    if approval.approved_by not in contract.authority.authorized_confirmers:
        raise WriteBackError("write-back approver is not authorized")
    if (
        not (contract.verification.tests or contract.verification.artifacts)
        or contract.verification.passed is not True
    ):
        raise WriteBackError("write-back requires a passing deterministic verification")
    confirmed_at = contract.authority.confirmed_at
    checked_at = contract.verification.checked_at
    if confirmed_at and approval.approved_at < confirmed_at:
        raise WriteBackError("write-back approval predates confirmation")
    if checked_at and approval.approved_at < checked_at:
        raise WriteBackError("write-back approval predates verification")


def load_demo_context() -> QueryContext:
    """Load the package-owned reproducible DataHub context fixture."""

    fixture_root = files("rationaleops.demo")
    payload = json.loads(fixture_root.joinpath("context.json").read_text())
    payload["sql"] = fixture_root.joinpath("revenue_daily.sql").read_text()
    return QueryContext.model_validate(payload)


class FixtureDataHubGateway:
    """A deterministic read/write substitute for judges without DataHub."""

    def __init__(self, context: QueryContext | None = None) -> None:
        self._context = context or load_demo_context()
        self._contracts: dict[str, dict[str, Any]] = {}

    def get_query_context(self) -> QueryContext:
        return self._context

    def write_contract(
        self,
        contract: DecisionContract,
        approval: MutationApproval,
    ) -> WriteBackReceipt:
        _validate_write_approval(contract, approval)
        self._contracts[contract.id] = contract.model_dump(mode="json")
        retrievable = self.read_contract(contract.id) is not None
        return WriteBackReceipt(
            contract_id=contract.id,
            dataset_urn=contract.implements.dataset_urn,
            mode="recorded-fixture",
            written_by=approval.approved_by,
            written_at=approval.approved_at,
            retrievable=retrievable,
        )

    def read_contract(self, contract_id: str) -> dict[str, Any] | None:
        return self._contracts.get(contract_id)


class DataHubSdkWriter:
    """Live DataHub writer; construction does not mutate remote state."""

    _PROPERTY_PREFIX = "rationaleops."

    def __init__(self, *, server: str, token: str | None = None) -> None:
        from datahub.sdk.main_client import DataHubClient

        self._client = DataHubClient(server=server, token=token)

    @staticmethod
    def _contract_key(contract_id: str) -> str:
        return contract_id.replace(".", "_")

    @staticmethod
    def _contract_properties(contract: DecisionContract) -> dict[str, str]:
        confirmed_at = contract.authority.confirmed_at
        expires_at = contract.lifecycle.expires_at
        properties = {
            "rationaleops.contract_id": contract.id,
            "rationaleops.status": contract.status.value,
            "rationaleops.finding_type": (
                contract.finding_type.value if contract.finding_type else ""
            ),
            "rationaleops.outcome": (
                contract.outcome.value if contract.outcome else ""
            ),
            "rationaleops.title": contract.title,
            "rationaleops.intent": contract.intent.canonical_rule,
            "rationaleops.owner": contract.authority.owner,
            "rationaleops.confirmed_by": contract.authority.confirmed_by or "",
            "rationaleops.confirmed_at": (
                confirmed_at.isoformat() if confirmed_at else ""
            ),
            "rationaleops.sql_fingerprint": (contract.implements.sql_fingerprint),
            "rationaleops.review_on": json.dumps(
                contract.lifecycle.review_on,
                separators=(",", ":"),
            ),
            "rationaleops.expires_at": expires_at.isoformat() if expires_at else "",
            "rationaleops.verification_artifacts": json.dumps(
                contract.verification.tests + contract.verification.artifacts,
                separators=(",", ":"),
            ),
            "rationaleops.verification_passed": str(
                contract.verification.passed
            ).lower(),
        }
        contract_key = DataHubSdkWriter._contract_key(contract.id)
        properties[f"rationaleops.contract.{contract_key}.status"] = (
            contract.status.value
        )
        properties[f"rationaleops.contract.{contract_key}.intent"] = (
            contract.intent.canonical_rule
        )
        properties[f"rationaleops.contract.{contract_key}.fingerprint"] = (
            contract.implements.sql_fingerprint
        )
        return properties

    def test_connection(self) -> None:
        self._client.test_connection()

    def write_contract(
        self,
        contract: DecisionContract,
        approval: MutationApproval,
    ) -> WriteBackReceipt:
        from datahub.sdk.dataset import Dataset

        _validate_write_approval(contract, approval)
        entity = self._client.entities.get(contract.implements.dataset_urn)
        if not isinstance(entity, Dataset):
            raise WriteBackError("write-back target is not a DataHub dataset")

        properties = dict(entity.custom_properties)
        properties.update(self._contract_properties(contract))
        entity.set_custom_properties(properties)
        entity.add_tag("urn:li:tag:RationaleVerified")
        self._client.entities.update(entity)

        persisted = self._client.entities.get(contract.implements.dataset_urn)
        if not isinstance(persisted, Dataset):
            raise WriteBackError("unable to retrieve the updated dataset")
        marker = f"rationaleops.contract.{self._contract_key(contract.id)}.status"
        retrievable = persisted.custom_properties.get(marker) == contract.status.value
        return WriteBackReceipt(
            contract_id=contract.id,
            dataset_urn=contract.implements.dataset_urn,
            mode="datahub-sdk",
            written_by=approval.approved_by,
            written_at=datetime.now(UTC),
            retrievable=retrievable,
        )
