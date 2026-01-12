import os
import logging
import json
from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
import psycopg2
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

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
Psycopg2Instrumentor().instrument()

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
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def get_kafka_producer():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

@app.route('/create', methods=['POST'])
def create_order():
    data = request.json
    user_id = data.get('user_id')
    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)

    logger.info(f"Creating order: {data}")

    # 1. Write order to PostgreSQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, item_id, quantity, status) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, item_id, quantity, "PENDING")
        )
        order_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # 2. Publish order event to Kafka
    try:
        producer = get_kafka_producer()
        producer.send('orders', {
            'order_id': order_id,
            'user_id': user_id,
            'item_id': item_id,
            'quantity': quantity,
            'status': 'PENDING'
        })
        producer.flush()
        producer.close()
    except Exception as e:
        logger.error(f"Kafka failed: {e}")
        return jsonify({"error": "Kafka error"}), 500

    return jsonify({"status": "success", "order_id": order_id}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

