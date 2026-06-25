import os
import time

import redis
from fastapi import Depends, FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Order
from app.schemas import OrderCreate, OrderResponse

app = FastAPI(
    title="Order Processing Demo API",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    decode_responses=True,
)

REQUEST_COUNTER = Counter(
    "order_api_requests_total",
    "Number of API requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "order_api_request_duration_seconds",
    "API request duration",
    ["endpoint"],
)

ORDERS_CREATED = Counter(
    "orders_created_total",
    "Number of orders created",
)

application_healthy = True


@app.get("/")
def root():
    return {
        "service": "order-api",
        "status": "running",
    }


@app.get("/health")
def health():
    if not application_healthy:
        REQUEST_COUNTER.labels(
            method="GET",
            endpoint="/health",
            status="503",
        ).inc()

        raise HTTPException(
            status_code=503,
            detail="Application is unhealthy",
        )

    REQUEST_COUNTER.labels(
        method="GET",
        endpoint="/health",
        status="200",
    ).inc()

    return {
        "status": "alive",
    }


@app.get("/ready")
def ready(
    database: Session = Depends(get_db),
):
    database_status = False
    redis_status = False

    try:
        database.execute(text("SELECT 1"))
        database_status = True
    except Exception:
        database_status = False

    try:
        redis_status = bool(redis_client.ping())
    except Exception:
        redis_status = False

    if not database_status or not redis_status:
        raise HTTPException(
            status_code=503,
            detail={
                "database": database_status,
                "redis": redis_status,
            },
        )

    return {
        "status": "ready",
        "database": "available",
        "redis": "available",
    }


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=201,
)
def create_order(
    order_data: OrderCreate,
    database: Session = Depends(get_db),
):
    started_at = time.perf_counter()

    order = Order(
        customer_name=order_data.customer_name,
        product_name=order_data.product_name,
        quantity=order_data.quantity,
        status="PENDING",
    )

    database.add(order)
    database.commit()
    database.refresh(order)

    redis_client.lpush(
        "order_queue",
        str(order.id),
    )

    ORDERS_CREATED.inc()

    REQUEST_COUNTER.labels(
        method="POST",
        endpoint="/orders",
        status="201",
    ).inc()

    REQUEST_DURATION.labels(
        endpoint="/orders"
    ).observe(
        time.perf_counter() - started_at
    )

    return order


@app.get(
    "/orders",
    response_model=list[OrderResponse],
)
def list_orders(
    database: Session = Depends(get_db),
):
    return (
        database.query(Order)
        .order_by(Order.id.desc())
        .all()
    )


@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
)
def get_order(
    order_id: int,
    database: Session = Depends(get_db),
):
    order = (
        database.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order


@app.post("/simulate/unhealthy")
def simulate_unhealthy():
    global application_healthy

    application_healthy = False

    return {
        "message": "Application is now unhealthy",
    }


@app.post("/simulate/healthy")
def simulate_healthy():
    global application_healthy

    application_healthy = True

    return {
        "message": "Application is healthy",
    }


@app.get("/simulate/slow")
def simulate_slow():
    with REQUEST_DURATION.labels(
        endpoint="/simulate/slow"
    ).time():
        time.sleep(8)

    return {
        "message": "Slow request completed",
    }


metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)