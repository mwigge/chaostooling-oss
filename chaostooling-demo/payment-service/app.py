import logging
import os
import json
import psycopg2
import pika
from flask import Flask, request, jsonify
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor

# Setup OpenTelemetry with proper service name
service_name = os.getenv("OTEL_SERVICE_NAME", "payment-service")
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
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def get_rabbitmq_connection():
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "chaos")
    password = os.getenv("RABBITMQ_PASSWORD", "password")
    credentials = pika.PlainCredentials(user, password)
    parameters = pika.ConnectionParameters(host, port, '/', credentials)
    return pika.BlockingConnection(parameters)

@app.route('/process', methods=['POST'])
def process_payment():
    """
    Payment processing with distributed transaction:
    1. Receive payment request
    2. Write payment record to PostgreSQL (Hop 4)
    3. Publish payment event to RabbitMQ (Hop 3)
    """
    data = request.json
    amount = data.get('amount')
    user_id = data.get('user_id')
    
    logger.info(f"Processing payment: {data}")

    # Hop 4: Write to PostgreSQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (user_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
            (user_id, amount, "PROCESSED")
        )
        payment_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # Hop 3: Publish to RabbitMQ
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='payments', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='payments',
            body=json.dumps({
                'payment_id': payment_id,
                'user_id': user_id,
                'amount': amount,
                'status': 'PROCESSED'
            }),
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        connection.close()
    except Exception as e:
        logger.warning(f"RabbitMQ publish failed (non-critical): {e}")

    return jsonify({"status": "processed", "payment_id": payment_id}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

