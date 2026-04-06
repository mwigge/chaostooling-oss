#!/bin/bash
set -e

# Enable pg_stat_statements extension for query tracking
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

    -- Grant monitoring permissions
    GRANT pg_monitor TO $POSTGRES_USER;
EOSQL

echo "pg_stat_statements extension enabled"

# Create replication user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'changeme';
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO replicator;
EOSQL

# Create tables (merged from all initialization scripts)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Mobile purchases table (supports both VARCHAR and INTEGER user_id for compatibility)
    CREATE TABLE IF NOT EXISTS mobile_purchases (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        amount DECIMAL(10, 2) NOT NULL,
        item_id VARCHAR(255) NOT NULL,
        order_id INTEGER,
        status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_mobile_purchases_user_id ON mobile_purchases(user_id);
    CREATE INDEX IF NOT EXISTS idx_mobile_purchases_created_at ON mobile_purchases(created_at);
    CREATE INDEX IF NOT EXISTS idx_mobile_purchases_order_id ON mobile_purchases(order_id);

    -- Orders table
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        item_id VARCHAR(100) NOT NULL,
        quantity INTEGER NOT NULL,
        status VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_orders_item_id ON orders(item_id);

    -- Payments table
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
    CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

    -- Notifications table
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        type VARCHAR(50) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, type, message, created_at)
    );

    CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
    CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
EOSQL

echo "Primary database initialized"


# Allow replication connections
echo "host replication replicator 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"

