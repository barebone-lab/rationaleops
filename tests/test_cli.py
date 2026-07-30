from __future__ import annotations

import json
from pathlib import Path

from rationaleops.cli import main
from rationaleops.llm import LLMCheckResult, OpenAICompatibleCTAAgent


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


def test_llm_check_reports_provider_without_printing_key(
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "super-secret-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LLM_MODEL", "judge-model")
    monkeypatch.setenv("LLM_PROVIDER", "Judge LLM")
    monkeypatch.setattr(
        OpenAICompatibleCTAAgent,
        "smoke_test",
        lambda self: LLMCheckResult(
            provider=self.config.provider,
            model=self.config.model,
            base_url=self.config.display_base_url,
            json_transport="native",
        ),
    )

    result = main(["llm-check"])
    output = capsys.readouterr().out

    assert result == 0
    assert "LLM check passed" in output
    assert "Judge LLM" in output
    assert "super-secret-test-key" not in output
