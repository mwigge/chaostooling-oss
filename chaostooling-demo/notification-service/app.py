import json
import logging
import os
import threading
import time

import psycopg2
from flask import Flask, jsonify
from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Setup OpenTelemetry with proper service name
service_name = os.getenv("OTEL_SERVICE_NAME", "notification-service")
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global consumer instance
consumer = None
consumer_thread = None
running = False


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


def get_kafka_consumer():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return KafkaConsumer(
        "orders",
        "purchases",
        bootstrap_servers=bootstrap_servers.split(","),
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="notification-service-group",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        consumer_timeout_ms=1000,
    )


def process_message(message):
    """Process a Kafka message and update database"""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("kafka.consume") as span:
        topic = message.topic
        value = message.value

        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", topic)
        span.set_attribute("messaging.operation", "receive")

        try:
            logger.info(f"Received message from {topic}: {value}")

            # Process orders topic
            if topic == "orders":
                order_id = value.get("order_id")
                user_id = value.get("user_id")
                status = value.get("status")

                span.set_attribute("order.id", str(order_id))
                span.set_attribute("order.status", status)

                # Update order status in database
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s",
                    ("PROCESSED", order_id),
                )
                conn.commit()
                cur.close()
                conn.close()

                logger.info(f"Updated order {order_id} status to PROCESSED")
                span.set_status(Status(StatusCode.OK))

            # Process purchases topic
            elif topic == "purchases":
                transaction_id = value.get("transaction_id")
                user_id = value.get("user_id")
                amount = value.get("amount")
                status = value.get("status")

                span.set_attribute("transaction.id", str(transaction_id))
                span.set_attribute("transaction.status", status)

                # Log purchase notification (in real system, would send email/SMS)
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO notifications (user_id, type, message, status, created_at) 
                       VALUES (%s, %s, %s, %s, NOW()) 
                       ON CONFLICT DO NOTHING""",
                    (user_id, "purchase", f"Purchase completed: ${amount}", "sent"),
                )
                conn.commit()
                cur.close()
                conn.close()

                logger.info(f"Sent notification for transaction {transaction_id}")
                span.set_status(Status(StatusCode.OK))

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))


def consume_messages():
    """Background thread to consume Kafka messages"""
    global consumer, running

    tracer = trace.get_tracer(__name__)

    while running:
        try:
            with tracer.start_as_current_span("kafka.consume.batch") as span:
                messages = consumer.poll(timeout_ms=1000)

                if messages:
                    span.set_attribute("messaging.batch.size", len(messages))

                    for topic_partition, message_list in messages.items():
                        for message in message_list:
                            process_message(message)

        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            time.sleep(1)


@app.route("/health", methods=["GET"])
def health():
    return (
        jsonify(
            {
                "status": "ok",
                "consumer_running": running,
                "service": "notification-service",
            }
        ),
        200,
    )


@app.route("/start-consumer", methods=["POST"])
def start_consumer():
    """Start the Kafka consumer"""
    global consumer, consumer_thread, running

    if running:
        return jsonify({"status": "already running"}), 200

    try:
        consumer = get_kafka_consumer()
        running = True
        consumer_thread = threading.Thread(target=consume_messages, daemon=True)
        consumer_thread.start()
        logger.info("Kafka consumer started")
        return jsonify({"status": "started"}), 200
    except Exception as e:
        logger.error(f"Failed to start consumer: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/stop-consumer", methods=["POST"])
def stop_consumer():
    """Stop the Kafka consumer"""
    global consumer, running

    if not running:
        return jsonify({"status": "not running"}), 200

    try:
        running = False
        if consumer:
            consumer.close()
        logger.info("Kafka consumer stopped")
        return jsonify({"status": "stopped"}), 200
    except Exception as e:
        logger.error(f"Failed to stop consumer: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Auto-start consumer on service startup
    try:
        consumer = get_kafka_consumer()
        running = True
        consumer_thread = threading.Thread(target=consume_messages, daemon=True)
        consumer_thread.start()
        logger.info("Kafka consumer auto-started")
    except Exception as e:
        logger.warning(f"Failed to auto-start consumer: {e}")

    app.run(host="0.0.0.0", port=5000)
