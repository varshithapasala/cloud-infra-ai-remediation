import sqlite3

import pytest
from fastapi.testclient import TestClient

import incident_api.main as incident_api


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    database_path = tmp_path / "incidents.db"

    connection = sqlite3.connect(database_path)

    connection.executescript(
        """
        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_name TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            evidence_json TEXT,
            status TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            resolved_at TEXT,
            ai_summary TEXT,
            ai_root_cause TEXT,
            ai_recommendation TEXT
        );

        CREATE TABLE actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT,
            executed_at TEXT NOT NULL
        );

        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_name TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            started_at TEXT NOT NULL,
            recovered_at TEXT,
            recovery_seconds REAL,
            result TEXT NOT NULL,
            details TEXT
        );
        """
    )

    connection.execute(
        """
        INSERT INTO incidents (
            resource_name,
            incident_type,
            severity,
            description,
            evidence_json,
            status,
            detected_at,
            resolved_at,
            ai_summary,
            ai_root_cause,
            ai_recommendation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "order-api",
            "CONTAINER_STOPPED",
            "HIGH",
            "The API container stopped",
            '{"container_status": "exited"}',
            "RESOLVED",
            "2026-06-25T10:00:00+00:00",
            "2026-06-25T10:00:20+00:00",
            "The API container was unavailable",
            "The container was manually stopped",
            "Restart the approved container",
        ),
    )

    connection.execute(
        """
        INSERT INTO actions (
            incident_id,
            action_type,
            result,
            details,
            executed_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            "restart",
            "SUCCESS",
            "Container restarted successfully",
            "2026-06-25T10:00:10+00:00",
        ),
    )

    connection.execute(
        """
        INSERT INTO experiments (
            scenario_name,
            resource_name,
            started_at,
            recovered_at,
            recovery_seconds,
            result,
            details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "STOP_API",
            "order-api",
            "2026-06-25T10:00:00+00:00",
            "2026-06-25T10:00:20+00:00",
            20.0,
            "SUCCESS",
            "API recovered successfully",
        ),
    )

    connection.execute(
        """
        INSERT INTO experiments (
            scenario_name,
            resource_name,
            started_at,
            recovered_at,
            recovery_seconds,
            result,
            details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "STOP_WORKER",
            "order-worker",
            "2026-06-25T11:00:00+00:00",
            None,
            120.0,
            "FAILED",
            "Worker did not recover in time",
        ),
    )

    connection.commit()
    connection.close()

    monkeypatch.setattr(
        incident_api,
        "DATABASE_PATH",
        database_path,
    )

    return database_path


@pytest.fixture
def client(test_database):
    return TestClient(incident_api.app)


def test_health_returns_healthy(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "incident-api"
    assert data["database_available"] is True


def test_list_incidents(client):
    response = client.get("/incidents")

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert data["incidents"][0]["resource_name"] == "order-api"
    assert data["incidents"][0]["status"] == "RESOLVED"

    assert data["incidents"][0]["evidence"] == {
        "container_status": "exited"
    }


def test_filter_incidents_by_status(client):
    response = client.get(
        "/incidents",
        params={"status": "RESOLVED"},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_invalid_incident_status_returns_400(client):
    response = client.get(
        "/incidents",
        params={"status": "INVALID"},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "status must be OPEN or RESOLVED"
    )


def test_get_single_incident_with_actions(client):
    response = client.get("/incidents/1")

    assert response.status_code == 200

    data = response.json()

    assert data["incident"]["id"] == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_type"] == "restart"
    assert data["actions"][0]["result"] == "SUCCESS"


def test_missing_incident_returns_404(client):
    response = client.get("/incidents/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"


def test_incident_timeline(client):
    response = client.get("/incidents/1/timeline")

    assert response.status_code == 200

    data = response.json()

    events = [
        item["event"]
        for item in data["timeline"]
    ]

    assert "INCIDENT_DETECTED" in events
    assert "AI_ANALYSIS_COMPLETED" in events
    assert "restart" in events
    assert "INCIDENT_RESOLVED" in events


def test_incident_statistics(client):
    response = client.get("/statistics")

    assert response.status_code == 200

    data = response.json()

    assert data["total_incidents"] == 1
    assert data["open_incidents"] == 0
    assert data["resolved_incidents"] == 1
    assert data["resolution_rate_percent"] == 100.0


def test_list_experiments(client):
    response = client.get("/experiments")

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2
    assert len(data["experiments"]) == 2


def test_filter_experiments_by_scenario(client):
    response = client.get(
        "/experiments",
        params={"scenario_name": "STOP_API"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert (
        data["experiments"][0]["scenario_name"]
        == "STOP_API"
    )


def test_filter_experiments_by_result(client):
    response = client.get(
        "/experiments",
        params={"result": "SUCCESS"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert data["experiments"][0]["result"] == "SUCCESS"


def test_invalid_experiment_result_returns_400(client):
    response = client.get(
        "/experiments",
        params={"result": "UNKNOWN"},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "result must be SUCCESS or FAILED"
    )


def test_experiment_statistics(client):
    response = client.get("/experiments/statistics")

    assert response.status_code == 200

    data = response.json()

    assert data["total_experiments"] == 2
    assert data["successful_experiments"] == 1
    assert data["failed_experiments"] == 1
    assert data["success_rate_percent"] == 50.0
    assert data["average_recovery_seconds"] == 20.0
    assert data["fastest_recovery_seconds"] == 20.0
    assert data["slowest_recovery_seconds"] == 20.0