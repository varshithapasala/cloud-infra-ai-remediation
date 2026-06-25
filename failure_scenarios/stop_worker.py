import time
from datetime import datetime, timezone

import docker

from failure_scenarios.experiment_store import (
    initialize_experiments_table,
    save_experiment,
)


CONTAINER_NAME = "order-worker"

CHECK_INTERVAL_SECONDS = 2
MAX_WAIT_SECONDS = 120


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_worker_running(
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

    print("Checking worker before experiment...")

    if not is_worker_running(docker_client):
        print(
            "The worker is not running before the experiment."
        )
        print(
            "Start order-worker before running this test."
        )
        return

    print("Worker is running.")
    print("Starting worker-stop experiment...")

    container = docker_client.containers.get(
        CONTAINER_NAME
    )

    failure_started_at = time.monotonic()
    started_at = utc_now()

    container.stop()

    print(
        f"Stopped container: {CONTAINER_NAME}"
    )

    recovered = False
    recovered_at = None

    deadline = (
        time.monotonic()
        + MAX_WAIT_SECONDS
    )

    while time.monotonic() < deadline:
        if is_worker_running(docker_client):
            recovered = True
            recovered_at = utc_now()
            break

        elapsed = (
            time.monotonic()
            - failure_started_at
        )

        print(
            f"Waiting for worker recovery... "
            f"{elapsed:.1f} seconds"
        )

        time.sleep(CHECK_INTERVAL_SECONDS)

    recovery_seconds = (
        time.monotonic()
        - failure_started_at
    )

    result = (
        "SUCCESS"
        if recovered
        else "FAILED"
    )

    details = (
        "Worker restarted successfully"
        if recovered
        else (
            "Worker did not recover within "
            f"{MAX_WAIT_SECONDS} seconds"
        )
    )

    experiment_id = save_experiment(
        scenario_name="STOP_WORKER",
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
        f"Recovery time: "
        f"{recovery_seconds:.2f} seconds"
    )


if __name__ == "__main__":
    main()