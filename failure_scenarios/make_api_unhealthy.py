import time
from datetime import datetime, timezone

import requests

from failure_scenarios.experiment_store import (
    initialize_experiments_table,
    save_experiment,
)


HEALTH_URL = "http://localhost:8000/health"
FAILURE_URL = "http://localhost:8000/simulate/unhealthy"

CHECK_INTERVAL_SECONDS = 2
MAX_WAIT_SECONDS = 120


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_api_healthy() -> bool:
    try:
        response = requests.get(
            HEALTH_URL,
            timeout=3,
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def main() -> None:
    initialize_experiments_table()

    print("Checking API before experiment...")

    if not is_api_healthy():
        print("The API is not healthy before the experiment.")
        return

    print("API is healthy.")
    print("Starting unhealthy-API experiment...")

    started_at = utc_now()
    failure_started_at = time.monotonic()

    response = requests.post(
        FAILURE_URL,
        timeout=5,
    )

    response.raise_for_status()

    print("API was changed to unhealthy state.")

    recovered = False
    recovered_at = None

    deadline = time.monotonic() + MAX_WAIT_SECONDS

    while time.monotonic() < deadline:
        if is_api_healthy():
            recovered = True
            recovered_at = utc_now()
            break

        elapsed = time.monotonic() - failure_started_at

        print(
            f"Waiting for API recovery... "
            f"{elapsed:.1f} seconds"
        )

        time.sleep(CHECK_INTERVAL_SECONDS)

    recovery_seconds = (
        time.monotonic() - failure_started_at
    )

    result = "SUCCESS" if recovered else "FAILED"

    details = (
        "Unhealthy API recovered successfully"
        if recovered
        else (
            "API did not recover within "
            f"{MAX_WAIT_SECONDS} seconds"
        )
    )

    experiment_id = save_experiment(
        scenario_name="API_UNHEALTHY",
        resource_name="order-api",
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