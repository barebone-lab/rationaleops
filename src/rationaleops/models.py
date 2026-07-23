"""Typed domain models and trust-boundary validation for RationaleOps."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class FrozenModel(BaseModel):
    """A strict immutable model used for evidence and mined facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StrictModel(BaseModel):
    """A strict mutable model used while a workflow is progressing."""

    model_config = ConfigDict(extra="forbid")


class DecisionKind(StrEnum):
    DATE_WINDOW = "DATE_WINDOW"
    HARD_CODED_EXCLUSION = "HARD_CODED_EXCLUSION"
    CASE_BRANCH = "CASE_BRANCH"
    UNUSUAL_PREDICATE = "UNUSUAL_PREDICATE"


class TruthState(StrEnum):
    HYPOTHESIS = "HYPOTHESIS"
    OWNER_STATED = "OWNER_STATED"
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    EXPIRED = "EXPIRED"
    ORPHANED = "ORPHANED"


class DecisionPoint(FrozenModel):
    id: str
    query_urn: str
    dataset_urn: str
    sql_fragment: str
    normalized_sql: str
    sql_fingerprint: str
    ast_type: str
    kind: DecisionKind
    referenced_fields: tuple[str, ...] = ()
    literal_values: tuple[str, ...] = ()


class GlossaryContext(FrozenModel):
    term: str
    definition: str
    urn: str


class OwnerContext(FrozenModel):
    owner_urn: str
    display_name: str
    authorized_confirmers: tuple[str, ...]


class ImpactContext(FrozenModel):
    downstream_count: int = Field(ge=0)
    critical_assets: tuple[str, ...] = ()
    usage_criticality: float = Field(ge=0, le=1)
    documentation_gap: float = Field(ge=0, le=1)
    owner_bus_factor: float = Field(ge=0, le=1)
    age_or_staleness: float = Field(ge=0, le=1)


class QueryContext(FrozenModel):
    query_urn: str
    dataset_urn: str
    sql: str
    dialect: str = "postgres"
    glossary: tuple[GlossaryContext, ...] = ()
    owner: OwnerContext
    impact: ImpactContext


class RiskBoost(FrozenModel):
    reason: str
    value: float = Field(gt=0)


class RiskBreakdown(FrozenModel):
    normalized_downstream_count: float = Field(ge=0, le=1)
    downstream_impact: float = Field(ge=0)
    usage_criticality: float = Field(ge=0)
    documentation_gap: float = Field(ge=0)
    owner_bus_factor: float = Field(ge=0)
    age_or_staleness: float = Field(ge=0)
    boosts: tuple[RiskBoost, ...] = ()
    total: float = Field(ge=0, le=1)


class RankedDecisionPoint(FrozenModel):
    decision_point: DecisionPoint
    risk: RiskBreakdown


class InterviewRole(StrEnum):
    AGENT = "agent"
    OWNER = "owner"


class InterviewTurn(FrozenModel):
    turn_number: int = Field(gt=0)
    role: InterviewRole
    content: str = Field(min_length=1)
    evidence_ref: str


class ContractImplementation(FrozenModel):
    dataset_urn: str
    query_urn: str
    sql_fingerprint: str
    sql_fragment: str


class ContractIntent(FrozenModel):
    goal: str = Field(min_length=1)
    canonical_rule: str = Field(min_length=1)


class ContractScope(FrozenModel):
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


class ContractException(FrozenModel):
    when: str = Field(min_length=1)
    behavior: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ContractAuthority(FrozenModel):
    owner: str
    authorized_confirmers: tuple[str, ...] = Field(min_length=1)
    confirmed_by: str | None = None
    confirmed_at: AwareDatetime | None = None


class ContractLifecycle(FrozenModel):
    effective_from: date | None = None
    expires_at: date | None = None
    review_on: tuple[str, ...] = ()


class ContractEvidence(FrozenModel):
    interview_quote_refs: tuple[str, ...] = Field(min_length=1)
    datahub_asset_refs: tuple[str, ...] = Field(min_length=1)


class ContractVerification(FrozenModel):
    tests: tuple[str, ...] = ()
    passed: bool | None = None
    checked_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_check_pair(self) -> ContractVerification:
        if (self.passed is None) != (self.checked_at is None):
            raise ValueError("passed and checked_at must be set together")
        if self.passed is not None and not self.tests:
            raise ValueError("a validation result requires a test artifact")
        return self


class DecisionContract(StrictModel):
    id: str
    status: TruthState
    title: str = Field(min_length=1)
    implements: ContractImplementation
    intent: ContractIntent
    scope: ContractScope
    exceptions: tuple[ContractException, ...] = ()
    authority: ContractAuthority
    lifecycle: ContractLifecycle
    evidence: ContractEvidence
    verification: ContractVerification = Field(
        default_factory=ContractVerification
    )

    @model_validator(mode="after")
    def enforce_confirmation_boundary(self) -> DecisionContract:
        if self.status is TruthState.CONFIRMED:
            if not self.authority.confirmed_by or not self.authority.confirmed_at:
                raise ValueError(
                    "CONFIRMED contracts require confirmed_by and confirmed_at"
                )
            if (
                self.authority.confirmed_by
                not in self.authority.authorized_confirmers
            ):
                raise ValueError("contract confirmer is not authorized")
        elif self.status in {
            TruthState.HYPOTHESIS,
            TruthState.OWNER_STATED,
            TruthState.ORPHANED,
        } and (self.authority.confirmed_by or self.authority.confirmed_at):
            raise ValueError(
                "unconfirmed contracts cannot contain confirmation metadata"
            )
        return self


class ArtifactCheck(FrozenModel):
    artifact_path: str
    passed: bool
    failing_rows: tuple[tuple[str, ...], ...] = ()


class MutationApproval(FrozenModel):
    contract_id: str
    approved_by: str
    approved_at: AwareDatetime


class WriteBackReceipt(FrozenModel):
    contract_id: str
    dataset_urn: str
    mode: str
    written_by: str
    written_at: AwareDatetime
    retrievable: bool
