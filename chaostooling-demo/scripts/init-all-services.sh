#!/bin/bash
# Initialize all services for production-scale demo

set -e

echo "=========================================="
echo "Initializing Production-Scale Demo Services"
echo "=========================================="

# Initialize PostgreSQL
if [ -f /scripts/init-production-scale-db.sh ]; then
    echo "[1/7] Initializing PostgreSQL..."
    /scripts/init-production-scale-db.sh
else
    echo "⚠ PostgreSQL init script not found, skipping..."
fi

# Initialize MySQL
if [ -f /scripts/init-mysql-db.sh ]; then
    echo "[2/7] Initializing MySQL..."
    /scripts/init-mysql-db.sh
else
    echo "⚠ MySQL init script not found, skipping..."
fi

# Initialize MSSQL
if [ -f /scripts/init-mssql-db.sh ]; then
    echo "[3/7] Initializing MSSQL..."
    /scripts/init-mssql-db.sh
else
    echo "⚠ MSSQL init script not found, skipping..."
fi

# Initialize MongoDB
if [ -f /scripts/init-mongodb-inventory.sh ]; then
    echo "[4/7] Initializing MongoDB inventory..."
    /scripts/init-mongodb-inventory.sh
else
    echo "⚠ MongoDB init script not found, skipping..."
fi

# Initialize Redis
if [ -f /scripts/init-redis-data.sh ]; then
    echo "[5/7] Initializing Redis data structures..."
    /scripts/init-redis-data.sh
else
    echo "⚠ Redis init script not found, skipping..."
fi

# Initialize Cassandra
if [ -f /scripts/init-cassandra-keyspace.sh ]; then
    echo "[6/7] Initializing Cassandra keyspace..."
    /scripts/init-cassandra-keyspace.sh
else
    echo "⚠ Cassandra init script not found, skipping..."
fi

# Initialize ActiveMQ
if [ -f /scripts/init-activemq-queues.sh ]; then
    echo "[7/7] Initializing ActiveMQ queues..."
    /scripts/init-activemq-queues.sh
else
    echo "⚠ ActiveMQ init script not found, skipping..."
fi

echo ""
echo "=========================================="
echo "All services initialized!"
echo "=========================================="
echo ""
echo "Initialized systems:"
echo "  ✅ PostgreSQL (Primary database)"
echo "  ✅ MySQL (Secondary database)"
echo "  ✅ MSSQL (Legacy database)"
echo "  ✅ MongoDB (Document store)"
echo "  ✅ Redis (Cache layer)"
echo "  ✅ Cassandra (Time-series data)"
echo "  ✅ ActiveMQ (Messaging system)"
echo "  ✅ Kafka (Messaging system - auto-configured)"
echo "  ✅ RabbitMQ (Messaging system - auto-configured)"

