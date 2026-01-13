#!/usr/bin/env python3
"""
Background Transaction Load Generator

Generates continuous distributed transactions across:
- Multiple databases (PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra)
- Event messaging systems (Kafka, RabbitMQ, ActiveMQ)

Transaction Flow:
1. App Server → Payment Service → RabbitMQ → PostgreSQL
2. App Server → Order Service → Kafka → MySQL
3. App Server → Inventory Service → MongoDB → Redis
4. Kafka Consumer → ActiveMQ → MSSQL
5. RabbitMQ Consumer → Cassandra

This simulates a real transaction platform with event-driven architecture.

All transactions are instrumented with OpenTelemetry for distributed tracing.
"""

import os
import time
import logging
import threading
import requests
from typing import Dict, Optional
from datetime import datetime

# OpenTelemetry instrumentation for distributed tracing
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Setup OpenTelemetry for service graph visibility
service_name = os.getenv("OTEL_SERVICE_NAME", "transaction-load-generator")
resource = Resource.create({
    "service.name": service_name,
    "service.version": "1.0.0",
})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
    insecure=True
)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
RequestsInstrumentor().instrument()  # Auto-instrument HTTP requests with trace context

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("transaction_load_generator")

# Configuration from environment
API_URL = os.getenv("API_URL", "http://haproxy-site-a:80")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "chaos")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "password")
ACTIVEMQ_HOST = os.getenv("ACTIVEMQ_HOST", "activemq")
ACTIVEMQ_PORT = int(os.getenv("ACTIVEMQ_PORT", "61616"))
ACTIVEMQ_USER = os.getenv("ACTIVEMQ_USER", "admin")
ACTIVEMQ_PASSWORD = os.getenv("ACTIVEMQ_PASSWORD", "admin")

# Load generation parameters
TRANSACTIONS_PER_SECOND = float(os.getenv("TRANSACTIONS_PER_SECOND", "2.0"))
RUNNING = threading.Event()
RUNNING.set()  # Start running by default


class TransactionLoadGenerator:
    """Generates continuous transaction load across multiple systems."""
    
    def __init__(self, api_url: str, tps: float = 2.0):
        self.api_url = api_url
        self.tps = tps
        self.interval = 1.0 / tps if tps > 0 else 1.0
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "start_time": None,
            "last_transaction_time": None
        }
        self.thread = None
    
    def generate_transaction(self) -> Dict:
        """Generate a single transaction with OpenTelemetry tracing."""
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("transaction.generate") as span:
            user_id = int(time.time() * 1000) % 10000  # Rotating user IDs
            amount = round(10.0 + (user_id % 100), 2)
            item_id = f"item_{user_id % 1000}"
            
            payload = {
                "user_id": user_id,
                "amount": amount,
                "item_id": item_id
            }
            
            # Set span attributes for better trace visibility
            span.set_attribute("transaction.user_id", user_id)
            span.set_attribute("transaction.amount", amount)
            span.set_attribute("transaction.item_id", item_id)
            span.set_attribute("http.url", f"{self.api_url}/purchase")
            span.set_attribute("http.method", "POST")
            
            try:
                # HTTP request is auto-instrumented by RequestsInstrumentor
                # Trace context is automatically propagated in headers
                response = requests.post(
                    f"{self.api_url}/purchase",
                    json=payload,
                    timeout=10
                )
                
                span.set_attribute("http.status_code", response.status_code)
                
                if response.status_code == 200:
                    span.set_status(Status(StatusCode.OK))
                    return {"status": "success", "payload": payload, "response": response.json()}
                else:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    return {"status": "failed", "payload": payload, "error": f"HTTP {response.status_code}"}
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                return {"status": "failed", "payload": payload, "error": str(e)}
    
    def run(self):
        """Run continuous transaction generation."""
        logger.info(f"Starting transaction load generator: {self.tps} TPS")
        self.stats["start_time"] = datetime.now()
        
        while RUNNING.is_set():
            start = time.time()
            
            # Generate transaction
            result = self.generate_transaction()
            self.stats["total"] += 1
            self.stats["last_transaction_time"] = datetime.now()
            
            if result["status"] == "success":
                self.stats["successful"] += 1
                logger.debug(f"Transaction successful: {result['payload']}")
            else:
                self.stats["failed"] += 1
                logger.warning(f"Transaction failed: {result.get('error', 'Unknown error')}")
            
            # Maintain TPS rate
            elapsed = time.time() - start
            sleep_time = max(0, self.interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def start(self):
        """Start the load generator in a background thread."""
        if self.thread and self.thread.is_alive():
            logger.warning("Load generator already running")
            return
        
        RUNNING.set()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("Load generator started")
    
    def stop(self):
        """Stop the load generator."""
        RUNNING.clear()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Load generator stopped")
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        stats = self.stats.copy()
        if stats["start_time"]:
            duration = (datetime.now() - stats["start_time"]).total_seconds()
            stats["duration_seconds"] = duration
            stats["actual_tps"] = stats["total"] / duration if duration > 0 else 0
            stats["success_rate"] = stats["successful"] / stats["total"] if stats["total"] > 0 else 0
        return stats


# Global generator instance
_generator: Optional[TransactionLoadGenerator] = None


def start_load_generator(tps: float = 2.0):
    """Start the background transaction load generator."""
    global _generator
    if _generator is None:
        _generator = TransactionLoadGenerator(API_URL, tps)
    _generator.start()
    return {"status": "started", "tps": tps}


def stop_load_generator():
    """Stop the background transaction load generator."""
    global _generator
    if _generator:
        _generator.stop()
        return {"status": "stopped", "stats": _generator.get_stats()}
    return {"status": "not_running"}


def get_load_stats():
    """Get current load generator statistics."""
    global _generator
    if _generator:
        return _generator.get_stats()
    return {"status": "not_running"}


# Flask API for control
from flask import Flask, jsonify, request  # noqa: E402

app = Flask(__name__)


@app.route('/start', methods=['POST'])
def start():
    """Start the load generator."""
    data = request.json or {}
    tps = float(data.get('tps', TRANSACTIONS_PER_SECOND))
    result = start_load_generator(tps)
    return jsonify(result)


@app.route('/stop', methods=['POST'])
def stop():
    """Stop the load generator."""
    result = stop_load_generator()
    return jsonify(result)


@app.route('/stats', methods=['GET'])
def stats():
    """Get load generator statistics."""
    result = get_load_stats()
    return jsonify(result)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "running": RUNNING.is_set()})


if __name__ == "__main__":
    # Auto-start if environment variable is set
    if os.getenv("AUTO_START", "false").lower() == "true":
        tps = float(os.getenv("TRANSACTIONS_PER_SECOND", "2.0"))
        start_load_generator(tps)
        logger.info(f"Auto-started load generator at {tps} TPS")
    
    # Run Flask API
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, threaded=True)
