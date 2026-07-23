from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from rationaleops.datahub_gateway import load_demo_context
from rationaleops.llm import (
    DeepSeekConfig,
    DeepSeekCTAAgent,
    DeepSeekResponseError,
    LiveContractDraft,
    materialize_live_draft,
)
from rationaleops.mining import mine_decision_points
from rationaleops.models import (
    DecisionKind,
    DecisionOutcome,
    FindingType,
    InterviewRole,
    InterviewTurn,
    TruthState,
)


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def _agent(contents: list[str]) -> tuple[DeepSeekCTAAgent, _FakeCompletions]:
    completions = _FakeCompletions(contents)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = DeepSeekConfig(
        api_key=SecretStr("unit-test-key"),
        model="deepseek-v4-pro",
        thinking_enabled=True,
        reasoning_effort="high",
    )
    return DeepSeekCTAAgent(config, client=client), completions


def _active_point():
    context = load_demo_context()
    point = next(
        item
        for item in mine_decision_points(
            context.sql,
            query_urn=context.query_urn,
            dataset_urn=context.dataset_urn,
            dialect=context.dialect,
        )
        if item.kind is DecisionKind.DATE_WINDOW
    )
    return context, point


def test_live_agent_uses_thinking_json_mode_without_temperature() -> None:
    context, point = _active_point()
    agent, completions = _agent(
        [
            json.dumps(
                {
                    "phase": "BOUNDARY",
                    "question": "Which field identifies prepaid accounts?",
                    "evidence_needed": ["executable account signal"],
                    "can_draft": False,
                    "contradiction_detected": False,
                }
            )
        ]
    )

    directive = agent.next_question(decision_point=point, context=context)

    assert directive.phase == "BOUNDARY"
    call = completions.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert call["reasoning_effort"] == "high"
    assert "temperature" not in call


def test_materialized_live_draft_stays_owner_stated_and_requires_real_refs() -> None:
    context, point = _active_point()
    turns = (
        InterviewTurn(
            turn_number=1,
            role=InterviewRole.OWNER,
            content="Finance added a grace period.",
            evidence_ref="live:turn-1",
        ),
    )
    draft = LiveContractDraft(
        title="Settlement grace period",
        goal="Avoid under-reporting",
        canonical_rule="Use 37 days for postpaid accounts",
        evidence_refs=("live:turn-1",),
    )

    contract = materialize_live_draft(
        draft,
        contract_id="live-contract-1",
        decision_point=point,
        context=context,
        turns=turns,
        finding_type=FindingType.CONTRADICTORY_DECISION,
        outcome=DecisionOutcome.CONFIRMED_RULE,
    )

    assert contract.status is TruthState.OWNER_STATED
    assert contract.authority.confirmed_by is None

    bad = draft.model_copy(update={"evidence_refs": ("missing:turn-9",)})
    with pytest.raises(DeepSeekResponseError, match="visible owner turns"):
        materialize_live_draft(
            bad,
            contract_id="live-contract-2",
            decision_point=point,
            context=context,
            turns=turns,
            finding_type=FindingType.CONTRADICTORY_DECISION,
            outcome=DecisionOutcome.CONFIRMED_RULE,
        )
