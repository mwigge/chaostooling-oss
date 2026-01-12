-- Setup script for Postgres Chaos Experiments
-- This creates the test schema and seeds data for all experiments

-- Drop and recreate table
DROP TABLE IF EXISTS mobile_purchases CASCADE;

CREATE TABLE mobile_purchases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_mobile_purchases_user_id ON mobile_purchases(user_id);
CREATE INDEX idx_mobile_purchases_created_at ON mobile_purchases(created_at);
CREATE INDEX idx_mobile_purchases_status ON mobile_purchases(status);

-- Seed initial data (10,000 rows for testing)
INSERT INTO mobile_purchases (user_id, product_id, amount, status, created_at)
SELECT 
    (random() * 1000)::INTEGER as user_id,
    (random() * 100)::INTEGER as product_id,
    (random() * 1000)::DECIMAL(10,2) as amount,
    CASE (random() * 3)::INTEGER
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'completed'
        WHEN 2 THEN 'failed'
        ELSE 'cancelled'
    END as status,
    NOW() - (random() * INTERVAL '30 days') as created_at
FROM generate_series(1, 10000);

-- Create test user for lock storm scenarios
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'test_user') THEN
        CREATE USER test_user WITH PASSWORD 'test_password';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON TABLE mobile_purchases TO test_user;
GRANT USAGE, SELECT ON SEQUENCE mobile_purchases_id_seq TO test_user;

-- Analyze table for proper query planning
ANALYZE mobile_purchases;

-- Display summary
SELECT 
    'Setup Complete' as status,
    COUNT(*) as total_rows,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT status) as unique_statuses
FROM mobile_purchases;
