#!/bin/bash
# Entrypoint wrapper for Cassandra to initialize keyspace after service startup

set -e

# Start Cassandra in background (Cassandra 4.1 uses /usr/local/bin/docker-entrypoint.sh or direct cassandra command)
if [ -f /usr/local/bin/docker-entrypoint.sh ]; then
    /usr/local/bin/docker-entrypoint.sh cassandra -f &
elif [ -f /docker-entrypoint.sh ]; then
    /docker-entrypoint.sh cassandra -f &
else
    # Fallback: start cassandra directly
    cassandra -f &
fi
CASSANDRA_PID=$!

# Wait for Cassandra to be ready (with timeout)
echo "Waiting for Cassandra to be ready..."
MAX_WAIT=120
WAIT_COUNT=0
until cqlsh localhost 9042 -e "DESCRIBE KEYSPACES" 2>/dev/null; do
  if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "Warning: Cassandra did not become ready within ${MAX_WAIT} seconds, continuing anyway..."
    break
  fi
  echo "Cassandra is starting up - sleeping (${WAIT_COUNT}/${MAX_WAIT})"
  sleep 2
  WAIT_COUNT=$((WAIT_COUNT + 2))
done

if cqlsh localhost 9042 -e "DESCRIBE KEYSPACES" 2>/dev/null; then
  echo "Cassandra is ready - running initialization..."

  # Run initialization script (skip chmod since it's read-only, just run it)
  if [ -f /docker-entrypoint-initdb.d/init-cassandra-keyspace.sh ]; then
    bash /docker-entrypoint-initdb.d/init-cassandra-keyspace.sh || echo "Warning: Cassandra initialization script failed (may already be initialized)"
  fi
else
  echo "Warning: Cassandra is not fully ready, but continuing..."
fi

# Wait for Cassandra process (foreground)
wait $CASSANDRA_PID
