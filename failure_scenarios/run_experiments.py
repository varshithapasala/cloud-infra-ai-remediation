import subprocess
import sys
import time


SCENARIOS = [
    {
        "name": "STOP_API",
        "module": "failure_scenarios.stop_api",
        "wait_after_seconds": 10,
    },
    {
        "name": "STOP_WORKER",
        "module": "failure_scenarios.stop_worker",
        "wait_after_seconds": 10,
    },
    {
        "name": "API_UNHEALTHY",
        "module": "failure_scenarios.make_api_unhealthy",
        "wait_after_seconds": 10,
    },
    {
        "name": "STOP_POSTGRES",
        "module": "failure_scenarios.stop_postgres",
        "wait_after_seconds": 10,
    },
    {
        "name": "STOP_REDIS",
        "module": "failure_scenarios.stop_redis",
        "wait_after_seconds": 10,
    },
]


def run_scenario(
    name: str,
    module: str,
) -> bool:
    print("")
    print("=" * 70)
    print(f"Running scenario: {name}")
    print("=" * 70)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
        ],
        check=False,
    )

    if result.returncode == 0:
        print(f"{name} script completed.")
        return True

    print(
        f"{name} script failed with "
        f"exit code {result.returncode}."
    )
    return False


def main() -> None:
    print("Starting infrastructure failure experiments...")

    completed = 0
    failed = 0

    for scenario in SCENARIOS:
        success = run_scenario(
            name=scenario["name"],
            module=scenario["module"],
        )

        if success:
            completed += 1
        else:
            failed += 1

        wait_seconds = scenario["wait_after_seconds"]

        print(
            f"Waiting {wait_seconds} seconds before "
            "the next experiment..."
        )

        time.sleep(wait_seconds)

    print("")
    print("=" * 70)
    print("Experiment run completed")
    print("=" * 70)
    print(f"Scripts completed: {completed}")
    print(f"Scripts failed: {failed}")

    print("")
    print(
        "Run the following command to view stored results:"
    )
    print(
        'python -c "import sqlite3; '
        "db=sqlite3.connect('data/incidents.db'); "
        "print(db.execute("
        "'SELECT id, scenario_name, resource_name, "
        "recovery_seconds, result FROM experiments "
        "ORDER BY id DESC'"
        ").fetchall()); db.close()\""
    )


if __name__ == "__main__":
    main()