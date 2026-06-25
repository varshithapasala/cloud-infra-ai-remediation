from prometheus_client import Counter, Gauge

INCIDENTS_DETECTED = Counter(
    "remediation_incidents_detected_total",
    "Number of detected incidents",
    [
        "resource",
        "incident_type",
        "severity",
    ],
)

ACTIONS_EXECUTED = Counter(
    "remediation_actions_executed_total",
    "Number of remediation actions",
    [
        "resource",
        "action",
        "result",
    ],
)

OPEN_INCIDENTS = Gauge(
    "remediation_open_incidents",
    "Number of unresolved incidents",
)

RECOVERY_DURATION = Gauge(
    "remediation_last_recovery_duration_seconds",
    "Duration of latest recovery",
    [
        "resource",
    ],
)