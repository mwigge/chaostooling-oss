#!/bin/bash
# Test script to verify database storage integration
# Runs a simple postgres pool exhaustion experiment and checks database records

set -e

echo "[TEST] Database Storage Integration for Chaos Toolkit"
echo "======================================================="
echo ""

# Configuration
EXPERIMENT_FILE="/home/morgan/dev/src/chaostooling-oss/chaostooling-experiments/postgres/mcp-test-postgres-pool-exhaustion.json"
DEMO_DIR="/home/morgan/dev/src/chaostooling-oss/chaostooling-demo"
CHAOS_DB_HOST="${CHAOS_DB_HOST:-chaos-platform-db}"
CHAOS_DB_PORT="${CHAOS_DB_PORT:-5432}"
GRAFANA_URL="${GRAFANA_URL:-http://grafana:3000}"

# Check if services are running
echo "[INFO] Checking required services..."
docker ps | grep -q chaos_platform_db || (echo "[ERROR] PostgreSQL not running"; exit 1)
docker ps | grep -q chaos-runner || (echo "[ERROR] chaos-runner not running"; exit 1)
docker ps | grep -q grafana || (echo "[ERROR] Grafana not running"; exit 1)
echo "[OK] All services running"
echo ""

# Get baseline experiment count
echo "[INFO] Checking baseline experiment count in database..."
BASELINE_COUNT=$(docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -t -c "SELECT COUNT(*) FROM experiment_runs;" 2>/dev/null || echo "0")
echo "[INFO] Current experiment count: $BASELINE_COUNT"
echo ""

# Run experiment
echo "[INFO] Running experiment with database storage enabled..."
echo "[INFO] Experiment: $EXPERIMENT_FILE"
docker-compose -f "$DEMO_DIR/docker-compose.yml" exec -e CHAOS_DB_HOST="$CHAOS_DB_HOST" \
  -e CHAOS_DB_PORT="$CHAOS_DB_PORT" \
  -e GRAFANA_URL="$GRAFANA_URL" \
  -T chaos-runner chaos run "$EXPERIMENT_FILE" 2>&1 | tail -50

echo ""
echo "[INFO] Waiting for experiment to complete..."
sleep 3

# Check if new experiment record was created
echo "[INFO] Verifying database records..."
NEW_COUNT=$(docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -t -c "SELECT COUNT(*) FROM experiment_runs;" 2>/dev/null || echo "0")

if [ "$NEW_COUNT" -gt "$BASELINE_COUNT" ]; then
  echo "[OK] New experiment record created!"
  echo "[OK] Experiment count: $BASELINE_COUNT → $NEW_COUNT"
  
  # Get details of the latest experiment
  echo ""
  echo "[INFO] Latest Experiment Details:"
  docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -c \
    "SELECT run_id, title, status, started_at, ended_at FROM experiment_runs ORDER BY run_id DESC LIMIT 1;" 
  
  # Check metric snapshots
  echo ""
  echo "[INFO] Checking Metric Snapshots:"
  LATEST_RUN_ID=$(docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -t -c "SELECT MAX(run_id) FROM experiment_runs;")
  SNAPSHOT_COUNT=$(docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -t -c "SELECT COUNT(*) FROM metric_snapshots WHERE run_id = $LATEST_RUN_ID;")
  
  if [ "$SNAPSHOT_COUNT" -gt "0" ]; then
    echo "[OK] $SNAPSHOT_COUNT metric snapshots stored for run_id=$LATEST_RUN_ID"
    
    # Show snapshot details
    docker exec chaos-platform-db psql -U chaos_user -d chaos_platform -c \
      "SELECT snapshot_id, service_name, phase, captured_at FROM metric_snapshots WHERE run_id = $LATEST_RUN_ID ORDER BY captured_at;"
  else
    echo "[WARNING] No metric snapshots found. Verify metrics collector is using run_id parameter."
  fi
  
  echo ""
  echo "[SUCCESS] Database storage integration test PASSED!"
  exit 0
else
  echo "[FAIL] No new experiment record created. Database storage may not be working."
  echo ""
  echo "[DEBUG] Checking chaos-runner logs..."
  docker-compose -f "$DEMO_DIR/docker-compose.yml" logs chaos-runner | tail -100
  exit 1
fi
