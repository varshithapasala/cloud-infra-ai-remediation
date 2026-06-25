import time
from datetime import datetime, timezone

import docker
import requests

from failure_scenarios.experiment_store import (
    initialize_experiments_table,
    save_experiment,
)


CONTAINER_NAME = "cloud-redis"
READINESS_URL = "http://localhost:8000/ready"

CHECK_INTERVAL_SECONDS = 2
DETECTION_TIMEOUT_SECONDS = 30
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


def is_container_running(
    docker_client: docker.DockerClient,
) -> bool:
    try:
        container = docker_client.containers.get(
            CONTAINER_NAME
        )
        container.reload()

        return container.status == "running"

    except docker.errors.NotFound:
        return False

    except docker.errors.DockerException:
        return False


def main() -> None:
    initialize_experiments_table()

    docker_client = docker.from_env()

    print("Checking Redis and application readiness...")

    if not is_container_running(docker_client):
        print(
            f"{CONTAINER_NAME} is not running before "
            "the experiment."
        )
        return

    if not is_api_ready():
        print(
            "Application is not ready before the experiment."
        )
        return

    print("Redis and application are ready.")
    print("Starting Redis-stop experiment...")

    redis_container = docker_client.containers.get(
        CONTAINER_NAME
    )

    started_at = utc_now()
    failure_started_at = time.monotonic()

    redis_container.stop()

    print(f"Stopped container: {CONTAINER_NAME}")

    dependency_failure_detected = False
    detection_seconds = None

    detection_deadline = (
        time.monotonic()
        + DETECTION_TIMEOUT_SECONDS
    )

    while time.monotonic() < detection_deadline:
        if not is_api_ready():
            dependency_failure_detected = True
            detection_seconds = (
                time.monotonic()
                - failure_started_at
            )
            break

        elapsed = (
            time.monotonic()
            - failure_started_at
        )

        print(
            f"Waiting for Redis failure detection... "
            f"{elapsed:.1f} seconds"
        )

        time.sleep(CHECK_INTERVAL_SECONDS)

    if dependency_failure_detected:
        print(
            "Redis dependency failure was detected "
            "through the readiness endpoint."
        )
        print(
            f"Detection time: "
            f"{detection_seconds:.2f} seconds"
        )
    else:
        print(
            "The readiness endpoint did not detect "
            "the Redis failure within "
            f"{DETECTION_TIMEOUT_SECONDS} seconds."
        )

    print(
        "Redis requires manual recovery in this experiment."
    )

    redis_container.start()

    print("Redis container started manually.")

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
            "Redis failure was detected and the "
            "application recovered after manual restart. "
            f"Detection time: {detection_seconds:.2f} seconds."
        )
    else:
        result = "FAILED"
        details = (
            "Redis failure detection or recovery failed."
        )

    experiment_id = save_experiment(
        scenario_name="STOP_REDIS",
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

    if detection_seconds is not None:
        print(
            f"Detection time: "
            f"{detection_seconds:.2f} seconds"
        )

    print(
        f"Total recovery time: "
        f"{recovery_seconds:.2f} seconds"
    )


if __name__ == "__main__":
    main()