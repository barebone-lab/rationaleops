"""Deterministic recorded CTA workflow for the first vertical slice."""

from __future__ import annotations

from enum import StrEnum

from rationaleops.contracts import (
    ContractTransitionError,
    draft_active_window_contract,
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
            raise ContractTransitionError(
                "the exception boundary is not complete"
            )
        return draft_active_window_contract(
            decision_point=self.decision_point,
            owner=self.context.owner,
            interview_turns=self.turns,
        )
