from __future__ import annotations

import json
from pathlib import Path

from rationaleops.full_workflow import run_recorded_full_demo


def test_full_demo_produces_three_distinct_verified_outcomes(
    tmp_path: Path,
) -> None:
    summary = run_recorded_full_demo(
        output_dir=tmp_path,
        approve_actions=False,
        approve_writeback=False,
    )

    assert summary["decision_points_found"] == 3
    assert set(summary["outcomes"]) == {
        "CONFIRMED_RULE",
        "EXPIRED_WORKAROUND",
        "DOCUMENTATION_DRIFT",
    }
    assert summary["generated_test_passes"] is True
    assert summary["expired_workaround_patch_passes"] is True
    assert summary["documentation_update_valid"] is True
    assert summary["unconfirmed_rationale_published"] == 0
    assert summary["datahub_write_back_visible"] is False
    assert (tmp_path / "active_window/test_active_window.sql").exists()
    assert (tmp_path / "germany/remove_germany_filter.patch").exists()
    assert (tmp_path / "status/glossary_update.diff").exists()


def test_full_demo_records_item_approvals_and_retrievable_writes(
    tmp_path: Path,
) -> None:
    summary = run_recorded_full_demo(
        output_dir=tmp_path,
        approve_actions=True,
        approve_writeback=True,
    )

    assert summary["actions_approved"] is True
    assert summary["writeback_approved"] is True
    assert summary["datahub_write_back_visible"] is True
    assert len(summary["writeback_receipts"]) == 3
    actions = json.loads((tmp_path / "actions.json").read_text())
    assert len(actions["approvals"]) == 3
    assert all(item["status"] == "APPROVED" for item in actions["artifacts"])
