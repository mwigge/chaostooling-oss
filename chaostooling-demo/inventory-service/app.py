import logging
import os

import redis

# Import from chaosotel for auto-instrumentation
from chaosotel import initialize
from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from pymongo import MongoClient

# Setup OpenTelemetry with auto-instrumentation
service_name = os.getenv("OTEL_SERVICE_NAME", "inventory-service")
initialize(
    target_type="service",
    service_name=service_name,
    service_version="1.0.0",
    auto_instrument=True,
    auto_instrument_databases=True,  # Auto-instruments MongoDB, Redis
)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
# No manual instrumentation needed - auto-instrumentation handles MongoDB and Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_mongodb():
    uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
    db_name = os.getenv("MONGODB_DB", "test")
    client = MongoClient(uri)
    return client[db_name]


def get_redis():
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


@app.route("/check", methods=["POST"])
def check_inventory():
    data = request.json
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)

    logger.info(f"Checking inventory: {data}")

    # 1. Check Redis cache
    try:
        redis_client = get_redis()
        cache_key = f"inventory:{item_id}"
        cached_quantity = redis_client.get(cache_key)

        if cached_quantity:
            available = int(cached_quantity) >= quantity
            if available:
                return jsonify({"status": "available", "source": "cache"}), 200
    except Exception as e:
        logger.warning(f"Redis cache check failed: {e}")

    # 2. Check MongoDB
    try:
        db = get_mongodb()
        inventory = db.inventory.find_one({"item_id": item_id})

        if inventory and inventory.get("quantity", 0) >= quantity:
            # Update cache
            try:
                redis_client.set(cache_key, str(inventory["quantity"]), ex=300)
            except Exception:
                pass
            return jsonify({"status": "available", "source": "database"}), 200
        else:
            return (
                jsonify({"status": "unavailable", "reason": "insufficient_stock"}),
                200,
            )
    except Exception as e:
        logger.error(f"MongoDB failed: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/update", methods=["POST"])
def update_inventory():
    data = request.json
    item_id = data.get("item_id")
    quantity = data.get("quantity")

    logger.info(f"Updating inventory: {data}")

    # 1. Update MongoDB
    try:
        db = get_mongodb()
        db.inventory.update_one(
            {"item_id": item_id}, {"$inc": {"quantity": -quantity}}, upsert=True
        )
    except Exception as e:
        logger.error(f"MongoDB failed: {e}")
        return jsonify({"error": "Database error"}), 500

    # 2. Invalidate Redis cache
    try:
        redis_client = get_redis()
        redis_client.delete(f"inventory:{item_id}")
    except Exception as e:
        logger.warning(f"Redis cache invalidation failed: {e}")

    return jsonify({"status": "success"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
