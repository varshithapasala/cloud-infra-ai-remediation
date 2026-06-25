import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


DATABASE_PATH = Path("/app/data/incidents.db")


app = FastAPI(
    title="Infrastructure Incident API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise RuntimeError(
            f"Incident database not found at {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def parse_incident(row: sqlite3.Row) -> dict:
    incident = dict(row)

    evidence_json = incident.get("evidence_json")

    if evidence_json:
        try:
            incident["evidence"] = json.loads(
                evidence_json
            )
        except json.JSONDecodeError:
            incident["evidence"] = {}
    else:
        incident["evidence"] = {}

    incident.pop("evidence_json", None)

    return incident


@app.get("/health")
def health():
    database_available = DATABASE_PATH.exists()

    return {
        "status": (
            "healthy"
            if database_available
            else "degraded"
        ),
        "service": "incident-api",
        "database_available": database_available,
    }


@app.get("/incidents")
def list_incidents(
    status: str | None = Query(
        default=None,
        description="Filter using OPEN or RESOLVED",
    ),
    resource_name: str | None = Query(
        default=None,
        description="Filter by resource name",
    ),
    incident_type: str | None = Query(
        default=None,
        description="Filter by incident type",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
):
    conditions: list[str] = []
    parameters: list = []

    if status:
        normalized_status = status.upper()

        if normalized_status not in {
            "OPEN",
            "RESOLVED",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "status must be OPEN or RESOLVED"
                ),
            )

        conditions.append("status = ?")
        parameters.append(normalized_status)

    if resource_name:
        conditions.append("resource_name = ?")
        parameters.append(resource_name)

    if incident_type:
        conditions.append("incident_type = ?")
        parameters.append(incident_type)

    query = """
        SELECT *
        FROM incidents
    """

    if conditions:
        query += " WHERE " + " AND ".join(
            conditions
        )

    query += " ORDER BY id DESC LIMIT ?"
    parameters.append(limit)

    try:
        with get_connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    return {
        "count": len(rows),
        "incidents": [
            parse_incident(row)
            for row in rows
        ],
    }


@app.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
):
    try:
        with get_connection() as connection:
            incident = connection.execute(
                """
                SELECT *
                FROM incidents
                WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()

            if incident is None:
                raise HTTPException(
                    status_code=404,
                    detail="Incident not found",
                )

            actions = connection.execute(
                """
                SELECT *
                FROM actions
                WHERE incident_id = ?
                ORDER BY id ASC
                """,
                (incident_id,),
            ).fetchall()

    except HTTPException:
        raise

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    return {
        "incident": parse_incident(
            incident
        ),
        "actions": [
            dict(action)
            for action in actions
        ],
    }


@app.get("/incidents/{incident_id}/timeline")
def get_incident_timeline(
    incident_id: int,
):
    try:
        with get_connection() as connection:
            incident = connection.execute(
                """
                SELECT *
                FROM incidents
                WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()

            if incident is None:
                raise HTTPException(
                    status_code=404,
                    detail="Incident not found",
                )

            actions = connection.execute(
                """
                SELECT *
                FROM actions
                WHERE incident_id = ?
                ORDER BY executed_at ASC, id ASC
                """,
                (incident_id,),
            ).fetchall()

    except HTTPException:
        raise

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    timeline = [
        {
            "event": "INCIDENT_DETECTED",
            "timestamp": incident["detected_at"],
            "result": None,
            "details": incident["description"],
        }
    ]

    if incident["ai_summary"]:
        timeline.append(
            {
                "event": "AI_ANALYSIS_COMPLETED",
                "timestamp": incident["detected_at"],
                "result": "SUCCESS",
                "details": incident["ai_summary"],
            }
        )

    for action in actions:
        timeline.append(
            {
                "event": action["action_type"],
                "timestamp": action["executed_at"],
                "result": action["result"],
                "details": action["details"],
            }
        )

    if incident["resolved_at"]:
        timeline.append(
            {
                "event": "INCIDENT_RESOLVED",
                "timestamp": incident["resolved_at"],
                "result": "SUCCESS",
                "details": (
                    "Resource recovery was verified"
                ),
            }
        )

    timeline.sort(
        key=lambda item: item["timestamp"] or ""
    )

    return {
        "incident_id": incident_id,
        "timeline": timeline,
    }


@app.get("/statistics")
def statistics():
    try:
        with get_connection() as connection:
            total_incidents = connection.execute(
                """
                SELECT COUNT(*)
                FROM incidents
                """
            ).fetchone()[0]

            open_incidents = connection.execute(
                """
                SELECT COUNT(*)
                FROM incidents
                WHERE status = 'OPEN'
                """
            ).fetchone()[0]

            resolved_incidents = connection.execute(
                """
                SELECT COUNT(*)
                FROM incidents
                WHERE status = 'RESOLVED'
                """
            ).fetchone()[0]

            successful_actions = connection.execute(
                """
                SELECT COUNT(*)
                FROM actions
                WHERE result = 'SUCCESS'
                  AND action_type !=
                      'recovery_verification'
                """
            ).fetchone()[0]

            failed_actions = connection.execute(
                """
                SELECT COUNT(*)
                FROM actions
                WHERE result = 'FAILED'
                """
            ).fetchone()[0]

            incidents_by_type = connection.execute(
                """
                SELECT
                    incident_type,
                    COUNT(*) AS count
                FROM incidents
                GROUP BY incident_type
                ORDER BY count DESC
                """
            ).fetchall()

            incidents_by_resource = (
                connection.execute(
                    """
                    SELECT
                        resource_name,
                        COUNT(*) AS count
                    FROM incidents
                    GROUP BY resource_name
                    ORDER BY count DESC
                    """
                ).fetchall()
            )

            incidents_by_severity = (
                connection.execute(
                    """
                    SELECT
                        severity,
                        COUNT(*) AS count
                    FROM incidents
                    GROUP BY severity
                    ORDER BY count DESC
                    """
                ).fetchall()
            )

            recent_incidents = connection.execute(
                """
                SELECT
                    id,
                    resource_name,
                    incident_type,
                    severity,
                    status,
                    detected_at,
                    resolved_at
                FROM incidents
                ORDER BY id DESC
                LIMIT 5
                """
            ).fetchall()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    resolution_rate = 0.0

    if total_incidents > 0:
        resolution_rate = round(
            resolved_incidents
            / total_incidents
            * 100,
            2,
        )

    return {
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "resolved_incidents": resolved_incidents,
        "resolution_rate_percent": resolution_rate,
        "successful_remediation_actions": (
            successful_actions
        ),
        "failed_actions": failed_actions,
        "incidents_by_type": [
            dict(row)
            for row in incidents_by_type
        ],
        "incidents_by_resource": [
            dict(row)
            for row in incidents_by_resource
        ],
        "incidents_by_severity": [
            dict(row)
            for row in incidents_by_severity
        ],
        "recent_incidents": [
            dict(row)
            for row in recent_incidents
        ],
    }

@app.get("/experiments")
def list_experiments(
    scenario_name: str | None = Query(
        default=None,
        description="Filter by scenario name",
    ),
    result: str | None = Query(
        default=None,
        description="Filter using SUCCESS or FAILED",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
):
    conditions: list[str] = []
    parameters: list = []

    if scenario_name:
        conditions.append("scenario_name = ?")
        parameters.append(scenario_name.upper())

    if result:
        normalized_result = result.upper()

        if normalized_result not in {
            "SUCCESS",
            "FAILED",
        }:
            raise HTTPException(
                status_code=400,
                detail="result must be SUCCESS or FAILED",
            )

        conditions.append("result = ?")
        parameters.append(normalized_result)

    query = """
        SELECT
            id,
            scenario_name,
            resource_name,
            started_at,
            recovered_at,
            recovery_seconds,
            result,
            details
        FROM experiments
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ?"
    parameters.append(limit)

    try:
        with get_connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return {
                "count": 0,
                "experiments": [],
            }

        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    return {
        "count": len(rows),
        "experiments": [
            dict(row)
            for row in rows
        ],
    }


@app.get("/experiments/statistics")
def experiment_statistics():
    try:
        with get_connection() as connection:
            total_experiments = connection.execute(
                """
                SELECT COUNT(*)
                FROM experiments
                """
            ).fetchone()[0]

            successful_experiments = connection.execute(
                """
                SELECT COUNT(*)
                FROM experiments
                WHERE result = 'SUCCESS'
                """
            ).fetchone()[0]

            failed_experiments = connection.execute(
                """
                SELECT COUNT(*)
                FROM experiments
                WHERE result = 'FAILED'
                """
            ).fetchone()[0]

            average_recovery_seconds = connection.execute(
                """
                SELECT AVG(recovery_seconds)
                FROM experiments
                WHERE result = 'SUCCESS'
                """
            ).fetchone()[0]

            fastest_recovery_seconds = connection.execute(
                """
                SELECT MIN(recovery_seconds)
                FROM experiments
                WHERE result = 'SUCCESS'
                """
            ).fetchone()[0]

            slowest_recovery_seconds = connection.execute(
                """
                SELECT MAX(recovery_seconds)
                FROM experiments
                WHERE result = 'SUCCESS'
                """
            ).fetchone()[0]

            scenario_rows = connection.execute(
                """
                SELECT
                    scenario_name,
                    COUNT(*) AS total_runs,
                    SUM(
                        CASE
                            WHEN result = 'SUCCESS'
                            THEN 1
                            ELSE 0
                        END
                    ) AS successful_runs,
                    SUM(
                        CASE
                            WHEN result = 'FAILED'
                            THEN 1
                            ELSE 0
                        END
                    ) AS failed_runs,
                    AVG(
                        CASE
                            WHEN result = 'SUCCESS'
                            THEN recovery_seconds
                        END
                    ) AS average_recovery_seconds
                FROM experiments
                GROUP BY scenario_name
                ORDER BY scenario_name
                """
            ).fetchall()

    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return {
                "total_experiments": 0,
                "successful_experiments": 0,
                "failed_experiments": 0,
                "success_rate_percent": 0.0,
                "average_recovery_seconds": None,
                "fastest_recovery_seconds": None,
                "slowest_recovery_seconds": None,
                "by_scenario": [],
            }

        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {exc}",
        ) from exc

    success_rate = 0.0

    if total_experiments > 0:
        success_rate = round(
            successful_experiments
            / total_experiments
            * 100,
            2,
        )

    return {
        "total_experiments": total_experiments,
        "successful_experiments": successful_experiments,
        "failed_experiments": failed_experiments,
        "success_rate_percent": success_rate,
        "average_recovery_seconds": (
            round(average_recovery_seconds, 2)
            if average_recovery_seconds is not None
            else None
        ),
        "fastest_recovery_seconds": (
            round(fastest_recovery_seconds, 2)
            if fastest_recovery_seconds is not None
            else None
        ),
        "slowest_recovery_seconds": (
            round(slowest_recovery_seconds, 2)
            if slowest_recovery_seconds is not None
            else None
        ),
        "by_scenario": [
            {
                "scenario_name": row["scenario_name"],
                "total_runs": row["total_runs"],
                "successful_runs": row["successful_runs"],
                "failed_runs": row["failed_runs"],
                "average_recovery_seconds": (
                    round(
                        row["average_recovery_seconds"],
                        2,
                    )
                    if row["average_recovery_seconds"]
                    is not None
                    else None
                ),
            }
            for row in scenario_rows
        ],
    }