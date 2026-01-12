#!/bin/bash
# Initialize all services for production-scale demo

set -e

echo "=========================================="
echo "Initializing Production-Scale Demo Services"
echo "=========================================="

# Initialize PostgreSQL
if [ -f /scripts/init-production-scale-db.sh ]; then
    echo "[1/2] Initializing PostgreSQL..."
    /scripts/init-production-scale-db.sh
else
    echo "⚠ PostgreSQL init script not found, skipping..."
fi

# Initialize MongoDB
if [ -f /scripts/init-mongodb-inventory.sh ]; then
    echo "[2/2] Initializing MongoDB inventory..."
    /scripts/init-mongodb-inventory.sh
else
    echo "⚠ MongoDB init script not found, skipping..."
fi

echo ""
echo "=========================================="
echo "All services initialized!"
echo "=========================================="

