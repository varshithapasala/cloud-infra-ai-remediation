const API_BASE_URL = "http://localhost:8080";


function setText(elementId, value) {
    const element = document.getElementById(elementId);

    if (element) {
        element.textContent = value;
    }
}


function formatSeconds(value) {
    if (value === null || value === undefined) {
        return "--";
    }

    return `${Number(value).toFixed(2)} s`;
}


function formatDate(value) {
    if (!value) {
        return "--";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString();
}


function createStatusBadge(value) {
    const normalizedValue = String(value).toUpperCase();

    let className = "badge";

    if (
        normalizedValue === "SUCCESS" ||
        normalizedValue === "RESOLVED"
    ) {
        className += " badge-success";
    } else if (
        normalizedValue === "FAILED" ||
        normalizedValue === "OPEN"
    ) {
        className += " badge-failed";
    }

    return `
        <span class="${className}">
            ${normalizedValue}
        </span>
    `;
}


async function requestJson(path) {
    const response = await fetch(
        `${API_BASE_URL}${path}`
    );

    if (!response.ok) {
        throw new Error(
            `Request failed: ${response.status} ${path}`
        );
    }

    return response.json();
}


async function loadIncidentStatistics() {
    const data = await requestJson("/statistics");

    setText(
        "total-incidents",
        data.total_incidents ?? 0
    );

    setText(
        "open-incidents",
        data.open_incidents ?? 0
    );

    setText(
        "resolved-incidents",
        data.resolved_incidents ?? 0
    );

    setText(
        "resolution-rate",
        `${data.resolution_rate_percent ?? 0}%`
    );
}


async function loadExperimentStatistics() {
    const data = await requestJson(
        "/experiments/statistics"
    );

    setText(
        "total-experiments",
        data.total_experiments ?? 0
    );

    setText(
        "successful-experiments",
        data.successful_experiments ?? 0
    );

    setText(
        "failed-experiments",
        data.failed_experiments ?? 0
    );

    setText(
        "experiment-success-rate",
        `${data.success_rate_percent ?? 0}%`
    );

    setText(
        "average-recovery-time",
        formatSeconds(data.average_recovery_seconds)
    );

    setText(
        "fastest-recovery-time",
        formatSeconds(data.fastest_recovery_seconds)
    );

    setText(
        "slowest-recovery-time",
        formatSeconds(data.slowest_recovery_seconds)
    );

    renderScenarioStatistics(
        data.by_scenario ?? []
    );
}


function renderScenarioStatistics(scenarios) {
    const tableBody = document.getElementById(
        "scenario-statistics-body"
    );

    if (!scenarios.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    No experiment statistics available.
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = scenarios
        .map(
            (scenario) => `
                <tr>
                    <td>
                        ${scenario.scenario_name}
                    </td>

                    <td>
                        ${scenario.total_runs}
                    </td>

                    <td>
                        ${scenario.successful_runs}
                    </td>

                    <td>
                        ${scenario.failed_runs}
                    </td>

                    <td>
                        ${formatSeconds(
                            scenario.average_recovery_seconds
                        )}
                    </td>
                </tr>
            `
        )
        .join("");
}


async function loadExperiments() {
    const data = await requestJson(
        "/experiments?limit=50"
    );

    const tableBody = document.getElementById(
        "experiments-body"
    );

    const experiments = data.experiments ?? [];

    if (!experiments.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    No experiments available.
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = experiments
        .map(
            (experiment) => `
                <tr>
                    <td>${experiment.id}</td>

                    <td>
                        ${experiment.scenario_name}
                    </td>

                    <td>
                        ${experiment.resource_name}
                    </td>

                    <td>
                        ${formatDate(
                            experiment.started_at
                        )}
                    </td>

                    <td>
                        ${formatSeconds(
                            experiment.recovery_seconds
                        )}
                    </td>

                    <td>
                        ${createStatusBadge(
                            experiment.result
                        )}
                    </td>

                    <td>
                        ${experiment.details ?? "--"}
                    </td>
                </tr>
            `
        )
        .join("");
}


async function loadIncidents() {
    const data = await requestJson(
        "/incidents?limit=20"
    );

    const tableBody = document.getElementById(
        "incidents-body"
    );

    const incidents = data.incidents ?? [];

    if (!incidents.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6">
                    No incidents available.
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = incidents
        .map(
            (incident) => `
                <tr>
                    <td>${incident.id}</td>

                    <td>
                        ${incident.resource_name}
                    </td>

                    <td>
                        ${incident.incident_type}
                    </td>

                    <td>
                        ${incident.severity}
                    </td>

                    <td>
                        ${createStatusBadge(
                            incident.status
                        )}
                    </td>

                    <td>
                        ${formatDate(
                            incident.detected_at
                        )}
                    </td>
                </tr>
            `
        )
        .join("");
}


async function loadDashboard() {
    const errorElement = document.getElementById(
        "error-message"
    );

    errorElement.textContent = "";

    try {
        await Promise.all([
            loadIncidentStatistics(),
            loadExperimentStatistics(),
            loadExperiments(),
            loadIncidents(),
        ]);
    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Dashboard data could not be loaded. " +
            "Check that incident-api is running on port 8080.";
    }
}


document
    .getElementById("refresh-button")
    .addEventListener(
        "click",
        loadDashboard
    );


loadDashboard();

setInterval(
    loadDashboard,
    15000
);