from __future__ import annotations

import json
from pathlib import Path

from rationaleops.workflow import run_recorded_vertical_slice


def test_recorded_vertical_slice_preserves_approval_boundary(
    tmp_path: Path,
) -> None:
    summary = run_recorded_vertical_slice(
        output_dir=tmp_path,
        approve_writeback=False,
    )

    assert summary["decision_points_found"] == 3
    assert summary["contract_status"] == "CONFIRMED"
    assert summary["generated_test_passes"] is True
    assert summary["unconfirmed_rationale_published"] == 0
    assert summary["datahub_write_back_visible"] is False
    assert "prepaid" in summary["adaptive_follow_up"].lower()


def test_recorded_vertical_slice_writes_and_reads_after_explicit_approval(
    tmp_path: Path,
) -> None:
    summary = run_recorded_vertical_slice(
        output_dir=tmp_path,
        approve_writeback=True,
    )

    assert summary["datahub_write_back_visible"] is True
    assert (tmp_path / "test_active_window.sql").exists()
    assert (tmp_path / "decision-contract.json").exists()
    persisted_summary = json.loads(
        (tmp_path / "summary.json").read_text(encoding="utf-8")
    )
    assert persisted_summary == summary
