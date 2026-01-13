#!/bin/bash
# Run the production-scale distributed transaction experiment

set -e

EXPERIMENT_PATH=${1:-/experiments/production-scale/production-scale-distributed-transaction-experiment.json}

echo "=========================================="
echo "Running Production-Scale Chaos Experiment"
echo "=========================================="
echo ""
echo "Experiment: $EXPERIMENT_PATH"
echo ""

# Check if experiment file exists
if [ ! -f "$EXPERIMENT_PATH" ]; then
    echo "❌ Error: Experiment file not found: $EXPERIMENT_PATH"
    exit 1
fi

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

# Run the experiment
echo "Starting chaos experiment..."
echo ""

chaos run "$EXPERIMENT_PATH" --verbose

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Experiment completed successfully!"
else
    echo "❌ Experiment completed with errors (exit code: $EXIT_CODE)"
fi
echo "=========================================="
echo ""
echo "View results in:"
echo "  - Grafana: http://localhost:3000"
echo "  - Tempo: http://localhost:3200"
echo "  - Prometheus: http://localhost:9090"
echo ""

exit $EXIT_CODE
