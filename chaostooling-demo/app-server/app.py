import json
import logging
import os

import pika
import psycopg2
import redis
import requests
from flask import Flask, jsonify, request
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from chaosotel.core.trace_core import trace_kafka_produce

# Setup OpenTelemetry with proper service name
service_name = os.getenv("OTEL_SERVICE_NAME", "app-server")
resource = Resource.create(
    {
        "service.name": service_name,
        "service.version": "1.0.0",
    }
)
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
    insecure=True,
)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
Psycopg2Instrumentor().instrument()
PikaInstrumentor().instrument()
RedisInstrumentor().instrument()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    # Support for multiple hosts (Primary + Replica)
    # Format: "host1:port1,host2:port2"
    # We use target_session_attrs='read-write' to ensure we get the primary for writes
    # But for this simple app, we might just want to connect to *any* available for reads,
    # and fail on writes if we hit a replica that is read-only (though postgres user is usually superuser in docker).
    # Let's assume we want to connect to Primary.

    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")

    # If host contains comma, it's a list
    if "," in host:
        # Construct libpq connection string
        # postgresql://user:password@host1:port1,host2:port2/dbname?target_session_attrs=read-write
        dsn = f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@{host}/{os.getenv('POSTGRES_DB', 'testdb')}?target_session_attrs=read-write"
        return psycopg2.connect(dsn)
    else:
        return psycopg2.connect(
            host=host,
            port=port,
            dbname=os.getenv("POSTGRES_DB", "testdb"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        )


def get_rabbitmq_connection():
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "chaos")
    password = os.getenv("RABBITMQ_PASSWORD", "password")
    credentials = pika.PlainCredentials(user, password)
    parameters = pika.ConnectionParameters(host, port, "/", credentials)
    return pika.BlockingConnection(parameters)


def get_redis_connection():
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, db=0, decode_responses=True)


@app.route("/purchase", methods=["POST"])
def purchase():
    """
    Distributed transaction flow (8-10 hops):
    1. HA-Proxy → App Server (this service)
    2. App Server → Payment Service (HTTP)
    3. Payment Service → RabbitMQ (publish)
    4. Payment Service → PostgreSQL (write)
    5. App Server → Order Service (HTTP)
    6. Order Service → Kafka (publish)
    7. Order Service → PostgreSQL (write)
    8. App Server → Inventory Service (HTTP)
    9. Inventory Service → MongoDB (read/write)
    10. Inventory Service → Redis (cache)
    11. App Server → PostgreSQL (write final transaction)
    """
    data = request.json
    user_id = data.get("user_id")
    amount = data.get("amount")
    item_id = data.get("item_id")

    logger.info(f"Received purchase request: {data}")

    # Hop 2: Call Payment Service
    payment_service_url = os.getenv(
        "PAYMENT_SERVICE_URL", "http://payment-service:5000"
    )
    payment_data = None
    try:
        resp = requests.post(
            f"{payment_service_url}/process",
            json={"amount": amount, "user_id": user_id},
            timeout=5,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Payment failed"}), 502
        payment_data = resp.json()
        payment_id = payment_data.get("payment_id")
    except requests.exceptions.RequestException as e:
        logger.error(f"Payment service failed: {e}")
        return jsonify({"error": "Payment service unavailable"}), 503

    # Hop 5: Call Order Service
    order_service_url = os.getenv(
        "ORDER_SERVICE_URL", "http://order-service-site-a:5000"
    )
    order_data = None
    try:
        resp = requests.post(
            f"{order_service_url}/create",
            json={"user_id": user_id, "item_id": item_id, "quantity": 1},
            timeout=5,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Order creation failed"}), 502
        order_data = resp.json()
        order_id = order_data.get("order_id")
    except requests.exceptions.RequestException as e:
        logger.error(f"Order service failed: {e}")
        return jsonify({"error": "Order service unavailable"}), 503

    # NEW: Cache payment + order data in Redis
    try:
        redis_client = get_redis_connection()
        cache_key = f"transaction:{user_id}:{order_id}"
        cache_data = {
            "payment_id": payment_id,
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "item_id": item_id,
            "status": "pending",
        }
        redis_client.setex(
            cache_key,
            3600,  # TTL: 1 hour
            json.dumps(cache_data),
        )
        logger.info(f"Cached payment+order data in Redis: {cache_key}")
    except Exception as e:
        logger.warning(f"Redis cache failed (non-critical): {e}")

    # Hop 8: Call Inventory Service
    inventory_service_url = os.getenv(
        "INVENTORY_SERVICE_URL", "http://inventory-service-site-a:5000"
    )
    try:
        resp = requests.post(
            f"{inventory_service_url}/check",
            json={"item_id": item_id, "quantity": 1},
            timeout=5,
        )
        if resp.status_code != 200:
            return jsonify({"error": "Inventory check failed"}), 502
        inventory_data = resp.json()
        if inventory_data.get("status") != "available":
            return jsonify({"error": "Item out of stock"}), 400
    except requests.exceptions.RequestException as e:
        logger.error(f"Inventory service failed: {e}")
        return jsonify({"error": "Inventory service unavailable"}), 503

    # Hop 11: Write final transaction to PostgreSQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mobile_purchases (user_id, amount, item_id, order_id, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, amount, item_id, order_id, "COMPLETED"),
        )
        transaction_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # Publish event to Kafka for async processing
    trace_kafka_produce(
        "purchases",
        {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "item_id": item_id,
            "order_id": order_id,
            "status": "COMPLETED",
        },
        additional_attributes={"transaction.id": transaction_id},
    )

    return (
        jsonify(
            {
                "status": "success",
                "message": "Purchase completed",
                "transaction_id": transaction_id,
                "order_id": order_id,
            }
        ),
        200,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
