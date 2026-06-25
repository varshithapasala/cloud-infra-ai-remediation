from remediation_agent.models import (
    ContainerSnapshot,
    Incident,
    IncidentType,
    Severity,
)


class RuleEngine:
    CPU_THRESHOLD = 85.0
    MEMORY_THRESHOLD = 85.0

    def evaluate(
        self,
        snapshot: ContainerSnapshot,
    ) -> list[Incident]:
        incidents: list[Incident] = []

        if snapshot.status in {
            "exited",
            "dead",
        }:
            incidents.append(
                Incident(
                    resource_name=snapshot.name,
                    incident_type=(
                        IncidentType.CONTAINER_STOPPED
                    ),
                    severity=Severity.CRITICAL,
                    description=(
                        f"{snapshot.name} is "
                        f"{snapshot.status}"
                    ),
                    recommended_action="restart",
                    evidence={
                        "status": snapshot.status,
                        "logs": snapshot.logs,
                    },
                )
            )

        if snapshot.health == "unhealthy":
            incidents.append(
                Incident(
                    resource_name=snapshot.name,
                    incident_type=(
                        IncidentType.CONTAINER_UNHEALTHY
                    ),
                    severity=Severity.CRITICAL,
                    description=(
                        f"{snapshot.name} failed "
                        "its health checks"
                    ),
                    recommended_action="restart",
                    evidence={
                        "health": snapshot.health,
                        "logs": snapshot.logs,
                    },
                )
            )

        if (
            snapshot.cpu_percent
            >= self.CPU_THRESHOLD
        ):
            incidents.append(
                Incident(
                    resource_name=snapshot.name,
                    incident_type=(
                        IncidentType.HIGH_CPU
                    ),
                    severity=Severity.WARNING,
                    description=(
                        f"CPU usage reached "
                        f"{snapshot.cpu_percent:.2f}%"
                    ),
                    recommended_action=(
                        "manual_review"
                    ),
                    evidence={
                        "cpu_percent": (
                            snapshot.cpu_percent
                        ),
                        "logs": snapshot.logs,
                    },
                )
            )

        if (
            snapshot.memory_percent
            >= self.MEMORY_THRESHOLD
        ):
            incidents.append(
                Incident(
                    resource_name=snapshot.name,
                    incident_type=(
                        IncidentType.HIGH_MEMORY
                    ),
                    severity=Severity.WARNING,
                    description=(
                        f"Memory usage reached "
                        f"{snapshot.memory_percent:.2f}%"
                    ),
                    recommended_action=(
                        "manual_review"
                    ),
                    evidence={
                        "memory_percent": (
                            snapshot.memory_percent
                        ),
                        "logs": snapshot.logs,
                    },
                )
            )

        return incidents