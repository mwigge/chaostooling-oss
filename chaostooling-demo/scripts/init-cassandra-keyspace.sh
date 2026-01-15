#!/bin/bash
# Initialize Cassandra keyspace for production-scale demo

set -e

CASSANDRA_HOST=${CASSANDRA_HOST:-localhost}
CASSANDRA_PORT=${CASSANDRA_PORT:-9042}

echo "Waiting for Cassandra to be ready..."
until cqlsh $CASSANDRA_HOST $CASSANDRA_PORT -e "DESCRIBE KEYSPACES" 2>/dev/null; do
  echo "Cassandra is unavailable - sleeping"
  sleep 2
done

echo "Cassandra is ready - initializing keyspace and tables..."

cqlsh $CASSANDRA_HOST $CASSANDRA_PORT << EOF
-- Create keyspace if not exists
CREATE KEYSPACE IF NOT EXISTS testdb
WITH REPLICATION = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
};

USE testdb;

-- Create mobile_purchases table
CREATE TABLE IF NOT EXISTS mobile_purchases (
    id UUID PRIMARY KEY,
    user_id INT,
    amount DECIMAL,
    item_id TEXT,
    order_id INT,
    status TEXT,
    created_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ON mobile_purchases (user_id);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY,
    user_id INT,
    item_id TEXT,
    quantity INT,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ON orders (user_id);

-- Create payments table
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY,
    user_id INT,
    amount DECIMAL,
    status TEXT,
    created_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ON payments (user_id);
EOF

echo "Cassandra keyspace and tables initialized successfully!"
