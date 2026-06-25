import time
from datetime import datetime, timezone

import docker
import requests

from failure_scenarios.experiment_store import (
    initialize_experiments_table,
    save_experiment,
)


CONTAINER_NAME = "cloud-postgres"
READINESS_URL = "http://localhost:8000/ready"

CHECK_INTERVAL_SECONDS = 2
MAX_WAIT_SECONDS = 120


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_api_ready() -> bool:
    try:
        response = requests.get(
            READINESS_URL,
            timeout=3,
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def main() -> None:
    initialize_experiments_table()

    docker_client = docker.from_env()

    print("Checking application readiness...")

    if not is_api_ready():
        print(
            "Application is not ready before the experiment."
        )
        return

    print("Application is ready.")
    print("Starting PostgreSQL-stop experiment...")

    postgres = docker_client.containers.get(
        CONTAINER_NAME
    )

    started_at = utc_now()
    failure_started_at = time.monotonic()

    postgres.stop()

    print(
        f"Stopped container: {CONTAINER_NAME}"
    )

    dependency_failure_detected = False

    deadline = time.monotonic() + 30

    while time.monotonic() < deadline:
        if not is_api_ready():
            dependency_failure_detected = True
            break

        time.sleep(CHECK_INTERVAL_SECONDS)

    if dependency_failure_detected:
        print(
            "Database dependency failure detected "
            "through the readiness endpoint."
        )
    else:
        print(
            "Readiness endpoint did not report the "
            "database failure within 30 seconds."
        )

    print(
        "PostgreSQL requires manual recovery in this project."
    )

    postgres.start()

    print("PostgreSQL started manually.")

    recovered = False
    recovered_at = None

    recovery_deadline = (
        time.monotonic()
        + MAX_WAIT_SECONDS
    )

    while time.monotonic() < recovery_deadline:
        if is_api_ready():
            recovered = True
            recovered_at = utc_now()
            break

        elapsed = (
            time.monotonic()
            - failure_started_at
        )

        print(
            f"Waiting for application readiness... "
            f"{elapsed:.1f} seconds"
        )

        time.sleep(CHECK_INTERVAL_SECONDS)

    recovery_seconds = (
        time.monotonic()
        - failure_started_at
    )

    if dependency_failure_detected and recovered:
        result = "SUCCESS"
        details = (
            "Database failure detected and "
            "application recovered after manual restart"
        )
    else:
        result = "FAILED"
        details = (
            "Database failure detection or recovery failed"
        )

    experiment_id = save_experiment(
        scenario_name="STOP_POSTGRES",
        resource_name=CONTAINER_NAME,
        started_at=started_at,
        recovered_at=recovered_at,
        recovery_seconds=recovery_seconds,
        result=result,
        details=details,
    )

    print("")
    print(f"Experiment ID: {experiment_id}")
    print(f"Result: {result}")
    print(
        f"Total recovery time: "
        f"{recovery_seconds:.2f} seconds"
    )


if __name__ == "__main__":
    main()