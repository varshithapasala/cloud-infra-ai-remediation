from dataclasses import dataclass
from datetime import datetime, timezone

import docker

from remediation_agent.models import Incident


@dataclass
class RemediationResult:
    action: str
    success: bool
    details: str


class RemediationExecutor:
    ALLOWED_ACTIONS = {"restart"}
    MAX_ATTEMPTS = 2
    COOLDOWN_SECONDS = 120

    def __init__(self) -> None:
        self.client = docker.from_env()
        self.last_action_time: dict[str, datetime] = {}
        self.action_counts: dict[str, int] = {}

    def execute(
        self,
        incident: Incident,
    ) -> RemediationResult:
        action = incident.recommended_action

        # Only explicitly allowed automatic actions can execute.
        if action not in self.ALLOWED_ACTIONS:
            return RemediationResult(
                action=action,
                success=False,
                details="Action requires manual review",
            )

        allowed, reason = self._can_execute(
            incident.resource_name
        )

        if not allowed:
            return RemediationResult(
                action=action,
                success=False,
                details=reason,
            )

        try:
            container = self.client.containers.get(
                incident.resource_name
            )

            # Read Docker labels from the selected container.
            labels = container.labels or {}

            # Block containers that are not approved.
            if labels.get("remediation.enabled") != "true":
                return RemediationResult(
                    action=action,
                    success=False,
                    details=(
                        "Resource is not approved "
                        "for automatic remediation"
                    ),
                )

            # Actually restart the approved container.
            container.restart(timeout=10)

            self.last_action_time[
                incident.resource_name
            ] = datetime.now(timezone.utc)

            self.action_counts[
                incident.resource_name
            ] = (
                self.action_counts.get(
                    incident.resource_name,
                    0,
                )
                + 1
            )

            return RemediationResult(
                action=action,
                success=True,
                details=f"Restarted {incident.resource_name}",
            )

        except docker.errors.NotFound:
            return RemediationResult(
                action=action,
                success=False,
                details=(
                    f"Container {incident.resource_name} "
                    "was not found"
                ),
            )

        except docker.errors.DockerException as exc:
            return RemediationResult(
                action=action,
                success=False,
                details=f"Docker error: {exc}",
            )

    def _can_execute(
        self,
        resource_name: str,
    ) -> tuple[bool, str]:
        attempts = self.action_counts.get(
            resource_name,
            0,
        )

        if attempts >= self.MAX_ATTEMPTS:
            return (
                False,
                "Maximum automatic attempts reached",
            )

        last_action = self.last_action_time.get(
            resource_name
        )

        if last_action is not None:
            elapsed_seconds = (
                datetime.now(timezone.utc)
                - last_action
            ).total_seconds()

            if elapsed_seconds < self.COOLDOWN_SECONDS:
                return (
                    False,
                    "Resource is in cooldown",
                )

        return True, "Allowed"