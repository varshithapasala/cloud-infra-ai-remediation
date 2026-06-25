from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentType(str, Enum):
    CONTAINER_STOPPED = "CONTAINER_STOPPED"
    CONTAINER_UNHEALTHY = "CONTAINER_UNHEALTHY"
    HIGH_CPU = "HIGH_CPU"
    HIGH_MEMORY = "HIGH_MEMORY"
    WORKER_HEARTBEAT_MISSING = "WORKER_HEARTBEAT_MISSING"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


@dataclass
class ContainerSnapshot:
    name: str
    container_id: str
    status: str
    health: Optional[str]
    cpu_percent: float
    memory_percent: float
    restart_count: int
    logs: str


@dataclass
class Incident:
    resource_name: str
    incident_type: IncidentType
    severity: Severity
    description: str
    recommended_action: str
    evidence: dict