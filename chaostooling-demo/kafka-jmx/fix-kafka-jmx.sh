#!/bin/bash
# Quick fix script for Kafka JMX Exporter issues

set -e

echo "=== Kafka JMX Exporter Fix Script ==="
echo ""

# Check if JAR exists
if [ ! -f "jmx_prometheus_javaagent.jar" ]; then
    echo "❌ JMX Exporter JAR not found. Downloading..."
    curl -L -o jmx_prometheus_javaagent.jar \
      https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar
    echo "✅ Downloaded JMX Exporter JAR"
else
    echo "✅ JMX Exporter JAR exists"
fi

# Check JAR file size
JAR_SIZE=$(stat -f%z jmx_prometheus_javaagent.jar 2>/dev/null || stat -c%s jmx_prometheus_javaagent.jar 2>/dev/null || echo "0")
if [ "$JAR_SIZE" -lt 100000 ]; then
    echo "⚠️  JAR file seems too small ($JAR_SIZE bytes). Re-downloading..."
    rm -f jmx_prometheus_javaagent.jar
    curl -L -o jmx_prometheus_javaagent.jar \
      https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar
    echo "✅ Re-downloaded JMX Exporter JAR"
fi

# Validate config file
if [ ! -f "kafka-jmx-config.yml" ]; then
    echo "❌ Config file not found!"
    exit 1
fi

echo "✅ Config file exists"

# Check if YAML is valid (basic check)
if ! grep -q "^rules:" kafka-jmx-config.yml; then
    echo "⚠️  Config file might be invalid (missing 'rules:' section)"
fi

echo ""
echo "=== Restarting Kafka ==="
echo "Run this command from the chaostooling-wl-demo directory:"
echo "  docker-compose restart kafka"
echo ""
echo "Then verify with:"
echo "  curl http://localhost:9999/metrics | head -20"
echo ""
echo "Check Prometheus targets:"
echo "  http://localhost:9090/targets"

