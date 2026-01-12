#!/bin/bash
set -e

# Setup script for Postgres Chaos Experiments
# This script initializes the test database on both primary and replica

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default configuration
POSTGRES_HOST="${POSTGRES_HOST:-postgres-primary}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-testdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

echo "========================================="
echo "Postgres Test Database Setup"
echo "========================================="
echo "Host: $POSTGRES_HOST"
echo "Port: $POSTGRES_PORT"
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo "========================================="

# Wait for Postgres to be ready
echo "Waiting for Postgres to be ready..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c '\q' 2>/dev/null; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "Postgres is ready!"

# Run setup SQL
echo "Running setup SQL script..."
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -f "$SCRIPT_DIR/setup_postgres_test_db.sql"

echo "========================================="
echo "Setup complete!"
echo "========================================="
