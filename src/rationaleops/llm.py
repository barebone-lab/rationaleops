"""DeepSeek V4-Pro CTA agent with typed, non-authoritative outputs."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from rationaleops.models import (
    ContractAuthority,
    ContractEvidence,
    ContractException,
    ContractImplementation,
    ContractIntent,
    ContractLifecycle,
    ContractScope,
    DecisionContract,
    DecisionOutcome,
    DecisionPoint,
    FindingType,
    InterviewRole,
    InterviewTurn,
    QueryContext,
    TruthState,
)


class DeepSeekConfigurationError(RuntimeError):
    """Raised when live-mode configuration is missing or invalid."""


class DeepSeekResponseError(RuntimeError):
    """Raised when a live response cannot satisfy the typed boundary."""


class DeepSeekConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: SecretStr
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    thinking_enabled: bool = True
    reasoning_effort: Literal["high", "max"] = "high"

    @classmethod
    def from_env(cls) -> DeepSeekConfig:
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key or "replace" in api_key.lower():
            raise DeepSeekConfigurationError(
                "DEEPSEEK_API_KEY is required for live interview mode"
            )
        effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").lower()
        if effort not in {"high", "max"}:
            raise DeepSeekConfigurationError(
                "DEEPSEEK_REASONING_EFFORT must be high or max"
            )
        thinking = os.getenv("DEEPSEEK_THINKING_ENABLED", "true").lower()
        return cls(
            api_key=SecretStr(api_key),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            thinking_enabled=thinking in {"1", "true", "yes", "on"},
            reasoning_effort=effort,
        )


class InterviewDirective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal["GROUNDING", "INCIDENT", "BOUNDARY", "LIFECYCLE", "CONFIRMATION"]
    question: str = Field(min_length=1)
    evidence_needed: tuple[str, ...] = ()
    can_draft: bool = False
    contradiction_detected: bool = False


class LiveExceptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    when: str
    behavior: str
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class LiveContractDraft(BaseModel):
    """An LLM draft that is structurally unable to claim confirmation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["OWNER_STATED"] = "OWNER_STATED"
    title: str
    goal: str
    canonical_rule: str
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    exceptions: tuple[LiveExceptionDraft, ...] = ()
    effective_from: date | None = None
    expires_at: date | None = None
    review_on: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    unknown_fields: tuple[str, ...] = ()


_SYSTEM_PROMPT = """You are the RationaleOps Cognitive Task Analysis agent.
The exact SQL, DataHub lineage, owner, glossary, and visible interview turns are
evidence. Never invent business intent, authority, dates, exceptions, or facts.
Ask one concise adaptive question using the Critical Decision Method. Prefer an
incident cue, counterfactual boundary, executable identification signal, expiry
trigger, or confirmation gap that the prior answer has not resolved. Unknown is
valid. Do not expose chain-of-thought. Output JSON only, exactly in this shape:
{
  "phase": "GROUNDING|INCIDENT|BOUNDARY|LIFECYCLE|CONFIRMATION",
  "question": "one owner-facing question",
  "evidence_needed": ["short field descriptions"],
  "can_draft": false,
  "contradiction_detected": false
}
Set can_draft true only when intent, scope, exceptions, lifecycle, authority,
and evidence references are sufficiently explicit for an OWNER_STATED draft.
"""


class DeepSeekCTAAgent:
    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self._client = client or OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
            timeout=60.0,
        )

    def _completion(self, messages: list[dict[str, str]]) -> str:
        extra_body = {
            "thinking": {
                "type": "enabled" if self.config.thinking_enabled else "disabled"
            }
        }
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            response_format={"type": "json_object"},
            reasoning_effort=self.config.reasoning_effort,
            extra_body=extra_body,
            max_tokens=1600,
        )
        content = response.choices[0].message.content
        if not content:
            raise DeepSeekResponseError("DeepSeek returned empty JSON content")
        return content

    @staticmethod
    def _context_payload(
        decision_point: DecisionPoint,
        context: QueryContext,
    ) -> dict[str, Any]:
        return {
            "decision_point": decision_point.model_dump(mode="json"),
            "datahub": {
                "downstream_count": context.impact.downstream_count,
                "critical_assets": context.impact.critical_assets,
                "owner": context.owner.model_dump(mode="json"),
                "glossary": [item.model_dump(mode="json") for item in context.glossary],
            },
        }

    def next_question(
        self,
        *,
        decision_point: DecisionPoint,
        context: QueryContext,
        turns: tuple[InterviewTurn, ...] = (),
    ) -> InterviewDirective:
        payload = self._context_payload(decision_point, context)
        payload["visible_interview_turns"] = [
            turn.model_dump(mode="json") for turn in turns
        ]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Evidence JSON:\n" + json.dumps(payload),
            },
        ]
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return InterviewDirective.model_validate_json(
                    self._completion(messages)
                )
            except (ValueError, DeepSeekResponseError) as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Return non-empty JSON matching the exact schema. "
                            "Do not add prose."
                        ),
                    }
                )
        raise DeepSeekResponseError(
            f"unable to validate DeepSeek interview directive: {last_error}"
        )

    def draft_contract(
        self,
        *,
        decision_point: DecisionPoint,
        context: QueryContext,
        turns: tuple[InterviewTurn, ...],
    ) -> LiveContractDraft:
        payload = self._context_payload(decision_point, context)
        payload["visible_interview_turns"] = [
            turn.model_dump(mode="json") for turn in turns
        ]
        schema = LiveContractDraft.model_json_schema()
        prompt = (
            "Draft an OWNER_STATED Decision Contract from owner statements only. "
            "Preserve unknown fields and cite exact owner evidence_ref values. "
            "Never output CONFIRMED. Output JSON matching this schema:\n"
            + json.dumps(schema)
            + "\nEvidence JSON:\n"
            + json.dumps(payload)
        )
        content = self._completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You structure owner evidence into JSON. Never infer or "
                        "authorize intent and never expose chain-of-thought."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
        try:
            return LiveContractDraft.model_validate_json(content)
        except ValueError as exc:
            raise DeepSeekResponseError(
                "DeepSeek contract draft failed typed validation"
            ) from exc


def materialize_live_draft(
    draft: LiveContractDraft,
    *,
    contract_id: str,
    decision_point: DecisionPoint,
    context: QueryContext,
    turns: tuple[InterviewTurn, ...],
    finding_type: FindingType,
    outcome: DecisionOutcome,
) -> DecisionContract:
    """Attach deterministic identity and authority to a non-authoritative draft."""

    owner_refs = {
        turn.evidence_ref for turn in turns if turn.role is InterviewRole.OWNER
    }
    cited_refs = set(draft.evidence_refs)
    for exception in draft.exceptions:
        cited_refs.update(exception.evidence_refs)
    if not cited_refs or not cited_refs.issubset(owner_refs):
        raise DeepSeekResponseError(
            "contract citations must reference visible owner turns"
        )
    return DecisionContract(
        id=contract_id,
        status=TruthState.OWNER_STATED,
        finding_type=finding_type,
        outcome=outcome,
        title=draft.title,
        implements=ContractImplementation(
            dataset_urn=decision_point.dataset_urn,
            query_urn=decision_point.query_urn,
            sql_fingerprint=decision_point.sql_fingerprint,
            sql_fragment=decision_point.sql_fragment,
        ),
        intent=ContractIntent(
            goal=draft.goal,
            canonical_rule=draft.canonical_rule,
        ),
        scope=ContractScope(
            includes=draft.includes,
            excludes=draft.excludes,
        ),
        exceptions=tuple(
            ContractException(
                when=item.when,
                behavior=item.behavior,
                evidence_refs=item.evidence_refs,
            )
            for item in draft.exceptions
        ),
        authority=ContractAuthority(
            owner=context.owner.owner_urn,
            authorized_confirmers=context.owner.authorized_confirmers,
        ),
        lifecycle=ContractLifecycle(
            effective_from=draft.effective_from,
            expires_at=draft.expires_at,
            review_on=draft.review_on,
        ),
        evidence=ContractEvidence(
            interview_quote_refs=draft.evidence_refs,
            datahub_asset_refs=(decision_point.dataset_urn,),
        ),
    )
