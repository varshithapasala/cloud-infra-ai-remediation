import logging
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server

from remediation_agent.ai_analyst import GeminiIncidentAnalyst
from remediation_agent.collector import DockerCollector
from remediation_agent.incident_store import (
    create_incident,
    get_open_incident,
    initialize_database,
    record_action,
    resolve_incident,
    resolve_open_incidents_for_resource,
    save_ai_analysis,
)
from remediation_agent.metrics import (
    ACTIONS_EXECUTED,
    INCIDENTS_DETECTED,
)
from remediation_agent.remediation import RemediationExecutor
from remediation_agent.rule_engine import RuleEngine
from remediation_agent.verifier import RecoveryVerifier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

CHECK_INTERVAL_SECONDS = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run() -> None:
    initialize_database()

    # Exposes remediation-agent metrics to Prometheus.
    start_http_server(9105)

    collector = DockerCollector()
    rule_engine = RuleEngine()
    executor = RemediationExecutor()
    verifier = RecoveryVerifier()

    try:
        ai_analyst = GeminiIncidentAnalyst()
    except Exception as exc:
        ai_analyst = None

        logging.warning(
            "Gemini incident analyst could not start: %s",
            exc,
        )

    logging.info("AI remediation agent started")

    while True:
        try:
            snapshots = collector.get_managed_containers()

            for snapshot in snapshots:
                resource_is_healthy = (
                    snapshot.status == "running"
                    and snapshot.health in {None, "healthy"}
                )

                if resource_is_healthy:
                    resolved_count = resolve_open_incidents_for_resource(
                        resource_name=snapshot.name,
                        resolved_at=utc_now(),
                    )

                    if resolved_count > 0:
                        logging.info(
                            "Resolved %s stale open incident(s) "
                            "for healthy resource=%s",
                            resolved_count,
                            snapshot.name,
                        )

                incidents = rule_engine.evaluate(snapshot)
                for incident in incidents:
                    incident_type = incident.incident_type.value
                    severity = incident.severity.value
                    resource_name = incident.resource_name

                    # Do not create another record when the same
                    # incident is already open.
                    existing_incident = get_open_incident(
                        resource_name=resource_name,
                        incident_type=incident_type,
                    )

                    if existing_incident:
                        logging.info(
                            "Open incident already exists: "
                            "resource=%s type=%s incident_id=%s",
                            resource_name,
                            incident_type,
                            existing_incident["id"],
                        )
                        continue

                    INCIDENTS_DETECTED.labels(
                        resource=resource_name,
                        incident_type=incident_type,
                        severity=severity,
                    ).inc()

                    incident_id = create_incident(
                        resource_name=resource_name,
                        incident_type=incident_type,
                        severity=severity,
                        description=incident.description,
                        evidence=incident.evidence,
                        detected_at=utc_now(),
                    )

                    logging.warning(
                        "Incident detected: "
                        "id=%s resource=%s type=%s description=%s",
                        incident_id,
                        resource_name,
                        incident_type,
                        incident.description,
                    )

                    analysis_input = {
                        "incident_id": incident_id,
                        "resource": resource_name,
                        "incident_type": incident_type,
                        "severity": severity,
                        "description": incident.description,
                        "recommended_action": (
                            incident.recommended_action
                        ),
                        "evidence": incident.evidence,
                    }

                    # AI analysis is optional.
                    # Detection and remediation continue even if Gemini fails.
                    if ai_analyst is not None:
                        try:
                            ai_analysis = ai_analyst.analyze(
                                analysis_input
                            )

                            save_ai_analysis(
                                incident_id=incident_id,
                                summary=ai_analysis.summary,
                                root_cause=(
                                    ai_analysis.probable_root_cause
                                ),
                                recommendation=(
                                    ai_analysis.recommendation
                                ),
                            )

                            logging.info(
                                "Gemini analysis saved for incident %s",
                                incident_id,
                            )

                        except Exception as exc:
                            logging.warning(
                                "Gemini analysis failed for "
                                "incident %s: %s",
                                incident_id,
                                exc,
                            )

                    remediation_started_at = time.monotonic()

                    result = executor.execute(incident)

                    action_result = (
                        "SUCCESS"
                        if result.success
                        else "FAILED"
                    )

                    record_action(
                        incident_id=incident_id,
                        action_type=result.action,
                        result=action_result,
                        details=result.details,
                        executed_at=utc_now(),
                    )

                    ACTIONS_EXECUTED.labels(
                        resource=resource_name,
                        action=result.action,
                        result=action_result.lower(),
                    ).inc()

                    logging.info(
                        "Remediation result: "
                        "incident_id=%s action=%s result=%s details=%s",
                        incident_id,
                        result.action,
                        action_result,
                        result.details,
                    )

                    # Only verify recovery if an automatic
                    # remediation action actually succeeded.
                    if not result.success:
                        continue

                    recovered, verification_details = verifier.verify(
                        resource_name
                    )

                    recovery_duration = (
                        time.monotonic()
                        - remediation_started_at
                    )

                    record_action(
                        incident_id=incident_id,
                        action_type="recovery_verification",
                        result=(
                            "SUCCESS"
                            if recovered
                            else "FAILED"
                        ),
                        details=verification_details,
                        executed_at=utc_now(),
                    )

                    if recovered:
                        resolve_incident(
                            incident_id=incident_id,
                            resolved_at=utc_now(),
                        )

                        logging.info(
                            "Incident resolved: "
                            "incident_id=%s resource=%s "
                            "recovery_time=%.2f seconds",
                            incident_id,
                            resource_name,
                            recovery_duration,
                        )

                    else:
                        logging.error(
                            "Recovery verification failed: "
                            "incident_id=%s resource=%s details=%s",
                            incident_id,
                            resource_name,
                            verification_details,
                        )

                    logging.info(
                        "Recovery result for %s: %s - %s",
                        resource_name,
                        recovered,
                        verification_details,
                    )

        except Exception:
            logging.exception(
                "Unexpected error in remediation-agent loop"
            )

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()