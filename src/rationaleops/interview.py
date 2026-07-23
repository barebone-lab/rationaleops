"""Deterministic recorded CTA workflow for the first vertical slice."""

from __future__ import annotations

from enum import StrEnum

from rationaleops.contracts import (
    ContractTransitionError,
    draft_active_window_contract,
    draft_germany_exclusion_contract,
    draft_status_exclusion_contract,
)
from rationaleops.models import (
    DecisionContract,
    DecisionPoint,
    InterviewRole,
    InterviewTurn,
    QueryContext,
)


class InterviewPhase(StrEnum):
    INCIDENT = "INCIDENT"
    BOUNDARY = "BOUNDARY"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"


class RecordedInterview:
    """A safe deterministic fallback; it never pretends to be a live LLM."""

    def __init__(
        self,
        *,
        session_id: str,
        decision_point: DecisionPoint,
        context: QueryContext,
    ) -> None:
        self.session_id = session_id
        self.decision_point = decision_point
        self.context = context
        self.phase = InterviewPhase.INCIDENT
        self._turns: list[InterviewTurn] = []
        self._append(
            InterviewRole.AGENT,
            (
                "DataHub's active-customer glossary says activity within 30 days, "
                f"but production SQL uses `{decision_point.sql_fragment}` and "
                f"reaches {context.impact.downstream_count} downstream assets. "
                "Was 37 days deliberate? What event led to that decision?"
            ),
        )

    @property
    def turns(self) -> tuple[InterviewTurn, ...]:
        return tuple(self._turns)

    @property
    def current_question(self) -> str:
        return self._turns[-1].content

    def _append(self, role: InterviewRole, content: str) -> InterviewTurn:
        number = len(self._turns) + 1
        turn = InterviewTurn(
            turn_number=number,
            role=role,
            content=content,
            evidence_ref=f"{self.session_id}:turn-{number}",
        )
        self._turns.append(turn)
        return turn

    def answer(self, content: str) -> str | None:
        self._append(InterviewRole.OWNER, content)
        lowered = content.lower()

        if self.phase is InterviewPhase.INCIDENT:
            if not any(
                signal in lowered
                for signal in ("settlement", "capture", "under-report")
            ):
                return self._append(
                    InterviewRole.AGENT,
                    (
                        "What specific operational signal or incident made the "
                        "30-day definition insufficient?"
                    ),
                ).content
            self.phase = InterviewPhase.BOUNDARY
            return self._append(
                InterviewRole.AGENT,
                (
                    "Does the seven-day grace period also apply to prepaid "
                    "accounts? If not, which field and value identify them?"
                ),
            ).content

        if self.phase is InterviewPhase.BOUNDARY:
            missing: list[str] = []
            if "prepaid" not in lowered:
                missing.append("the affected account type")
            if "billing_type" not in lowered:
                missing.append("its identifying field")
            if "30" not in lowered:
                missing.append("the exact fallback window")
            if missing:
                return self._append(
                    InterviewRole.AGENT,
                    "Please make the boundary executable by stating "
                    + ", ".join(missing)
                    + ".",
                ).content
            self.phase = InterviewPhase.READY_FOR_CONFIRMATION
            return None

        raise ContractTransitionError(
            "the recorded interview is already ready for confirmation"
        )

    def draft_contract(self) -> DecisionContract:
        if self.phase is not InterviewPhase.READY_FOR_CONFIRMATION:
            raise ContractTransitionError("the exception boundary is not complete")
        return draft_active_window_contract(
            decision_point=self.decision_point,
            owner=self.context.owner,
            interview_turns=self.turns,
        )


class _RecordedScenarioInterview:
    """Shared evidence recording for deterministic scenario interviews."""

    def __init__(
        self,
        *,
        session_id: str,
        decision_point: DecisionPoint,
        context: QueryContext,
        initial_question: str,
    ) -> None:
        self.session_id = session_id
        self.decision_point = decision_point
        self.context = context
        self._turns: list[InterviewTurn] = []
        self._ready = False
        self._phase = 0
        self._append(InterviewRole.AGENT, initial_question)

    @property
    def turns(self) -> tuple[InterviewTurn, ...]:
        return tuple(self._turns)

    def _append(self, role: InterviewRole, content: str) -> InterviewTurn:
        number = len(self._turns) + 1
        turn = InterviewTurn(
            turn_number=number,
            role=role,
            content=content,
            evidence_ref=f"{self.session_id}:turn-{number}",
        )
        self._turns.append(turn)
        return turn

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise ContractTransitionError("the interview boundary is incomplete")


class GermanyRecordedInterview(_RecordedScenarioInterview):
    def __init__(
        self,
        *,
        session_id: str,
        decision_point: DecisionPoint,
        context: QueryContext,
    ) -> None:
        super().__init__(
            session_id=session_id,
            decision_point=decision_point,
            context=context,
            initial_question=(
                "I found no current glossary rule for excluding Germany. "
                f"Was `{decision_point.sql_fragment}` temporary, and what event "
                "made it necessary?"
            ),
        )

    def answer(self, content: str) -> str | None:
        self._append(InterviewRole.OWNER, content)
        lowered = content.lower()
        if self._phase == 0:
            if "legal" not in lowered or "migration" not in lowered:
                return self._append(
                    InterviewRole.AGENT,
                    "Which incident or policy created the Germany exclusion?",
                ).content
            self._phase = 1
            return self._append(
                InterviewRole.AGENT,
                (
                    "What exact date or observable migration signal makes the "
                    "filter safe to remove?"
                ),
            ).content
        if self._phase == 1:
            if "completed" not in lowered or "2026-06-30" not in lowered:
                return self._append(
                    InterviewRole.AGENT,
                    "Please state both the completion signal and its effective date.",
                ).content
            self._ready = True
            self._phase = 2
            return None
        raise ContractTransitionError("the Germany interview is already complete")

    def draft_contract(self) -> DecisionContract:
        self._ensure_ready()
        return draft_germany_exclusion_contract(
            decision_point=self.decision_point,
            owner=self.context.owner,
            interview_turns=self.turns,
        )


class StatusRecordedInterview(_RecordedScenarioInterview):
    def __init__(
        self,
        *,
        session_id: str,
        decision_point: DecisionPoint,
        context: QueryContext,
    ) -> None:
        super().__init__(
            session_id=session_id,
            decision_point=decision_point,
            context=context,
            initial_question=(
                "The dashboard description does not mention status exclusions. "
                f"Is `{decision_point.sql_fragment}` part of the official "
                "active-customer definition?"
            ),
        )

    def answer(self, content: str) -> str | None:
        self._append(InterviewRole.OWNER, content)
        lowered = content.lower()
        if self._phase == 0:
            if not all(word in lowered for word in ("official", "trial", "refunded")):
                return self._append(
                    InterviewRole.AGENT,
                    "Which exact statuses are authoritative exclusions?",
                ).content
            self._phase = 1
            return self._append(
                InterviewRole.AGENT,
                (
                    "Which field identifies those records, and is there any "
                    "customer type for which the exclusion should not apply?"
                ),
            ).content
        if self._phase == 1:
            if "account_status" not in lowered:
                return self._append(
                    InterviewRole.AGENT,
                    "Please name the executable identification field.",
                ).content
            self._ready = True
            self._phase = 2
            return None
        raise ContractTransitionError("the status interview is already complete")

    def draft_contract(self) -> DecisionContract:
        self._ensure_ready()
        return draft_status_exclusion_contract(
            decision_point=self.decision_point,
            owner=self.context.owner,
            interview_turns=self.turns,
        )
