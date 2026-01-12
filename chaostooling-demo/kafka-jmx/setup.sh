#!/bin/bash
# Setup script to download JMX Exporter JAR

set -e

JMX_VERSION="0.20.0"
JMX_JAR="jmx_prometheus_javaagent-${JMX_VERSION}.jar"
JMX_URL="https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/${JMX_VERSION}/${JMX_JAR}"

echo "Downloading JMX Exporter ${JMX_VERSION}..."

# Create directory if it doesn't exist
mkdir -p "$(dirname "$0")"

# Download the JAR file
curl -L -o "$(dirname "$0")/jmx_prometheus_javaagent.jar" "$JMX_URL"

echo "✓ Downloaded JMX Exporter to $(dirname "$0")/jmx_prometheus_javaagent.jar"
echo ""
echo "Next steps:"
echo "1. Restart Kafka: docker-compose restart kafka"
echo "2. Verify metrics: curl http://localhost:9999/metrics"
echo "3. Check Prometheus: http://localhost:9090/targets"

