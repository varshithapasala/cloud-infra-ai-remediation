import time

import docker
import requests


class RecoveryVerifier:
    def __init__(self):
        self.client = docker.from_env()

    def verify(
        self,
        resource_name: str,
        attempts: int = 8,
        delay_seconds: int = 5,
    ) -> tuple[bool, str]:
        for _ in range(attempts):
            try:
                container = (
                    self.client.containers.get(
                        resource_name
                    )
                )

                container.reload()

                state = container.attrs.get(
                    "State",
                    {},
                )

                health = (
                    state.get(
                        "Health",
                        {},
                    )
                    .get("Status")
                )

                if (
                    container.status == "running"
                    and health
                    in {
                        None,
                        "healthy",
                    }
                ):
                    if resource_name == "order-api":
                        response = requests.get(
                            "http://order-api:8000/ready",
                            timeout=5,
                        )

                        if response.status_code == 200:
                            return (
                                True,
                                "Readiness check passed",
                            )
                    else:
                        return (
                            True,
                            "Container is running",
                        )

            except (
                docker.errors.DockerException,
                requests.RequestException,
            ):
                pass

            time.sleep(delay_seconds)

        return (
            False,
            "Recovery verification failed",
        )