from unittest.mock import MagicMock

from remediation_agent.models import (
    Incident,
    IncidentType,
    Severity,
)
from remediation_agent.remediation import RemediationExecutor


def build_incident(action: str = "restart") -> Incident:
    return Incident(
        resource_name="order-api",
        incident_type=IncidentType.CONTAINER_STOPPED,
        severity=Severity.CRITICAL,
        description="Order API stopped",
        recommended_action=action,
        evidence={"status": "exited"},
    )


def build_executor_with_mock_container(
    remediation_enabled: str,
):
    executor = RemediationExecutor()

    mock_container = MagicMock()
    mock_container.labels = {
        "remediation.enabled": remediation_enabled
    }

    mock_containers_manager = MagicMock()
    mock_containers_manager.get.return_value = (
        mock_container
    )

    mock_client = MagicMock()
    mock_client.containers = mock_containers_manager

    executor.client = mock_client

    return (
        executor,
        mock_container,
        mock_containers_manager,
    )


def test_manual_review_action_is_not_executed():
    executor = RemediationExecutor()

    incident = build_incident(
        action="manual_review"
    )

    result = executor.execute(incident)

    assert result.success is False
    assert result.action == "manual_review"
    assert result.details == "Action requires manual review"


def test_restart_is_blocked_for_unapproved_container():
    (
        executor,
        mock_container,
        mock_containers_manager,
    ) = build_executor_with_mock_container("false")

    result = executor.execute(
        build_incident()
    )

    assert result.success is False
    assert result.action == "restart"
    assert "not approved" in result.details.lower()

    mock_containers_manager.get.assert_called_once_with(
        "order-api"
    )

    mock_container.restart.assert_not_called()


def test_approved_container_is_restarted():
    (
        executor,
        mock_container,
        mock_containers_manager,
    ) = build_executor_with_mock_container("true")

    result = executor.execute(
        build_incident()
    )

    assert result.success is True
    assert result.action == "restart"
    assert result.details == "Restarted order-api"

    mock_containers_manager.get.assert_called_once_with(
        "order-api"
    )

    mock_container.restart.assert_called_once_with(
        timeout=10
    )


def test_second_action_is_blocked_by_cooldown():
    (
        executor,
        mock_container,
        mock_containers_manager,
    ) = build_executor_with_mock_container("true")

    incident = build_incident()

    first_result = executor.execute(incident)
    second_result = executor.execute(incident)

    assert first_result.success is True
    assert second_result.success is False
    assert "cooldown" in second_result.details.lower()

    # Docker lookup and restart occur only for the first action.
    mock_containers_manager.get.assert_called_once_with(
        "order-api"
    )

    mock_container.restart.assert_called_once_with(
        timeout=10
    )