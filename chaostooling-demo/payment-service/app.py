import json
import logging
import os

import pika
import psycopg2
from flask import Flask, jsonify, request
from kafka import KafkaProducer
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup OpenTelemetry with proper service name
service_name = os.getenv("OTEL_SERVICE_NAME", "payment-service")
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
Psycopg2Instrumentor().instrument()
PikaInstrumentor().instrument()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    host = os.getenv("POSTGRES_HOST", "postgres-primary-site-a")
    port = os.getenv("POSTGRES_PORT", "5432")
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


def get_kafka_producer():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


@app.route("/process", methods=["POST"])
def process_payment():
    """
    Payment processing with distributed transaction:
    1. Receive payment request
    2. Write payment record to PostgreSQL
    3. Publish payment event to RabbitMQ
    4. Publish payment event to Kafka (after PostgreSQL write)
    """
    data = request.json
    amount = data.get("amount")
    user_id_raw = data.get("user_id")

    # Convert user_id to integer (handle both "user_123" and 123 formats)
    if isinstance(user_id_raw, str) and user_id_raw.startswith("user_"):
        user_id = int(user_id_raw.replace("user_", ""))
    elif isinstance(user_id_raw, (int, float)):
        user_id = int(user_id_raw)
    else:
        user_id = int(user_id_raw) if user_id_raw else 0

    logger.info(f"Processing payment: amount={amount}, user_id={user_id}")

    # Write to PostgreSQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (user_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
            (user_id, amount, "PROCESSED"),
        )
        payment_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Payment {payment_id} written to PostgreSQL")
    except Exception as e:
        logger.error(f"Database failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # Publish to RabbitMQ
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue="payments", durable=True)
        channel.basic_publish(
            exchange="",
            routing_key="payments",
            body=json.dumps(
                {
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "amount": amount,
                    "status": "PROCESSED",
                }
            ),
            properties=pika.BasicProperties(delivery_mode=2),  # Make message persistent
        )
        connection.close()
        logger.info(f"Payment {payment_id} published to RabbitMQ")
    except Exception as e:
        logger.warning(f"RabbitMQ publish failed (non-critical): {e}")

    # NEW: Publish to Kafka after PostgreSQL write
    try:
        producer = get_kafka_producer()
        producer.send(
            "payment-events",
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "amount": amount,
                "status": "PROCESSED",
                "source": "postgresql",
            },
        )
        producer.flush()
        producer.close()
        logger.info(f"Payment {payment_id} published to Kafka (from PostgreSQL)")
    except Exception as e:
        logger.warning(f"Kafka publish failed (non-critical): {e}")

    return jsonify({"status": "processed", "payment_id": payment_id}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
