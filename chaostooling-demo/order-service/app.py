import os
import logging
import json
from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
import pymysql
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# Setup OpenTelemetry with proper service name
service_name = os.getenv("OTEL_SERVICE_NAME", "order-service")
resource = Resource.create({
    "service.name": service_name,
    "service.version": "1.0.0",
})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

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
        cursorclass=pymysql.cursors.DictCursor
    )

def get_kafka_producer():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

@app.route('/create', methods=['POST'])
def create_order():
    """
    Order creation with distributed transaction:
    1. Write order to MySQL
    2. Publish order event to Kafka (after MySQL write)
    """
    data = request.json
    user_id_raw = data.get('user_id')
    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)

    # Convert user_id to integer (handle both "user_123" and 123 formats)
    if isinstance(user_id_raw, str) and user_id_raw.startswith('user_'):
        user_id = int(user_id_raw.replace('user_', ''))
    elif isinstance(user_id_raw, (int, float)):
        user_id = int(user_id_raw)
    else:
        user_id = int(user_id_raw) if user_id_raw else 0

    logger.info(f"Creating order: user_id={user_id}, item_id={item_id}, quantity={quantity}")

    # Write order to MySQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, item_id, quantity, status) VALUES (%s, %s, %s, %s)",
            (user_id, item_id, quantity, "PENDING")
        )
        order_id = cur.lastrowid  # MySQL uses lastrowid instead of RETURNING
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Order {order_id} written to MySQL")
    except Exception as e:
        logger.error(f"Database failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # Publish order event to Kafka after MySQL write
    try:
        producer = get_kafka_producer()
        producer.send('order-events', {
            'order_id': order_id,
            'user_id': user_id,
            'item_id': item_id,
            'quantity': quantity,
            'status': 'PENDING',
            'source': 'mysql'
        })
        producer.flush()
        producer.close()
        logger.info(f"Order {order_id} published to Kafka (from MySQL)")
    except Exception as e:
        logger.error(f"Kafka failed: {e}")
        return jsonify({"error": "Kafka error"}), 500

    return jsonify({"status": "success", "order_id": order_id}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

