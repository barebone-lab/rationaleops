"""Decision Contract drafting and explicit state transitions."""

from __future__ import annotations

from datetime import UTC, datetime

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
    OwnerContext,
    TruthState,
)


class ContractTransitionError(ValueError):
    """Raised when a truth-state transition would cross the trust boundary."""


_ALLOWED_TRANSITIONS: dict[TruthState, set[TruthState]] = {
    TruthState.HYPOTHESIS: {
        TruthState.OWNER_STATED,
        TruthState.CONTRADICTED,
        TruthState.ORPHANED,
    },
    TruthState.OWNER_STATED: {
        TruthState.CONFIRMED,
        TruthState.CONTRADICTED,
        TruthState.ORPHANED,
    },
    TruthState.CONFIRMED: {
        TruthState.CONTRADICTED,
        TruthState.EXPIRED,
    },
    TruthState.CONTRADICTED: {
        TruthState.OWNER_STATED,
        TruthState.CONFIRMED,
        TruthState.ORPHANED,
    },
    TruthState.EXPIRED: {TruthState.CONTRADICTED},
    TruthState.ORPHANED: {
        TruthState.OWNER_STATED,
        TruthState.CONTRADICTED,
    },
}


def draft_active_window_contract(
    *,
    decision_point: DecisionPoint,
    owner: OwnerContext,
    interview_turns: tuple[InterviewTurn, ...],
) -> DecisionContract:
    """Build the seeded first-slice contract only from owner evidence."""

    owner_turns = tuple(
        turn for turn in interview_turns if turn.role is InterviewRole.OWNER
    )
    combined_answer = " ".join(turn.content.lower() for turn in owner_turns)
    required_signals = {
        "settlement rationale": ("settlement", "capture"),
        "prepaid exception": ("prepaid",),
        "exception field": ("billing_type",),
        "30-day boundary": ("30",),
    }
    missing = [
        label
        for label, signals in required_signals.items()
        if not any(signal in combined_answer for signal in signals)
    ]
    if missing:
        raise ContractTransitionError(
            "owner evidence is incomplete: " + ", ".join(missing)
        )

    quote_refs = tuple(turn.evidence_ref for turn in owner_turns)
    exception_ref = next(
        turn.evidence_ref for turn in owner_turns if "prepaid" in turn.content.lower()
    )
    return DecisionContract(
        id="decision-active-window-v1",
        status=TruthState.OWNER_STATED,
        finding_type=FindingType.CONTRADICTORY_DECISION,
        outcome=DecisionOutcome.CONFIRMED_RULE,
        title="Seven-day settlement grace period",
        implements=ContractImplementation(
            dataset_urn=decision_point.dataset_urn,
            query_urn=decision_point.query_urn,
            sql_fingerprint=decision_point.sql_fingerprint,
            sql_fragment=decision_point.sql_fragment,
        ),
        intent=ContractIntent(
            goal="Prevent under-reporting caused by late card settlement",
            canonical_rule=(
                "Activity within 30 days plus a seven-day grace period "
                "for postpaid accounts"
            ),
        ),
        scope=ContractScope(
            includes=("postpaid accounts",),
            excludes=("prepaid accounts from the grace period",),
        ),
        exceptions=(
            ContractException(
                when="billing_type = 'prepaid'",
                behavior="use a 30-day activity window",
                evidence_refs=(exception_ref,),
            ),
        ),
        authority=ContractAuthority(
            owner=owner.owner_urn,
            authorized_confirmers=owner.authorized_confirmers,
        ),
        lifecycle=ContractLifecycle(
            effective_from=None,
            expires_at=None,
            review_on=(
                "settlement_provider_change",
                "glossary_definition_change",
            ),
        ),
        evidence=ContractEvidence(
            interview_quote_refs=quote_refs,
            datahub_asset_refs=(decision_point.dataset_urn,),
        ),
    )


def draft_germany_exclusion_contract(
    *,
    decision_point: DecisionPoint,
    owner: OwnerContext,
    interview_turns: tuple[InterviewTurn, ...],
) -> DecisionContract:
    """Build the temporary Germany legal-hold contract from owner evidence."""

    owner_turns = tuple(
        turn for turn in interview_turns if turn.role is InterviewRole.OWNER
    )
    combined = " ".join(turn.content.lower() for turn in owner_turns)
    required = ("legal", "migration", "completed", "2026-06-30")
    missing = [signal for signal in required if signal not in combined]
    if missing:
        raise ContractTransitionError(
            "owner evidence is incomplete: " + ", ".join(missing)
        )
    quote_refs = tuple(turn.evidence_ref for turn in owner_turns)
    return DecisionContract(
        id="decision-germany-hold-v1",
        status=TruthState.OWNER_STATED,
        finding_type=FindingType.EXPIRED_DECISION,
        outcome=DecisionOutcome.EXPIRED_WORKAROUND,
        title="Temporary Germany legal hold",
        implements=ContractImplementation(
            dataset_urn=decision_point.dataset_urn,
            query_urn=decision_point.query_urn,
            sql_fingerprint=decision_point.sql_fingerprint,
            sql_fragment=decision_point.sql_fragment,
        ),
        intent=ContractIntent(
            goal="Pause German revenue reporting during the EU billing migration",
            canonical_rule=(
                "Exclude Germany only until the EU billing migration is complete"
            ),
        ),
        scope=ContractScope(
            includes=("all countries after migration completion",),
            excludes=("Germany before migration completion",),
        ),
        authority=ContractAuthority(
            owner=owner.owner_urn,
            authorized_confirmers=owner.authorized_confirmers,
        ),
        lifecycle=ContractLifecycle(
            effective_from=None,
            expires_at=datetime(2026, 6, 30, tzinfo=UTC).date(),
            review_on=("eu_billing_migration_complete",),
        ),
        evidence=ContractEvidence(
            interview_quote_refs=quote_refs,
            datahub_asset_refs=(decision_point.dataset_urn,),
        ),
    )


def draft_status_exclusion_contract(
    *,
    decision_point: DecisionPoint,
    owner: OwnerContext,
    interview_turns: tuple[InterviewTurn, ...],
) -> DecisionContract:
    """Build the official trial/refund definition contract from owner evidence."""

    owner_turns = tuple(
        turn for turn in interview_turns if turn.role is InterviewRole.OWNER
    )
    combined = " ".join(turn.content.lower() for turn in owner_turns)
    required = ("trial", "refunded", "account_status", "official")
    missing = [signal for signal in required if signal not in combined]
    if missing:
        raise ContractTransitionError(
            "owner evidence is incomplete: " + ", ".join(missing)
        )
    quote_refs = tuple(turn.evidence_ref for turn in owner_turns)
    return DecisionContract(
        id="decision-active-status-v1",
        status=TruthState.OWNER_STATED,
        finding_type=FindingType.CONTRADICTORY_DECISION,
        outcome=DecisionOutcome.DOCUMENTATION_DRIFT,
        title="Official trial and refund exclusion",
        implements=ContractImplementation(
            dataset_urn=decision_point.dataset_urn,
            query_urn=decision_point.query_urn,
            sql_fingerprint=decision_point.sql_fingerprint,
            sql_fragment=decision_point.sql_fragment,
        ),
        intent=ContractIntent(
            goal="Keep non-revenue accounts out of active-customer reporting",
            canonical_rule=(
                "Active customers exclude trial and refunded account statuses"
            ),
        ),
        scope=ContractScope(
            includes=("revenue-eligible customer accounts",),
            excludes=("trial accounts", "refunded accounts"),
        ),
        authority=ContractAuthority(
            owner=owner.owner_urn,
            authorized_confirmers=owner.authorized_confirmers,
        ),
        lifecycle=ContractLifecycle(
            effective_from=None,
            expires_at=None,
            review_on=("account_status_taxonomy_change",),
        ),
        evidence=ContractEvidence(
            interview_quote_refs=quote_refs,
            datahub_asset_refs=(decision_point.dataset_urn,),
        ),
    )


def transition_contract(
    contract: DecisionContract,
    target: TruthState,
    *,
    actor: str | None = None,
    occurred_at: datetime | None = None,
) -> DecisionContract:
    """Apply a validated truth-state transition."""

    allowed = _ALLOWED_TRANSITIONS[contract.status]
    if target not in allowed:
        raise ContractTransitionError(
            f"transition {contract.status} -> {target} is not allowed"
        )

    payload = contract.model_dump(mode="python")
    payload["status"] = target
    if target is TruthState.CONFIRMED:
        if actor is None:
            raise ContractTransitionError("confirmation requires an actor")
        if actor not in contract.authority.authorized_confirmers:
            raise ContractTransitionError(
                f"{actor} is not authorized to confirm this contract"
            )
        payload["authority"]["confirmed_by"] = actor
        payload["authority"]["confirmed_at"] = occurred_at or datetime.now(UTC)
    elif target in {
        TruthState.HYPOTHESIS,
        TruthState.OWNER_STATED,
        TruthState.ORPHANED,
    }:
        payload["authority"]["confirmed_by"] = None
        payload["authority"]["confirmed_at"] = None

    return DecisionContract.model_validate(payload)
