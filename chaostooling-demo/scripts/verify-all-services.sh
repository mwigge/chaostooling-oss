#!/bin/bash
# Verify all services are ready for production-scale experiment

set -e

echo "=========================================="
echo "Verifying Production-Scale Demo Services"
echo "=========================================="
echo ""

ALL_READY=true

# Check PostgreSQL
echo -n "Checking PostgreSQL... "
if PGPASSWORD=${POSTGRES_PASSWORD:-postgres} psql -h ${POSTGRES_PRIMARY_HOST:-postgres-primary-site-a} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-testdb} -c '\q' 2>/dev/null; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check MySQL
echo -n "Checking MySQL... "
if mysql -h ${MYSQL_HOST:-mysql} -P ${MYSQL_PORT:-3306} -u ${MYSQL_USER:-root} -p${MYSQL_PASSWORD:-mysql} -e 'SELECT 1' 2>/dev/null; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check MSSQL (requires sqlcmd)
echo -n "Checking MSSQL... "
if command -v /opt/mssql-tools/bin/sqlcmd >/dev/null 2>&1; then
    if /opt/mssql-tools/bin/sqlcmd -S ${MSSQL_HOST:-mssql},${MSSQL_PORT:-1433} -U ${MSSQL_USER:-sa} -P ${MSSQL_PASSWORD:-Password123!} -Q "SELECT 1" 2>/dev/null; then
        echo "✅ Ready"
    else
        echo "❌ Not ready"
        ALL_READY=false
    fi
else
    echo "⚠ sqlcmd not available (may need to run from MSSQL container)"
fi

# Check MongoDB
echo -n "Checking MongoDB... "
if mongosh --host ${MONGODB_HOST:-mongodb} --port ${MONGODB_PORT:-27017} --eval "db.adminCommand('ping')" 2>/dev/null | grep -q "ok.*1"; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check Redis
echo -n "Checking Redis... "
if redis-cli -h ${REDIS_HOST:-redis} -p ${REDIS_PORT:-6379} ping 2>/dev/null | grep -q PONG; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check Cassandra
echo -n "Checking Cassandra... "
if cqlsh ${CASSANDRA_HOST:-cassandra} ${CASSANDRA_PORT:-9042} -e "DESCRIBE KEYSPACES" 2>/dev/null; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check Kafka
echo -n "Checking Kafka... "
if kafka-broker-api-versions --bootstrap-server ${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092} 2>/dev/null | grep -q "kafka"; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check RabbitMQ
echo -n "Checking RabbitMQ... "
if curl -s -u ${RABBITMQ_USER:-chaos}:${RABBITMQ_PASSWORD:-password} "http://${RABBITMQ_HOST:-rabbitmq}:${RABBITMQ_MANAGEMENT_PORT:-15672}/api/overview" >/dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

# Check ActiveMQ
echo -n "Checking ActiveMQ... "
if curl -s -u ${ACTIVEMQ_USER:-admin}:${ACTIVEMQ_PASSWORD:-admin} "http://${ACTIVEMQ_HOST:-activemq}:${ACTIVEMQ_WEB_PORT:-8161}/api/jolokia/read/java.lang:type=Runtime" >/dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
    ALL_READY=false
fi

echo ""
echo "=========================================="
if [ "$ALL_READY" = true ]; then
    echo "✅ All services are ready!"
    exit 0
else
    echo "❌ Some services are not ready"
    echo ""
    echo "Run initialization scripts:"
    echo "  /scripts/init-all-services.sh"
    exit 1
fi
echo "=========================================="
