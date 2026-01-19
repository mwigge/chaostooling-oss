import logging
import os
import sys

import pymysql
from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# Use common OTEL setup for consistent service graph visibility
sys.path.insert(0, "/app/common")
from otel_setup import setup_otel

from chaosotel.core.trace_core import trace_kafka_produce, set_db_span_attributes

# Setup OpenTelemetry for service graph visibility
service_name = os.getenv("OTEL_SERVICE_NAME", "order-service")
setup_otel(service_name)
tracer = trace.get_tracer(__name__)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Connect to MySQL database (changed from PostgreSQL)."""
    host = os.getenv("MYSQL_HOST", "mysql")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    return pymysql.connect(
        host=host,
        port=port,
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "mysql"),
        database=os.getenv("MYSQL_DB", "testdb"),
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.route("/create", methods=["POST"])
def create_order():
    """
    Order creation with distributed transaction:
    1. Write order to MySQL
    2. Publish order event to Kafka (after MySQL write)
    """
    data = request.json
    user_id_raw = data.get("user_id")
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)

    # Convert user_id to integer (handle both "user_123" and 123 formats)
    if isinstance(user_id_raw, str) and user_id_raw.startswith("user_"):
        user_id = int(user_id_raw.replace("user_", ""))
    elif isinstance(user_id_raw, (int, float)):
        user_id = int(user_id_raw)
    else:
        user_id = int(user_id_raw) if user_id_raw else 0

    logger.info(
        f"Creating order: user_id={user_id}, item_id={item_id}, quantity={quantity}"
    )

    # Write order to MySQL with manual instrumentation for service graph visibility
    mysql_host = os.getenv("MYSQL_HOST", "mysql")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_db = os.getenv("MYSQL_DB", "testdb")
    
    try:
        with tracer.start_as_current_span("mysql.insert") as span:
            # Set database span attributes for service graph visibility
            set_db_span_attributes(
                span,
                db_system="mysql",
                db_name=mysql_db,
                db_operation="insert",
                host=mysql_host,
                port=mysql_port,
            )
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO orders (user_id, item_id, quantity, status) VALUES (%s, %s, %s, %s)",
                (user_id, item_id, quantity, "PENDING"),
            )
            order_id = cur.lastrowid  # MySQL uses lastrowid instead of RETURNING
            conn.commit()
            cur.close()
            conn.close()
            span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info(f"Order {order_id} written to MySQL")
    except Exception as e:
        logger.error(f"Database failed: {e}")
        if span:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
        return jsonify({"error": "Database error"}), 500

    # Publish order event to Kafka after MySQL write
    success = trace_kafka_produce(
        "order-events",
        {
            "order_id": order_id,
            "user_id": user_id,
            "item_id": item_id,
            "quantity": quantity,
            "status": "PENDING",
            "source": "mysql",
        },
        additional_attributes={"order.id": order_id},
    )
    if not success:
        logger.error(f"Kafka publish failed for order {order_id}")
        return jsonify({"error": "Kafka error"}), 500
    logger.info(f"Order {order_id} published to Kafka (from MySQL)")

    return jsonify({"status": "success", "order_id": order_id}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
