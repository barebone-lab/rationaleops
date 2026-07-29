from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rationaleops.api import create_app

ACTOR = "urn:li:corpuser:demo-owner"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            store_path=tmp_path / "state.db",
            artifact_root=tmp_path / "artifacts",
        )
    )


def test_api_health_reflects_loaded_runtime_configuration(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-only-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LLM_MODEL", "judge-model")
    monkeypatch.setenv("LLM_PROVIDER", "Judge LLM")
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")

    response = _client(tmp_path).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rationaleops",
        "version": "0.3.0",
        "datahub_server": "http://localhost:8080",
        "llm": {
            "configured": True,
            "provider": "Judge LLM",
            "model": "judge-model",
            "base_url": "https://gateway.example/v1",
            "json_mode": "auto",
            "source": "llm",
            "configuration_error": None,
        },
    }


def test_api_health_rejects_placeholder_as_configured(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "replace-with-your-api-key")

    llm = _client(tmp_path).get("/api/health").json()["llm"]

    assert llm["configured"] is False
    assert "LLM_API_KEY" in llm["configuration_error"]


def test_api_exposes_complete_recorded_snapshot(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/demo")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["invariants"]["decision_points_found"] == 3
    assert snapshot["invariants"]["downstream_count"] == 47
    assert snapshot["invariants"]["all_deterministic_checks_pass"] is True
    assert len(snapshot["graph"]["nodes"]) >= 10
    assert all(
        item["contract_status"] == "OWNER_STATED" for item in snapshot["decisions"]
    )


def test_api_enforces_confirmation_action_and_writeback_order(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    snapshot = client.get("/api/demo").json()
    card = snapshot["decisions"][0]

    response = client.post(
        f"/api/artifacts/{card['artifact_id']}/approve",
        json={"actor": ACTOR},
    )
    assert response.status_code == 409

    response = client.post(
        f"/api/contracts/{card['contract_id']}/confirm",
        json={"actor": ACTOR},
    )
    assert response.status_code == 200
    assert response.json()["contracts"][card["contract_id"]]["status"] == ("CONFIRMED")

    response = client.post(
        f"/api/artifacts/{card['artifact_id']}/approve",
        json={"actor": ACTOR},
    )
    assert response.status_code == 200
    assert response.json()["artifacts"][card["artifact_id"]]["status"] == ("APPROVED")

    response = client.post(
        f"/api/contracts/{card['contract_id']}/writeback",
        json={"actor": ACTOR, "mode": "fixture"},
    )
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["invariants"]["datahub_write_back_visible"] is True
    assert snapshot["invariants"]["unconfirmed_rationale_published"] == 0
    assert any(
        event["event_type"] == "DATAHUB_WRITEBACK" for event in snapshot["events"]
    )


def test_api_marks_expired_contract_only_after_authorized_confirmation(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    snapshot = client.get("/api/demo").json()
    card = next(
        item
        for item in snapshot["decisions"]
        if item["outcome"] == "EXPIRED_WORKAROUND"
    )

    rejected = client.post(
        f"/api/contracts/{card['contract_id']}/confirm",
        json={"actor": "urn:li:corpuser:unauthorized"},
    )
    assert rejected.status_code == 409

    confirmed = client.post(
        f"/api/contracts/{card['contract_id']}/confirm",
        json={"actor": ACTOR},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["contracts"][card["contract_id"]]["status"] == ("EXPIRED")
