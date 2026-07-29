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
    LLMConfigurationError,
    LLMResponseError,
    OpenAICompatibleConfig,
    OpenAICompatibleCTAAgent,
    llm_configuration_status,
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
    def __init__(self, contents: list[object]) -> None:
        self.contents = contents
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0)
        if isinstance(content, Exception):
            raise content
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


def _generic_agent(
    contents: list[object],
    **config_overrides,
) -> tuple[OpenAICompatibleCTAAgent, _FakeCompletions]:
    completions = _FakeCompletions(contents)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = OpenAICompatibleConfig(
        api_key=SecretStr("unit-test-key"),
        base_url="https://llm.example.test/v1",
        model="test-model",
        provider="Test provider",
        **config_overrides,
    )
    return OpenAICompatibleCTAAgent(config, client=client), completions


class _UnsupportedParameterError(RuntimeError):
    status_code = 400


class _AuthenticationError(RuntimeError):
    status_code = 401


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


def test_generic_prompt_mode_sends_only_common_chat_completion_fields() -> None:
    agent, completions = _generic_agent(
        ['{"ok": true}'],
        json_mode="prompt",
    )

    result = agent.smoke_test()

    assert result.ok is True
    assert result.json_transport == "prompt"
    assert set(completions.calls[0]) == {"model", "messages"}


def test_auto_json_mode_falls_back_when_provider_rejects_response_format() -> None:
    agent, completions = _generic_agent(
        [_UnsupportedParameterError("response_format is unsupported"), '{"ok": true}'],
        json_mode="auto",
    )

    result = agent.smoke_test()

    assert result.json_transport == "prompt"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in completions.calls[1]


def test_authentication_errors_are_not_retried_and_secrets_are_redacted() -> None:
    context, point = _active_point()
    agent, completions = _generic_agent(
        [
            _AuthenticationError(
                "bad key unit-test-key; header private-header; query private-query"
            )
        ],
        json_mode="auto",
        default_headers={"X-Private": "private-header"},
        default_query={"token": "private-query"},
    )

    with pytest.raises(LLMResponseError) as caught:
        agent.next_question(decision_point=point, context=context)

    assert len(completions.calls) == 1
    assert "unit-test-key" not in str(caught.value)
    assert "private-header" not in str(caught.value)
    assert "private-query" not in str(caught.value)


def test_smoke_test_accepts_json_fences_from_less_strict_providers() -> None:
    agent, _ = _generic_agent(
        ['```json\n{"ok": true}\n```'],
        json_mode="prompt",
    )

    assert agent.smoke_test().ok is True


def test_generic_optional_provider_fields_are_only_sent_when_configured() -> None:
    agent, completions = _generic_agent(
        ['{"ok": true}'],
        json_mode="native",
        reasoning_effort="high",
        thinking_enabled=True,
        extra_body={"vendor_flag": "enabled"},
        max_tokens=40,
        max_tokens_param="max_completion_tokens",
    )

    agent.smoke_test()

    call = completions.calls[0]
    assert call["reasoning_effort"] == "high"
    assert call["extra_body"] == {
        "vendor_flag": "enabled",
        "thinking": {"type": "enabled"},
    }
    assert call["max_completion_tokens"] == 40


def test_generic_config_loads_llm_environment_and_never_exposes_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://user:pass@gateway.test/v1?token=x")
    monkeypatch.setenv("LLM_MODEL", "gateway-model")
    monkeypatch.setenv("LLM_PROVIDER", "Judge gateway")
    monkeypatch.setenv("LLM_JSON_MODE", "prompt")

    config = OpenAICompatibleConfig.from_env()
    status = llm_configuration_status()

    assert config.api_key.get_secret_value() == "secret-test-key"
    assert config.display_base_url == "https://gateway.test/v1"
    assert status.configured is True
    assert status.provider == "Judge gateway"
    assert "secret-test-key" not in status.model_dump_json()


def test_generic_config_rejects_placeholder_setup(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("LLM_MODEL", "replace-with-your-model-id")

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        OpenAICompatibleConfig.from_env()


def test_legacy_deepseek_environment_remains_supported(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("LLM_MODEL", "replace-with-your-model-id")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    config = OpenAICompatibleConfig.from_env()

    assert config.provider == "DeepSeek"
    assert config.base_url == "https://api.deepseek.com"
    assert config.thinking_enabled is True
    assert config.source == "deepseek"


def test_standard_openai_aliases_override_untouched_placeholders(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL", "replace-with-your-model-id")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-style-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://judge-gateway.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "judge-model")

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://judge-gateway.test/v1"
    assert config.model == "judge-model"
    assert config.source == "openai"


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
