import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(
    "/app/data/incidents.db"
)


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                ai_summary TEXT,
                ai_root_cause TEXT,
                ai_recommendation TEXT
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                result TEXT NOT NULL,
                details TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
            );
            """
        )


def create_incident(
    resource_name: str,
    incident_type: str,
    severity: str,
    description: str,
    evidence: dict,
    detected_at: str,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                resource_name,
                incident_type,
                severity,
                description,
                evidence_json,
                detected_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resource_name,
                incident_type,
                severity,
                description,
                json.dumps(evidence),
                detected_at,
            ),
        )

        return int(cursor.lastrowid)


def save_ai_analysis(
    incident_id: int,
    summary: str,
    root_cause: str,
    recommendation: str,
):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE incidents
            SET ai_summary = ?,
                ai_root_cause = ?,
                ai_recommendation = ?
            WHERE id = ?
            """,
            (
                summary,
                root_cause,
                recommendation,
                incident_id,
            ),
        )

def get_open_incident(
    resource_name: str,
    incident_type: str,
):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE resource_name = ?
              AND incident_type = ?
              AND status = 'OPEN'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                resource_name,
                incident_type,
            ),
        ).fetchone()

    return dict(row) if row else None


def record_action(
    incident_id: int,
    action_type: str,
    result: str,
    details: str,
    executed_at: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO actions (
                incident_id,
                action_type,
                result,
                details,
                executed_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                action_type,
                result,
                details,
                executed_at,
            ),
        )


def resolve_incident(
    incident_id: int,
    resolved_at: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE incidents
            SET status = 'RESOLVED',
                resolved_at = ?
            WHERE id = ?
            """,
            (
                resolved_at,
                incident_id,
            ),
        )     

def resolve_open_incidents_for_resource(
    resource_name: str,
    resolved_at: str,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET status = 'RESOLVED',
                resolved_at = ?
            WHERE resource_name = ?
              AND status = 'OPEN'
            """,
            (
                resolved_at,
                resource_name,
            ),
        )

        return cursor.rowcount   