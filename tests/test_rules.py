from remediation_agent.models import (
    ContainerSnapshot,
    IncidentType,
)
from remediation_agent.rule_engine import RuleEngine


def test_stopped_container_detected():
    snapshot = ContainerSnapshot(
        name="order-api",
        container_id="abc123",
        status="exited",
        health=None,
        cpu_percent=0.0,
        memory_percent=0.0,
        restart_count=0,
        logs="Container stopped",
    )

    incidents = RuleEngine().evaluate(snapshot)

    assert len(incidents) == 1
    assert (
        incidents[0].incident_type
        == IncidentType.CONTAINER_STOPPED
    )


def test_healthy_container_has_no_incidents():
    snapshot = ContainerSnapshot(
        name="order-api",
        container_id="abc123",
        status="running",
        health="healthy",
        cpu_percent=10.0,
        memory_percent=20.0,
        restart_count=0,
        logs="Application running",
    )

    incidents = RuleEngine().evaluate(snapshot)

    assert incidents == []


def test_high_cpu_requires_manual_review():
    snapshot = ContainerSnapshot(
        name="order-api",
        container_id="abc123",
        status="running",
        health="healthy",
        cpu_percent=92.0,
        memory_percent=30.0,
        restart_count=0,
        logs="CPU usage is high",
    )

    incidents = RuleEngine().evaluate(snapshot)

    assert len(incidents) == 1
    assert incidents[0].incident_type == IncidentType.HIGH_CPU
    assert incidents[0].recommended_action == "manual_review"