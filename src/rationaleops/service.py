"""Application service for the interactive RationaleOps demo."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from rationaleops.contracts import transition_contract
from rationaleops.datahub_gateway import DataHubSdkWriter, FixtureDataHubGateway
from rationaleops.full_workflow import run_recorded_full_demo
from rationaleops.llm import DeepSeekConfig, DeepSeekCTAAgent
from rationaleops.models import (
    ActionApproval,
    ActionArtifact,
    ArtifactStatus,
    DecisionContract,
    DecisionPoint,
    InterviewRole,
    InterviewTurn,
    MutationApproval,
    QueryContext,
    TruthState,
)
from rationaleops.storage import WorkflowStore

DEFAULT_SESSION_ID = "hero-demo"
DEMO_ACTOR = "urn:li:corpuser:demo-owner"


class WorkflowNotFoundError(LookupError):
    """Raised when a requested workflow object is absent."""


class WorkflowGuardError(ValueError):
    """Raised when an interactive action crosses a trust boundary."""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_action_time(contract: DecisionContract) -> datetime:
    """Return a real timestamp that is never earlier than recorded checks."""

    now = datetime.now(UTC)
    candidates = [now]
    if contract.verification.checked_at:
        candidates.append(contract.verification.checked_at)
    if contract.authority.confirmed_at:
        candidates.append(contract.authority.confirmed_at)
    return max(candidates)


class RationaleOpsService:
    """Coordinate deterministic work, explicit approvals, and persistence."""

    def __init__(self, store: WorkflowStore, *, artifact_root: Path) -> None:
        self.store = store
        self.artifact_root = artifact_root

    def _build_snapshot(self, session_id: str) -> dict[str, Any]:
        output_dir = self.artifact_root / session_id
        summary = run_recorded_full_demo(
            output_dir=output_dir,
            approve_actions=False,
            approve_writeback=False,
        )
        context = FixtureDataHubGateway().get_query_context()
        actions = _read_json(output_dir / "actions.json")
        graph = _read_json(output_dir / "impact-graph.json")
        transcript_names = {
            "decision-active-window-v1": "active-window",
            "decision-germany-hold-v1": "germany-hold",
            "decision-active-status-v1": "status-rule",
        }
        contracts: dict[str, Any] = {}
        interviews: dict[str, Any] = {}
        targets: dict[str, str] = {}
        cards: list[dict[str, Any]] = []

        for card in summary["decision_cards"]:
            contract_id = card["contract_id"]
            contract_payload = _read_json(
                output_dir / "contracts" / f"{contract_id}.json"
            )
            targets[contract_id] = contract_payload["status"]
            contract_payload["status"] = TruthState.OWNER_STATED.value
            contract_payload["authority"]["confirmed_by"] = None
            contract_payload["authority"]["confirmed_at"] = None
            contract = DecisionContract.model_validate(contract_payload)
            contracts[contract_id] = contract.model_dump(mode="json")

            transcript = _read_json(
                output_dir / "interviews" / f"{transcript_names[contract_id]}.json"
            )
            decision_id = card["decision_point"]["id"]
            interviews[decision_id] = {
                "decision_id": decision_id,
                "contract_id": contract_id,
                "turns": transcript,
                "ready_for_confirmation": True,
                "mode": "recorded",
            }

            card["contract_status"] = TruthState.OWNER_STATED.value
            cards.append(card)

        snapshot: dict[str, Any] = {
            "session_id": session_id,
            "mode": "recorded-fixture",
            "selected_decision_id": cards[0]["decision_point"]["id"],
            "context": context.model_dump(mode="json"),
            "graph": graph,
            "decisions": cards,
            "interviews": interviews,
            "live_interviews": {},
            "contracts": contracts,
            "target_contract_states": targets,
            "artifacts": {item["id"]: item for item in actions["artifacts"]},
            "action_approvals": {},
            "writeback_receipts": {},
            "invariants": {},
        }
        self._refresh_invariants(snapshot)
        saved = self.store.save(session_id, snapshot)
        self.store.append_event(
            session_id,
            event_type="DEMO_RESET",
            actor="system",
            payload={"decision_points_found": 3, "downstream_count": 47},
        )
        return saved

    @staticmethod
    def _refresh_invariants(snapshot: dict[str, Any]) -> None:
        artifacts = snapshot["artifacts"].values()
        receipts = snapshot["writeback_receipts"].values()
        published_ids = set(snapshot["writeback_receipts"])
        unconfirmed_published = sum(
            1
            for contract_id in published_ids
            if snapshot["contracts"][contract_id]["status"]
            not in {TruthState.CONFIRMED.value, TruthState.EXPIRED.value}
        )
        snapshot["invariants"] = {
            "decision_points_found": len(snapshot["decisions"]),
            "outcomes": sorted(card["outcome"] for card in snapshot["decisions"]),
            "downstream_count": snapshot["context"]["impact"]["downstream_count"],
            "all_deterministic_checks_pass": all(
                item.get("check", {}).get("passed") is True for item in artifacts
            ),
            "unconfirmed_rationale_published": unconfirmed_published,
            "actions_approved": len(snapshot["action_approvals"]),
            "datahub_write_back_visible": bool(receipts)
            and all(item["retrievable"] for item in receipts),
        }

    def _save(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self._refresh_invariants(snapshot)
        return self.store.save(snapshot["session_id"], snapshot)

    def get(self, session_id: str = DEFAULT_SESSION_ID) -> dict[str, Any]:
        snapshot = self.store.load(session_id)
        if snapshot is None:
            snapshot = self._build_snapshot(session_id)
        snapshot["events"] = self.store.events(session_id)
        return snapshot

    def reset(self, session_id: str = DEFAULT_SESSION_ID) -> dict[str, Any]:
        self.store.reset(session_id)
        snapshot = self._build_snapshot(session_id)
        snapshot["events"] = self.store.events(session_id)
        return snapshot

    def select_decision(
        self,
        decision_id: str,
        *,
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, Any]:
        snapshot = self.get(session_id)
        if not any(
            card["decision_point"]["id"] == decision_id
            for card in snapshot["decisions"]
        ):
            raise WorkflowNotFoundError(f"decision point not found: {decision_id}")
        snapshot.pop("events", None)
        snapshot["selected_decision_id"] = decision_id
        self._save(snapshot)
        self.store.append_event(
            session_id,
            event_type="DECISION_SELECTED",
            actor="viewer",
            payload={"decision_id": decision_id},
        )
        return self.get(session_id)

    def confirm_contract(
        self,
        contract_id: str,
        *,
        actor: str,
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, Any]:
        snapshot = self.get(session_id)
        payload = snapshot["contracts"].get(contract_id)
        if payload is None:
            raise WorkflowNotFoundError(f"contract not found: {contract_id}")
        contract = DecisionContract.model_validate(payload)
        if contract.status in {TruthState.CONFIRMED, TruthState.EXPIRED}:
            return snapshot
        if contract.status is not TruthState.OWNER_STATED:
            raise WorkflowGuardError("only owner-stated contracts may be confirmed")
        if actor not in contract.authority.authorized_confirmers:
            raise WorkflowGuardError("contract confirmer is not authorized")
        occurred_at = _safe_action_time(contract)
        contract = transition_contract(
            contract,
            TruthState.CONFIRMED,
            actor=actor,
            occurred_at=occurred_at,
        )
        if snapshot["target_contract_states"][contract_id] == TruthState.EXPIRED:
            contract = transition_contract(
                contract,
                TruthState.EXPIRED,
                occurred_at=occurred_at,
            )
        snapshot.pop("events", None)
        snapshot["contracts"][contract_id] = contract.model_dump(mode="json")
        for card in snapshot["decisions"]:
            if card["contract_id"] == contract_id:
                card["contract_status"] = contract.status.value
        self._save(snapshot)
        self.store.append_event(
            session_id,
            event_type="CONTRACT_CONFIRMED",
            actor=actor,
            payload={"contract_id": contract_id, "status": contract.status.value},
        )
        return self.get(session_id)

    def approve_artifact(
        self,
        artifact_id: str,
        *,
        actor: str,
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, Any]:
        snapshot = self.get(session_id)
        payload = snapshot["artifacts"].get(artifact_id)
        if payload is None:
            raise WorkflowNotFoundError(f"artifact not found: {artifact_id}")
        artifact = ActionArtifact.model_validate(payload)
        contract = DecisionContract.model_validate(
            snapshot["contracts"][artifact.contract_id]
        )
        if contract.status not in {TruthState.CONFIRMED, TruthState.EXPIRED}:
            raise WorkflowGuardError("confirm the contract before approving its action")
        if actor not in contract.authority.authorized_confirmers:
            raise WorkflowGuardError("artifact approver is not authorized")
        if artifact.check is None or not artifact.check.passed:
            raise WorkflowGuardError("artifact approval requires a passing check")
        approval = ActionApproval(
            artifact_id=artifact_id,
            approved_by=actor,
            approved_at=_safe_action_time(contract),
        )
        snapshot.pop("events", None)
        snapshot["action_approvals"][artifact_id] = approval.model_dump(mode="json")
        snapshot["artifacts"][artifact_id] = artifact.model_copy(
            update={"status": ArtifactStatus.APPROVED}
        ).model_dump(mode="json")
        for card in snapshot["decisions"]:
            if card["artifact_id"] == artifact_id:
                card["artifact_status"] = ArtifactStatus.APPROVED.value
        self._save(snapshot)
        self.store.append_event(
            session_id,
            event_type="ACTION_APPROVED",
            actor=actor,
            payload={"artifact_id": artifact_id},
        )
        return self.get(session_id)

    def write_back(
        self,
        contract_id: str,
        *,
        actor: str,
        mode: Literal["fixture", "datahub"] = "fixture",
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, Any]:
        snapshot = self.get(session_id)
        payload = snapshot["contracts"].get(contract_id)
        if payload is None:
            raise WorkflowNotFoundError(f"contract not found: {contract_id}")
        contract = DecisionContract.model_validate(payload)
        artifact = next(
            (
                ActionArtifact.model_validate(item)
                for item in snapshot["artifacts"].values()
                if item["contract_id"] == contract_id
            ),
            None,
        )
        if artifact is None or artifact.status is not ArtifactStatus.APPROVED:
            raise WorkflowGuardError(
                "approve this contract's validated action before write-back"
            )
        approval = MutationApproval(
            contract_id=contract_id,
            approved_by=actor,
            approved_at=_safe_action_time(contract),
        )
        if mode == "datahub":
            writer = DataHubSdkWriter(
                server=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
                token=os.getenv("DATAHUB_GMS_TOKEN"),
            )
        else:
            writer = FixtureDataHubGateway()
        receipt = writer.write_contract(contract, approval)

        snapshot.pop("events", None)
        snapshot["writeback_receipts"][contract_id] = receipt.model_dump(mode="json")
        snapshot["artifacts"][artifact.id] = artifact.model_copy(
            update={"status": ArtifactStatus.APPLIED}
        ).model_dump(mode="json")
        for card in snapshot["decisions"]:
            if card["contract_id"] == contract_id:
                card["artifact_status"] = ArtifactStatus.APPLIED.value
        self._save(snapshot)
        self.store.append_event(
            session_id,
            event_type="DATAHUB_WRITEBACK",
            actor=actor,
            payload={
                "contract_id": contract_id,
                "mode": receipt.mode,
                "retrievable": receipt.retrievable,
            },
        )
        return self.get(session_id)

    @staticmethod
    def _recorded_follow_up(
        decision_point: DecisionPoint,
        owner_turns: int,
    ) -> str | None:
        fragment = decision_point.sql_fragment.lower()
        if owner_turns == 1 and "37" in fragment:
            return (
                "Would the grace period change for prepaid accounts, and which "
                "field identifies that boundary?"
            )
        if owner_turns == 1 and "country_code" in fragment:
            return (
                "What exact date or observable migration signal makes this "
                "temporary filter safe to remove?"
            )
        if owner_turns == 1 and "account_status" in fragment:
            return (
                "Which field identifies those records, and are there any "
                "customer-type exceptions?"
            )
        return None

    def answer_interview(
        self,
        decision_id: str,
        *,
        answer: str,
        mode: Literal["recorded", "live"],
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, Any]:
        snapshot = self.get(session_id)
        card = next(
            (
                item
                for item in snapshot["decisions"]
                if item["decision_point"]["id"] == decision_id
            ),
            None,
        )
        if card is None:
            raise WorkflowNotFoundError(f"decision point not found: {decision_id}")
        decision_point = DecisionPoint.model_validate(card["decision_point"])
        live = snapshot["live_interviews"].setdefault(
            decision_id,
            {
                "decision_id": decision_id,
                "mode": mode,
                "turns": [snapshot["interviews"][decision_id]["turns"][0]],
                "ready_for_confirmation": False,
            },
        )
        turns = [InterviewTurn.model_validate(item) for item in live["turns"]]
        owner_turn = InterviewTurn(
            turn_number=len(turns) + 1,
            role=InterviewRole.OWNER,
            content=answer,
            evidence_ref=f"live-{decision_id}:turn-{len(turns) + 1}",
        )
        turns.append(owner_turn)
        if mode == "live":
            directive = DeepSeekCTAAgent(DeepSeekConfig.from_env()).next_question(
                decision_point=decision_point,
                context=QueryContext.model_validate(snapshot["context"]),
                turns=tuple(turns),
            )
            question = directive.question
            live["ready_for_confirmation"] = directive.can_draft
        else:
            owner_count = sum(turn.role is InterviewRole.OWNER for turn in turns)
            question = self._recorded_follow_up(decision_point, owner_count)
            live["ready_for_confirmation"] = question is None
        if question:
            turns.append(
                InterviewTurn(
                    turn_number=len(turns) + 1,
                    role=InterviewRole.AGENT,
                    content=question,
                    evidence_ref=f"live-{decision_id}:turn-{len(turns) + 1}",
                )
            )
        live["turns"] = [turn.model_dump(mode="json") for turn in turns]
        live["mode"] = mode
        snapshot.pop("events", None)
        self._save(snapshot)
        self.store.append_event(
            session_id,
            event_type="INTERVIEW_ANSWER_RECORDED",
            actor=DEMO_ACTOR,
            payload={"decision_id": decision_id, "mode": mode},
        )
        return self.get(session_id)
