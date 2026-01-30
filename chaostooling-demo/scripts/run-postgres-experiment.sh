#!/bin/bash
set -e

# Script to run the MCP-driven PostgreSQL pool exhaustion chaos experiment
# This experiment tests PostgreSQL connection pool resilience
# Assumes services are already running via docker-compose
# Usage: ./scripts/run-postgres-experiment.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$SCRIPT_DIR")"
EXPERIMENTS_DIR="$(dirname "$DEMO_DIR")/chaostooling-experiments"

echo "=========================================="
echo "Running MCP-Driven PostgreSQL Pool Exhaustion Experiment"
echo "=========================================="
echo ""

cd "$EXPERIMENTS_DIR/postgres"

# Set up environment variables
if [ -f "mcp-test-postgres-pool-exhaustion.env.example" ]; then
    echo "Loading environment variables from example file..."
    set -a
    source mcp-test-postgres-pool-exhaustion.env.example
    set +a
fi

# Override with defaults if not set
export POSTGRES_HOST="${POSTGRES_HOST:-postgres-primary-site-a}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-testdb}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
export POSTGRES_MAX_CONNECTIONS="${POSTGRES_MAX_CONNECTIONS:-100}"
export PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
export LOKI_URL="${LOKI_URL:-http://loki:3100}"
export TEMPO_URL="${TEMPO_URL:-http://tempo:3200}"
export GRAFANA_URL="${GRAFANA_URL:-http://grafana:3000}"
export CHAOS_DB_HOST="${CHAOS_DB_HOST:-chaos-platform-db}"
export CHAOS_DB_PORT="${CHAOS_DB_PORT:-5432}"
export CHAOS_DB_NAME="${CHAOS_DB_NAME:-chaos_platform}"
export CHAOS_DB_USER="${CHAOS_DB_USER:-chaos_user}"
export CHAOS_DB_PASSWORD="${CHAOS_DB_PASSWORD:-chaos_password}"
export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-mcp-postgres-pool-exhaustion}"

echo "Configuration:"
echo "  PostgreSQL Host: $POSTGRES_HOST"
echo "  PostgreSQL Port: $POSTGRES_PORT"
echo "  PostgreSQL Database: $POSTGRES_DB"
echo "  Prometheus URL: $PROMETHEUS_URL"
echo "  Grafana URL: $GRAFANA_URL"
echo "  Loki URL: $LOKI_URL"
echo "  Tempo URL: $TEMPO_URL"
echo "  Chaos Platform DB: $CHAOS_DB_HOST:$CHAOS_DB_PORT/$CHAOS_DB_NAME"
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
    cd "$EXPERIMENTS_DIR/postgres"
fi

EXPERIMENT_FILE="mcp-test-postgres-pool-exhaustion.json"
EXPERIMENT_PATH="/experiments/postgres/$EXPERIMENT_FILE"

# Verify experiment file exists
if ! $DOCKER_CMD exec chaostooling-demo-chaos-runner-1 test -f "$EXPERIMENT_PATH" 2>/dev/null; then
    echo "ERROR: Experiment file not found in container: $EXPERIMENT_PATH"
    exit 1
fi

echo "Starting experiment in chaos-runner container..."
echo ""

# Build environment variable string for docker exec
ENV_VARS=""
for var in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD \
           POSTGRES_MAX_CONNECTIONS PROMETHEUS_URL GRAFANA_URL LOKI_URL TEMPO_URL \
           CHAOS_DB_HOST CHAOS_DB_PORT CHAOS_DB_NAME CHAOS_DB_USER CHAOS_DB_PASSWORD \
           OTEL_SERVICE_NAME OTEL_EXPORTER_OTLP_ENDPOINT OTEL_EXPORTER_OTLP_METRICS_ENDPOINT \
           OTEL_EXPORTER_OTLP_LOGS_ENDPOINT; do
    if [ -n "${!var}" ]; then
        # Escape quotes and special characters
        val="${!var}"
        val="${val//\"/\\\"}"
        ENV_VARS="${ENV_VARS}export $var=\"$val\"; "
    fi
done

# Run the experiment in the container
$DOCKER_CMD exec -i chaostooling-demo-chaos-runner-1 bash -c "$ENV_VARS cd /experiments/postgres && chaos run $EXPERIMENT_FILE" 2>&1 | tee /tmp/postgres-chaos-experiment-output.log

EXPERIMENT_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
if [ $EXPERIMENT_EXIT_CODE -eq 0 ]; then
    echo "[OK] Experiment completed successfully!"
else
    echo "[FAILED] Experiment completed with errors (exit code: $EXPERIMENT_EXIT_CODE)"
fi
echo "=========================================="
echo ""
echo "View results in Grafana:"
echo "  URL: http://localhost:3000"
echo "  Look for PostgreSQL dashboards"
echo ""
echo "Experiment log saved to: /tmp/postgres-chaos-experiment-output.log"
echo ""

exit $EXPERIMENT_EXIT_CODE
