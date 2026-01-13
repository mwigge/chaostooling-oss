#!/bin/bash
# Entrypoint wrapper for MSSQL to initialize database after service startup

set -e

# Start MSSQL in background
exec /opt/mssql/bin/sqlservr &
MSSQL_PID=$!

# Wait for MSSQL to be ready
echo "Waiting for MSSQL to be ready..."
until /opt/mssql-tools/bin/sqlcmd -S localhost,1433 -U sa -P "${MSSQL_SA_PASSWORD}" -Q "SELECT 1" 2>/dev/null; do
  echo "MSSQL is starting up - sleeping"
  sleep 2
done

echo "MSSQL is ready - running initialization..."

# Run initialization script in background (non-blocking)
if [ -f /docker-entrypoint-initdb.d/init-mssql-db.sh ]; then
  chmod +x /docker-entrypoint-initdb.d/init-mssql-db.sh
  /docker-entrypoint-initdb.d/init-mssql-db.sh || echo "Warning: MSSQL initialization script failed (may already be initialized)"
fi

# Wait for MSSQL process (foreground)
wait $MSSQL_PID
