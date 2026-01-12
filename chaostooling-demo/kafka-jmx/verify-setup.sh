#!/bin/bash
# Verify Kafka JMX Exporter setup

echo "=== Verifying Kafka JMX Exporter Setup ==="
echo ""

echo "1. Checking if JAR file exists..."
if [ -f "jmx_prometheus_javaagent.jar" ]; then
    SIZE=$(stat -f%z jmx_prometheus_javaagent.jar 2>/dev/null || stat -c%s jmx_prometheus_javaagent.jar 2>/dev/null || echo "0")
    echo "   ✅ JAR file exists (size: $SIZE bytes)"
    if [ "$SIZE" -lt 100000 ]; then
        echo "   ⚠️  WARNING: JAR file seems too small, might be corrupted"
    fi
else
    echo "   ❌ JAR file NOT found!"
    exit 1
fi

echo ""
echo "2. Checking if config file exists..."
if [ -f "kafka-jmx-config.yml" ]; then
    echo "   ✅ Config file exists"
else
    echo "   ❌ Config file NOT found!"
    exit 1
fi

echo ""
echo "3. Checking Kafka container..."
cd ..
docker-compose ps kafka | grep -q "Up" && echo "   ✅ Kafka container is running" || echo "   ❌ Kafka container is NOT running"

echo ""
echo "4. Checking if files are mounted in container..."
echo "   Checking JAR file:"
docker-compose exec -T kafka ls -la /opt/jmx_prometheus_javaagent.jar 2>/dev/null && echo "   ✅ JAR file is mounted" || echo "   ❌ JAR file NOT found in container"

echo "   Checking config file:"
docker-compose exec -T kafka ls -la /opt/kafka-jmx-config.yml 2>/dev/null && echo "   ✅ Config file is mounted" || echo "   ❌ Config file NOT found in container"

echo ""
echo "5. Checking KAFKA_OPTS environment variable..."
docker-compose exec -T kafka env | grep KAFKA_OPTS || echo "   ❌ KAFKA_OPTS not set in container"

echo ""
echo "6. Checking if port 9999 is listening..."
docker-compose exec -T kafka sh -c "netstat -tlnp 2>/dev/null | grep 9999 || ss -tlnp 2>/dev/null | grep 9999 || echo '   Port 9999 not listening'"

echo ""
echo "7. Checking Kafka process for javaagent..."
docker-compose exec -T kafka sh -c "ps aux | grep java | grep javaagent" || echo "   ⚠️  Java agent not found in process list"

echo ""
echo "8. Checking Kafka logs for JMX exporter errors..."
docker-compose logs kafka 2>&1 | tail -50 | grep -i -E "(jmx|javaagent|9999|error)" || echo "   No JMX-related messages in recent logs"

echo ""
echo "=== Diagnostic Complete ==="
echo ""
echo "If the Java agent isn't loading, try:"
echo "  1. Restart Kafka: docker-compose restart kafka"
echo "  2. Check full logs: docker-compose logs kafka | tail -100"
echo "  3. Verify KAFKA_OPTS syntax in docker-compose.yml"

