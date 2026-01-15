#!/bin/bash
set -e

# Script to run the enhanced multi-hop transaction validation experiment
# Assumes services are already running via docker-compose
# Usage: ./scripts/run-experiment.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$SCRIPT_DIR")"
EXPERIMENTS_DIR="$(dirname "$DEMO_DIR")/chaostooling-experiments"

echo "=========================================="
echo "Running Enhanced Multi-Hop Transaction Validation Experiment"
echo "=========================================="
echo ""

cd "$EXPERIMENTS_DIR/production-scale"

# Set up environment variables
if [ -f "enhanced-multi-hop-transaction-validation-experiment.env.example" ]; then
    echo "Loading environment variables from example file..."
    set -a
    source enhanced-multi-hop-transaction-validation-experiment.env.example
    set +a
fi

# Override with defaults if not set
export SITE_A_HAPROXY_URL="${SITE_A_HAPROXY_URL:-http://haproxy-site-a:80}"
export SITE_A_PAYMENT_SERVICE_URL="${SITE_A_PAYMENT_SERVICE_URL:-http://payment-service-site-a:5000}"
export SITE_A_ORDER_SERVICE_URL="${SITE_A_ORDER_SERVICE_URL:-http://order-service-site-a:5000}"
export SITE_A_INVENTORY_SERVICE_URL="${SITE_A_INVENTORY_SERVICE_URL:-http://inventory-service-site-a:5000}"
export POSTGRES_PRIMARY_HOST="${POSTGRES_PRIMARY_HOST:-postgres-primary-site-a}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-testdb}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
export MYSQL_HOST="${MYSQL_HOST:-mysql}"
export MYSQL_PORT="${MYSQL_PORT:-3306}"
export MYSQL_DB="${MYSQL_DB:-testdb}"
export MYSQL_USER="${MYSQL_USER:-root}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-mysql}"
export MONGODB_URI="${MONGODB_URI:-mongodb://mongodb:27017}"
export MONGODB_DB="${MONGODB_DB:-test}"
export REDIS_HOST="${REDIS_HOST:-redis}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
export RABBITMQ_HOST="${RABBITMQ_HOST:-rabbitmq}"
export RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"
export RABBITMQ_USER="${RABBITMQ_USER:-chaos}"
export RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-password}"
export TEST_NUM_TRANSACTIONS="${TEST_NUM_TRANSACTIONS:-10}"
export TEST_VALIDATION_DELAY_S="${TEST_VALIDATION_DELAY_S:-5}"
export TEST_ASYNC_WAIT_S="${TEST_ASYNC_WAIT_S:-10}"
export TEST_TRANSACTION_TIMEOUT_S="${TEST_TRANSACTION_TIMEOUT_S:-30}"
export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-enhanced-multi-hop-transaction-validation}"

echo "Configuration:"
echo "  Transactions to execute: $TEST_NUM_TRANSACTIONS"
echo "  Validation delay: ${TEST_VALIDATION_DELAY_S}s"
echo "  Async wait time: ${TEST_ASYNC_WAIT_S}s"
echo "  Transaction timeout: ${TEST_TRANSACTION_TIMEOUT_S}s"
echo ""

# Determine Docker command (with or without sudo)
DOCKER_CMD="docker"
if ! docker ps > /dev/null 2>&1; then
    if sudo docker ps > /dev/null 2>&1; then
        DOCKER_CMD="sudo docker"
    else
        echo "ERROR: Cannot access Docker. Please ensure Docker is running."
        exit 1
    fi
fi

# Check if chaos-runner container is running
if ! $DOCKER_CMD ps --format "{{.Names}}" | grep -q "^chaostooling-demo-chaos-runner-1$"; then
    echo "Starting chaos-runner container..."
    cd "$DEMO_DIR"
    DOCKER_COMPOSE_CMD="docker-compose"
    if ! docker-compose ps > /dev/null 2>&1; then
        if sudo docker-compose ps > /dev/null 2>&1; then
            DOCKER_COMPOSE_CMD="sudo docker-compose"
        fi
    fi
    $DOCKER_COMPOSE_CMD up -d chaos-runner
    echo "Waiting for chaos-runner to be ready..."
    sleep 10
    cd "$EXPERIMENTS_DIR/production-scale"
fi

EXPERIMENT_FILE="enhanced-multi-hop-transaction-validation-experiment.json"
EXPERIMENT_PATH="/experiments/production-scale/$EXPERIMENT_FILE"

# Verify experiment file exists
if ! $DOCKER_CMD exec chaostooling-demo-chaos-runner-1 test -f "$EXPERIMENT_PATH" 2>/dev/null; then
    echo "ERROR: Experiment file not found in container: $EXPERIMENT_PATH"
    exit 1
fi

echo "Starting experiment in chaos-runner container..."
echo ""

# Build environment variable string for docker exec
ENV_VARS=""
for var in SITE_A_HAPROXY_URL SITE_A_PAYMENT_SERVICE_URL SITE_A_ORDER_SERVICE_URL \
           SITE_A_INVENTORY_SERVICE_URL POSTGRES_PRIMARY_HOST POSTGRES_PORT POSTGRES_DB \
           POSTGRES_USER POSTGRES_PASSWORD MYSQL_HOST MYSQL_PORT MYSQL_DB MYSQL_USER \
           MYSQL_PASSWORD MONGODB_URI MONGODB_DB REDIS_HOST REDIS_PORT \
           KAFKA_BOOTSTRAP_SERVERS RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USER \
           RABBITMQ_PASSWORD TEST_NUM_TRANSACTIONS TEST_VALIDATION_DELAY_S \
           TEST_ASYNC_WAIT_S TEST_TRANSACTION_TIMEOUT_S OTEL_SERVICE_NAME; do
    if [ -n "${!var}" ]; then
        # Escape quotes and special characters
        val="${!var}"
        val="${val//\"/\\\"}"
        ENV_VARS="${ENV_VARS}export $var=\"$val\"; "
    fi
done

# Run the experiment in the container
$DOCKER_CMD exec -i chaostooling-demo-chaos-runner-1 bash -c "$ENV_VARS cd /experiments/production-scale && chaos run $EXPERIMENT_FILE" 2>&1 | tee /tmp/chaos-experiment-output.log

EXPERIMENT_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
if [ $EXPERIMENT_EXIT_CODE -eq 0 ]; then
    echo "✓ Experiment completed successfully!"
else
    echo "✗ Experiment completed with errors (exit code: $EXPERIMENT_EXIT_CODE)"
fi
echo "=========================================="
echo ""
echo "View results in Grafana:"
echo "  Dashboard: http://localhost:3000/d/enhanced-multi-hop-transaction"
echo ""
echo "Experiment log saved to: /tmp/chaos-experiment-output.log"
echo ""

exit $EXPERIMENT_EXIT_CODE
