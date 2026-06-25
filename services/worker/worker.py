import os
import time
from datetime import datetime, timezone

import redis
from prometheus_client import Counter, start_http_server
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://clouduser:cloudpass@postgres:5432/clouddb",
)

REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "redis",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
)

ORDERS_PROCESSED = Counter(
    "worker_orders_processed_total",
    "Number of orders processed",
)

WORKER_FAILURES = Counter(
    "worker_processing_failures_total",
    "Number of worker failures",
)


def update_heartbeat() -> None:
    redis_client.set(
        "worker:last_heartbeat",
        datetime.now(timezone.utc).isoformat(),
        ex=60,
    )


def process_order(order_id: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE orders
                SET status = 'PROCESSING'
                WHERE id = :order_id
                """
            ),
            {
                "order_id": order_id,
            },
        )

    time.sleep(3)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE orders
                SET status = 'COMPLETED'
                WHERE id = :order_id
                """
            ),
            {
                "order_id": order_id,
            },
        )

    ORDERS_PROCESSED.inc()


def run_worker() -> None:
    start_http_server(9101)

    print("Order worker started", flush=True)

    while True:
        try:
            update_heartbeat()

            queue_item = redis_client.brpop(
                "order_queue",
                timeout=5,
            )

            if queue_item is None:
                continue

            _, order_id = queue_item

            process_order(int(order_id))

            print(
                f"Processed order {order_id}",
                flush=True,
            )

        except Exception as exc:
            WORKER_FAILURES.inc()

            print(
                f"Worker error: {exc}",
                flush=True,
            )

            time.sleep(5)


if __name__ == "__main__":
    run_worker()