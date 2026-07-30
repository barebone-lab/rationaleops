"""OpenAI-compatible CTA agent with typed, non-authoritative outputs."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

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


class LLMConfigurationError(RuntimeError):
    """Raised when live-mode configuration is missing or invalid."""


class LLMResponseError(RuntimeError):
    """Raised when a live response cannot satisfy the typed boundary."""


class LLMRequestError(LLMResponseError):
    """Raised when the configured provider rejects or cannot serve a request."""


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return not normalized or any(
        marker in normalized
        for marker in (
            "replace-with",
            "replace_me",
            "your-api-key",
            "your-model-id",
            "<secret>",
            "<model>",
        )
    )


def _first_real_env(*names: str) -> tuple[str | None, str | None]:
    for name in names:
        value = os.getenv(name)
        if not _is_placeholder(value):
            return name, value.strip() if value else None
    return None, None


def _optional_bool(name: str, *, fallback: str | None = None) -> bool | None:
    value = os.getenv(name)
    if value is None and fallback:
        value = os.getenv(fallback)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise LLMConfigurationError(f"{name} must be true/false, yes/no, on/off, or 1/0")


def _json_object_env(name: str) -> dict[str, Any]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMConfigurationError(f"{name} must contain valid JSON") from exc
    if not isinstance(value, dict):
        raise LLMConfigurationError(f"{name} must contain a JSON object")
    return value


def _positive_int_env(name: str, *, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise LLMConfigurationError(f"{name} must be a positive integer")
    return value


def _positive_float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise LLMConfigurationError(f"{name} must be a positive number")
    return value


def _safe_base_url(value: str) -> str:
    """Remove credentials, query parameters, and fragments before display."""

    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    return urlunsplit((parsed.scheme, hostname, parsed.path, "", ""))


def _infer_provider(base_url: str) -> str:
    hostname = (urlsplit(base_url).hostname or "").lower()
    if hostname == "api.openai.com":
        return "OpenAI"
    if hostname == "api.deepseek.com":
        return "DeepSeek"
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return "Local OpenAI-compatible"
    return "OpenAI-compatible"


class OpenAICompatibleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: SecretStr
    base_url: str = "https://api.openai.com/v1"
    model: str
    provider: str = "OpenAI-compatible"
    json_mode: Literal["auto", "native", "prompt"] = "auto"
    reasoning_effort: str | None = None
    thinking_enabled: bool | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    default_headers: dict[str, str] = Field(default_factory=dict)
    default_query: dict[str, Any] = Field(default_factory=dict)
    organization: str | None = None
    project: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_tokens: int | None = Field(default=None, gt=0)
    max_tokens_param: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    source: Literal["llm", "openai", "deepseek"] = "llm"

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")
        return normalized

    @field_validator("model", "provider")
    @classmethod
    def _validate_non_placeholder(cls, value: str) -> str:
        if _is_placeholder(value):
            raise ValueError("value must not be a placeholder")
        return value.strip()

    @property
    def display_base_url(self) -> str:
        return _safe_base_url(self.base_url)

    @classmethod
    def from_env(cls) -> OpenAICompatibleConfig:
        load_dotenv()
        key_name, api_key = _first_real_env(
            "LLM_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
        )
        if not api_key:
            raise LLMConfigurationError(
                "Set LLM_API_KEY (or OPENAI_API_KEY) for live mode. "
                "For a local server without authentication, set "
                "LLM_API_KEY=not-required."
            )

        source = {
            "LLM_API_KEY": "llm",
            "OPENAI_API_KEY": "openai",
            "DEEPSEEK_API_KEY": "deepseek",
        }[key_name]
        _, generic_model = _first_real_env("LLM_MODEL")
        legacy_deepseek = source == "deepseek" and generic_model is None

        if legacy_deepseek:
            _, model = _first_real_env("DEEPSEEK_MODEL")
            model = model or "deepseek-v4-pro"
            base_url = os.getenv(
                "DEEPSEEK_BASE_URL",
                "https://api.deepseek.com",
            )
            provider = "DeepSeek"
            reasoning_effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
            thinking_enabled = _optional_bool("DEEPSEEK_THINKING_ENABLED")
            if thinking_enabled is None:
                thinking_enabled = True
            json_mode = os.getenv("LLM_JSON_MODE", "auto").strip().lower()
            max_tokens = _positive_int_env("LLM_MAX_TOKENS", default=1600)
        else:
            _, model = _first_real_env("LLM_MODEL", "OPENAI_MODEL")
            if not model:
                raise LLMConfigurationError(
                    "Set LLM_MODEL to a Chat Completions model ID exposed by "
                    "your provider."
                )
            if source == "openai" and generic_model is None:
                base_url = (
                    os.getenv("OPENAI_BASE_URL")
                    or os.getenv("LLM_BASE_URL")
                    or "https://api.openai.com/v1"
                )
            else:
                base_url = (
                    os.getenv("LLM_BASE_URL")
                    or os.getenv("OPENAI_BASE_URL")
                    or "https://api.openai.com/v1"
                )
            provider = os.getenv("LLM_PROVIDER") or _infer_provider(base_url)
            reasoning_effort = os.getenv("LLM_REASONING_EFFORT")
            thinking_enabled = _optional_bool("LLM_THINKING_ENABLED")
            json_mode = os.getenv("LLM_JSON_MODE", "auto").strip().lower()
            max_tokens = _positive_int_env("LLM_MAX_TOKENS")

        if json_mode not in {"auto", "native", "prompt"}:
            raise LLMConfigurationError("LLM_JSON_MODE must be auto, native, or prompt")
        raw_token_param = os.getenv("LLM_MAX_TOKENS_PARAM", "max_tokens")
        if raw_token_param not in {"max_tokens", "max_completion_tokens"}:
            raise LLMConfigurationError(
                "LLM_MAX_TOKENS_PARAM must be max_tokens or max_completion_tokens"
            )

        try:
            return cls(
                api_key=SecretStr(api_key),
                base_url=base_url,
                model=model,
                provider=provider,
                json_mode=json_mode,
                reasoning_effort=(
                    reasoning_effort.strip() if reasoning_effort else None
                ),
                thinking_enabled=thinking_enabled,
                extra_body=_json_object_env("LLM_EXTRA_BODY_JSON"),
                default_headers={
                    str(key): str(value)
                    for key, value in _json_object_env(
                        "LLM_DEFAULT_HEADERS_JSON"
                    ).items()
                },
                default_query=_json_object_env("LLM_DEFAULT_QUERY_JSON"),
                organization=os.getenv("LLM_ORGANIZATION") or None,
                project=os.getenv("LLM_PROJECT") or None,
                timeout_seconds=_positive_float_env(
                    "LLM_TIMEOUT_SECONDS",
                    default=60.0,
                ),
                max_tokens=max_tokens,
                max_tokens_param=raw_token_param,
                source=source,
            )
        except ValueError as exc:
            raise LLMConfigurationError(f"Invalid LLM configuration: {exc}") from exc


class LLMConfigurationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    configured: bool
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    json_mode: str | None = None
    source: str | None = None
    configuration_error: str | None = None


def llm_configuration_status() -> LLMConfigurationStatus:
    """Return a secret-free configuration summary without contacting a provider."""

    try:
        config = OpenAICompatibleConfig.from_env()
    except (LLMConfigurationError, ValueError) as exc:
        return LLMConfigurationStatus(
            configured=False,
            configuration_error=str(exc),
        )
    return LLMConfigurationStatus(
        configured=True,
        provider=config.provider,
        model=config.model,
        base_url=config.display_base_url,
        json_mode=config.json_mode,
        source=config.source,
    )


class LLMCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True] = True
    provider: str
    model: str
    base_url: str
    json_transport: Literal["native", "prompt"]


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


class OpenAICompatibleCTAAgent:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self.last_json_transport: Literal["native", "prompt"] = "prompt"
        if client is None:
            client_kwargs: dict[str, Any] = {
                "api_key": config.api_key.get_secret_value(),
                "base_url": config.base_url,
                "timeout": config.timeout_seconds,
            }
            if config.default_headers:
                client_kwargs["default_headers"] = config.default_headers
            if config.default_query:
                client_kwargs["default_query"] = config.default_query
            if config.organization:
                client_kwargs["organization"] = config.organization
            if config.project:
                client_kwargs["project"] = config.project
            self._client = OpenAI(**client_kwargs)
        else:
            self._client = client

    def _request_kwargs(
        self,
        messages: list[dict[str, str]],
        *,
        native_json: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }
        if native_json:
            kwargs["response_format"] = {"type": "json_object"}
        if self.config.reasoning_effort:
            kwargs["reasoning_effort"] = self.config.reasoning_effort
        extra_body = dict(self.config.extra_body)
        if self.config.thinking_enabled is not None:
            extra_body.setdefault(
                "thinking",
                {"type": ("enabled" if self.config.thinking_enabled else "disabled")},
            )
        if extra_body:
            kwargs["extra_body"] = extra_body
        if self.config.max_tokens is not None:
            kwargs[self.config.max_tokens_param] = self.config.max_tokens
        return kwargs

    @staticmethod
    def _native_json_can_fallback(exc: Exception) -> bool:
        return isinstance(exc, TypeError) or getattr(exc, "status_code", None) in {
            400,
            405,
            415,
            422,
            501,
        }

    def _safe_response_error(self, exc: Exception) -> LLMRequestError:
        secret = self.config.api_key.get_secret_value()
        detail = str(exc).replace(self.config.base_url, self.config.display_base_url)
        sensitive_values = [
            secret,
            *self.config.default_headers.values(),
            *(str(value) for value in self.config.default_query.values()),
        ]
        for value in sensitive_values:
            if len(value) >= 4:
                detail = detail.replace(value, "[redacted]")
        status = getattr(exc, "status_code", None)
        prefix = f"HTTP {status}: " if status else ""
        return LLMRequestError(
            f"{self.config.provider} Chat Completions request failed: {prefix}{detail}"
        )

    @staticmethod
    def _json_text(content: str) -> str:
        """Accept plain JSON or a single JSON object wrapped in prose/fences."""

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().lower() in {"```", "```json"}:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.dumps(json.loads(text))
        except json.JSONDecodeError:
            start = text.find("{")
            if start >= 0:
                try:
                    value, _ = json.JSONDecoder().raw_decode(text[start:])
                    return json.dumps(value)
                except json.JSONDecodeError:
                    pass
        return text

    def _send(
        self,
        messages: list[dict[str, str]],
        *,
        native_json: bool,
    ) -> str:
        response = self._client.chat.completions.create(
            **self._request_kwargs(messages, native_json=native_json)
        )
        content = response.choices[0].message.content
        if not content or not isinstance(content, str):
            raise LLMResponseError(
                f"{self.config.provider} returned empty JSON content"
            )
        self.last_json_transport = "native" if native_json else "prompt"
        return self._json_text(content)

    def _completion(self, messages: list[dict[str, str]]) -> str:
        if self.config.json_mode == "prompt":
            try:
                return self._send(messages, native_json=False)
            except LLMResponseError:
                raise
            except Exception as exc:
                raise self._safe_response_error(exc) from exc

        try:
            return self._send(messages, native_json=True)
        except LLMResponseError:
            raise
        except Exception as exc:
            if self.config.json_mode == "auto" and self._native_json_can_fallback(exc):
                try:
                    return self._send(messages, native_json=False)
                except LLMResponseError:
                    raise
                except Exception as fallback_exc:
                    raise self._safe_response_error(fallback_exc) from fallback_exc
            raise self._safe_response_error(exc) from exc

    def smoke_test(self) -> LLMCheckResult:
        """Make one small real request and validate the common JSON contract."""

        content = self._completion(
            [
                {
                    "role": "system",
                    "content": "Return JSON only. Do not add prose or markdown.",
                },
                {
                    "role": "user",
                    "content": 'Return exactly this JSON object: {"ok": true}',
                },
            ]
        )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"{self.config.provider} responded, but did not return valid JSON"
            ) from exc
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise LLMResponseError(
                f"{self.config.provider} responded, but failed the JSON smoke test"
            )
        return LLMCheckResult(
            provider=self.config.provider,
            model=self.config.model,
            base_url=self.config.display_base_url,
            json_transport=self.last_json_transport,
        )

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
            except LLMRequestError:
                raise
            except (ValueError, LLMResponseError) as exc:
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
        raise LLMResponseError(
            f"unable to validate the LLM interview directive: {last_error}"
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
            raise LLMResponseError(
                "LLM contract draft failed typed validation"
            ) from exc


class DeepSeekConfig(OpenAICompatibleConfig):
    """Backward-compatible explicit DeepSeek configuration."""

    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    provider: str = "DeepSeek"
    json_mode: Literal["auto", "native", "prompt"] = "auto"
    reasoning_effort: str | None = "high"
    thinking_enabled: bool | None = True
    max_tokens: int | None = 1600
    source: Literal["llm", "openai", "deepseek"] = "deepseek"

    @classmethod
    def from_env(cls) -> DeepSeekConfig:
        load_dotenv()
        _, api_key = _first_real_env("DEEPSEEK_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "DEEPSEEK_API_KEY is required for legacy DeepSeek configuration"
            )
        thinking = _optional_bool("DEEPSEEK_THINKING_ENABLED")
        return cls(
            api_key=SecretStr(api_key),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            reasoning_effort=os.getenv("DEEPSEEK_REASONING_EFFORT", "high"),
            thinking_enabled=True if thinking is None else thinking,
        )


# Source-level compatibility for integrations that imported the old names.
DeepSeekConfigurationError = LLMConfigurationError
DeepSeekResponseError = LLMResponseError
DeepSeekCTAAgent = OpenAICompatibleCTAAgent


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
        raise LLMResponseError("contract citations must reference visible owner turns")
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
