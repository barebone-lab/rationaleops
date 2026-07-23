from __future__ import annotations

import json
from pathlib import Path

from rationaleops.cli import main


def test_mine_command_outputs_bundled_decision_points(capsys) -> None:
    result = main(["mine"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert len(output) == 3
    assert output[0]["kind"] == "DATE_WINDOW"


def test_demo_command_runs_with_explicit_fixture_approval(
    tmp_path: Path,
    capsys,
) -> None:
    result = main(
        [
            "demo",
            "--approve-writeback",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "Generated SQL test passes: True" in output
    assert "Recorded write-back visible: True" in output
    assert (tmp_path / "summary.json").exists()
