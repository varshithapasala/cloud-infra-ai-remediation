import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/incidents.db")


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_experiments_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_name TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                recovered_at TEXT,
                recovery_seconds REAL,
                result TEXT NOT NULL,
                details TEXT
            )
            """
        )


def save_experiment(
    scenario_name: str,
    resource_name: str,
    started_at: str,
    recovered_at: str | None,
    recovery_seconds: float,
    result: str,
    details: str,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO experiments (
                scenario_name,
                resource_name,
                started_at,
                recovered_at,
                recovery_seconds,
                result,
                details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_name,
                resource_name,
                started_at,
                recovered_at,
                recovery_seconds,
                result,
                details,
            ),
        )

        return int(cursor.lastrowid)