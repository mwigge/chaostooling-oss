import json
import logging
import os
import time

import psycopg2
import requests
from chaosotel import ensure_initialized, flush, get_tracer
from kafka import KafkaProducer
from opentelemetry.propagate import inject
from opentelemetry.trace import StatusCode


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "testdb"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_purchase_table_exists():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mobile_purchases (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INT NOT NULL,
                    amount FLOAT NOT NULL,
                    item_id VARCHAR(255) NOT NULL,
                    status VARCHAR(50)
                );
            """)
        conn.commit()
    finally:
        conn.close()


def publish_purchase_event(user_id: int, amount: float, item_id: str):
    """
    Publish a purchase event to Kafka with OpenTelemetry context.
    """
    tracer = get_tracer()
    logger = logging.getLogger("chaosapp.actions.client")

    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = "mobile_orders"

    with tracer.start_as_current_span("mobile.client.kafka_produce") as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", topic)

        try:
            producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )

            message = {
                "user_id": user_id,
                "amount": amount,
                "item_id": item_id,
                "timestamp": time.time(),
            }

            # Inject OTEL context into Kafka headers
            headers = {}
            inject(headers)
            # Kafka headers must be list of tuples (str, bytes)
            kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            producer.send(topic, value=message, headers=kafka_headers)
            producer.flush()

            span.set_status(StatusCode.OK)
            logger.info(f"Published purchase event to {topic}")

        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Failed to publish to Kafka: {e}")
            # We don't fail the whole action if Kafka fails, just log it (or we could, depending on requirements)
            # For now, let's keep it robust.


def simulate_purchase(user_id: int, amount: float, item_id: str) -> bool:
    """
    Simulate a mobile app purchase transaction.
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosapp.actions.client")

    ensure_purchase_table_exists()

    with tracer.start_as_current_span("mobile.client.purchase") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("purchase.amount", amount)
        span.set_attribute("item.id", item_id)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Simulate processing time
                time.sleep(0.1)

                cursor.execute(
                    "INSERT INTO mobile_purchases (user_id, amount, item_id, status) VALUES (%s, %s, %s, %s)",
                    (user_id, amount, item_id, "COMPLETED"),
                )
            conn.commit()

            # Publish event to Kafka
            publish_purchase_event(user_id, amount, item_id)

            span.set_status(StatusCode.OK)
            logger.info(
                f"Purchase completed for user {user_id}: {amount} for {item_id}"
            )
            flush()
            return True

        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Purchase failed: {e}")
            flush()
            return False
        finally:
            conn.close()


def simulate_purchase_via_api(
    user_id: int, amount: float, item_id: str, url: str = "http://haproxy:80/purchase"
) -> bool:
    """
    Simulate a purchase by calling the App Server API.
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosapp.actions.client")

    with tracer.start_as_current_span("mobile.client.api_purchase") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("purchase.amount", amount)
        span.set_attribute("http.url", url)

        try:
            # Inject trace context into HTTP headers
            headers = {}
            inject(headers)

            payload = {"user_id": user_id, "amount": amount, "item_id": item_id}

            resp = requests.post(url, json=payload, headers=headers, timeout=5)

            if resp.status_code == 200:
                span.set_status(StatusCode.OK)
                logger.info(f"API Purchase successful: {resp.json()}")
                return True
            else:
                span.set_status(StatusCode.ERROR, f"HTTP {resp.status_code}")
                logger.error(f"API Purchase failed: {resp.text}")
                return False

        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"API Purchase exception: {e}")
            return False
