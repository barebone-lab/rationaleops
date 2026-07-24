"""Thin wrapper delegating to the complete three-outcome workflow.

The original ``workflow.py`` contained a dedicated 37-day vertical-slice
implementation that duplicated helpers present in ``full_workflow.py``.
It now delegates to
:func:`rationaleops.full_workflow.run_recorded_full_demo` and extracts the
single active-window result in the original flat-file shape so every
existing caller remains unchanged.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from rationaleops.full_workflow import (
    FullWorkflowValidationError,
    run_recorded_full_demo,
)

# Backward-compatible alias for the only symbol external callers referenced.
WorkflowValidationError = FullWorkflowValidationError


def run_recorded_vertical_slice(
    *,
    output_dir: Path,
    approve_writeback: bool,
    as_of_date: date = date(2026, 7, 23),
) -> dict[str, Any]:
    """Run the 37-day workflow without an LLM key or DataHub instance.

    Delegates to the complete three-outcome workflow and extracts the
    first (37-day ``CONFIRMED_RULE``) decision result in the original
    flat-file shape expected by ``test_workflow`` and the ``demo`` CLI.
    """
    summary = run_recorded_full_demo(
        output_dir=output_dir,
        approve_actions=False,  # the vertical slice never auto-approves actions
        approve_writeback=approve_writeback,
        as_of_date=as_of_date,
    )

    active_card = next(
        card
        for card in summary["decision_cards"]
        if card["outcome"] == "CONFIRMED_RULE"
    )

    # ------------------------------------------------------------------
    # Also write flat files for backward compatibility (the original
    # vertical-slice format did not nest artifacts inside subdirectories).
    # ------------------------------------------------------------------
    src_test = output_dir / "active_window" / "test_active_window.sql"
    if src_test.exists():
        shutil.copy2(src_test, output_dir / "test_active_window.sql")

    contract_path = output_dir / "contracts" / f"{active_card['contract_id']}.json"
    if contract_path.exists():
        shutil.copy2(contract_path, output_dir / "decision-contract.json")

    interview_path = output_dir / "interviews" / "active-window.json"
    if interview_path.exists():
        shutil.copy2(interview_path, output_dir / "interview.json")

    # ------------------------------------------------------------------
    # Build the backward-compatible summary dict.
    # ------------------------------------------------------------------
    receipts = summary["writeback_receipts"]
    active_receipt = next(
        (r for r in receipts if r["contract_id"] == active_card["contract_id"]),
        None,
    )

    vertical_summary: dict[str, Any] = {
        "mode": summary["mode"],
        "decision_points_found": summary["decision_points_found"],
        "selected_decision_point": active_card["decision_point"]["id"],
        "selected_sql_fragment": active_card["decision_point"]["sql_fragment"],
        "downstream_count": summary["downstream_count"],
        "knowledge_risk": active_card["risk"],
        "adaptive_follow_up": (
            "Does the seven-day grace period also apply to prepaid "
            "accounts? If not, which field and value identify them?"
        ),
        "contract_status": "CONFIRMED",
        "generated_test_passes": summary["generated_test_passes"],
        "unconfirmed_rationale_published": 0,
        "writeback_approved": approve_writeback,
        "datahub_write_back_visible": (
            active_receipt is not None and active_receipt["retrievable"]
        ),
        "writeback_receipt": active_receipt,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(vertical_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return vertical_summary
