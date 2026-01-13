#!/bin/bash
# Entrypoint wrapper for Redis to initialize data structures after service startup

set -e

# Start Redis in background
redis-server --daemonize yes

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until redis-cli ping 2>/dev/null | grep -q PONG; do
  echo "Redis is starting up - sleeping"
  sleep 1
done

echo "Redis is ready - running initialization..."

# Run initialization script (skip chmod since it's read-only, just run it)
if [ -f /docker-entrypoint-initdb.d/init-redis-data.sh ]; then
  bash /docker-entrypoint-initdb.d/init-redis-data.sh || echo "Warning: Redis initialization script failed (may already be initialized)"
fi

# Stop the daemonized Redis
redis-cli shutdown

# Keep Redis running in foreground
exec redis-server
