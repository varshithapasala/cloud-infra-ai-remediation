from typing import Any

import docker

from remediation_agent.models import ContainerSnapshot


class DockerCollector:
    def __init__(self):
        self.client = docker.from_env()

    def get_managed_containers(
        self,
    ) -> list[ContainerSnapshot]:
        containers = self.client.containers.list(
            all=True,
            filters={
                "label": "remediation.enabled=true",
            },
        )

        return [
            self._build_snapshot(container)
            for container in containers
        ]

    def _build_snapshot(
        self,
        container,
    ) -> ContainerSnapshot:
        container.reload()

        state = container.attrs.get(
            "State",
            {},
        )

        health = (
            state.get("Health", {})
            .get("Status")
        )

        cpu_percent = 0.0
        memory_percent = 0.0

        if container.status == "running":
            try:
                stats = container.stats(
                    stream=False,
                )

                cpu_percent = self._calculate_cpu(
                    stats
                )

                memory_percent = (
                    self._calculate_memory(stats)
                )

            except docker.errors.DockerException:
                pass

        logs = container.logs(
            tail=40,
            timestamps=True,
        ).decode(
            "utf-8",
            errors="replace",
        )

        return ContainerSnapshot(
            name=container.name,
            container_id=container.id,
            status=container.status,
            health=health,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            restart_count=container.attrs.get(
                "RestartCount",
                0,
            ),
            logs=logs,
        )

    @staticmethod
    def _calculate_cpu(
        stats: dict[str, Any],
    ) -> float:
        cpu_stats = stats.get(
            "cpu_stats",
            {},
        )

        previous_cpu_stats = stats.get(
            "precpu_stats",
            {},
        )

        cpu_delta = (
            cpu_stats
            .get("cpu_usage", {})
            .get("total_usage", 0)
            -
            previous_cpu_stats
            .get("cpu_usage", {})
            .get("total_usage", 0)
        )

        system_delta = (
            cpu_stats.get(
                "system_cpu_usage",
                0,
            )
            -
            previous_cpu_stats.get(
                "system_cpu_usage",
                0,
            )
        )

        online_cpus = cpu_stats.get(
            "online_cpus",
            1,
        )

        if system_delta <= 0:
            return 0.0

        return (
            cpu_delta
            / system_delta
            * online_cpus
            * 100
        )

    @staticmethod
    def _calculate_memory(
        stats: dict[str, Any],
    ) -> float:
        memory_stats = stats.get(
            "memory_stats",
            {},
        )

        usage = memory_stats.get(
            "usage",
            0,
        )

        limit = memory_stats.get(
            "limit",
            0,
        )

        if limit <= 0:
            return 0.0

        return usage / limit * 100