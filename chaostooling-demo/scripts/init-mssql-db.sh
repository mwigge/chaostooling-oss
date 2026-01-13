#!/bin/bash
# Initialize MSSQL database for production-scale demo

set -e

MSSQL_HOST=${MSSQL_HOST:-mssql}
MSSQL_PORT=${MSSQL_PORT:-1433}
MSSQL_DB=${POSTGRES_DB:-testdb}
MSSQL_USER=${MSSQL_USER:-sa}
MSSQL_PASSWORD=${MSSQL_PASSWORD:-Password123!}

echo "Waiting for MSSQL to be ready..."
until /opt/mssql-tools/bin/sqlcmd -S $MSSQL_HOST,$MSSQL_PORT -U $MSSQL_USER -P $MSSQL_PASSWORD -Q "SELECT 1" 2>/dev/null; do
  echo "MSSQL is unavailable - sleeping"
  sleep 2
done

echo "MSSQL is ready - initializing database and tables..."

/opt/mssql-tools/bin/sqlcmd -S $MSSQL_HOST,$MSSQL_PORT -U $MSSQL_USER -P $MSSQL_PASSWORD << EOF
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '$MSSQL_DB')
BEGIN
    CREATE DATABASE $MSSQL_DB;
END
GO

USE $MSSQL_DB;
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[mobile_purchases]') AND type in (N'U'))
BEGIN
    CREATE TABLE mobile_purchases (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        item_id VARCHAR(100) NOT NULL,
        order_id INT,
        status VARCHAR(50) NOT NULL,
        created_at DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX idx_user_id ON mobile_purchases(user_id);
END
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[orders]') AND type in (N'U'))
BEGIN
    CREATE TABLE orders (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        item_id VARCHAR(100) NOT NULL,
        quantity INT NOT NULL,
        status VARCHAR(50) NOT NULL,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX idx_user_id ON orders(user_id);
END
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[payments]') AND type in (N'U'))
BEGIN
    CREATE TABLE payments (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(50) NOT NULL,
        created_at DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX idx_user_id ON payments(user_id);
END
GO
EOF

echo "MSSQL database and tables initialized successfully!"
