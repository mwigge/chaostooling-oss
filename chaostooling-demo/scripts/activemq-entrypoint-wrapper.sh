#!/bin/bash
# Entrypoint wrapper for ActiveMQ to initialize queues after service startup

set -e

# Start ActiveMQ in background
/opt/apache-activemq/bin/activemq console &
ACTIVEMQ_PID=$!

# Wait for ActiveMQ to be ready (with timeout)
echo "Waiting for ActiveMQ to be ready..."
ACTIVEMQ_WEB_PORT=${ACTIVEMQ_WEB_PORT:-8161}
ACTIVEMQ_USER=${ACTIVEMQ_USER:-admin}
ACTIVEMQ_PASSWORD=${ACTIVEMQ_PASSWORD:-admin}

MAX_WAIT=120
WAIT_COUNT=0
until curl -s -u $ACTIVEMQ_USER:$ACTIVEMQ_PASSWORD "http://localhost:$ACTIVEMQ_WEB_PORT/api/jolokia/read/java.lang:type=Runtime" > /dev/null 2>&1; do
  if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "Warning: ActiveMQ did not become ready within ${MAX_WAIT} seconds, continuing anyway..."
    break
  fi
  echo "ActiveMQ is starting up - sleeping (${WAIT_COUNT}/${MAX_WAIT})"
  sleep 3
  WAIT_COUNT=$((WAIT_COUNT + 3))
done

if curl -s -u $ACTIVEMQ_USER:$ACTIVEMQ_PASSWORD "http://localhost:$ACTIVEMQ_WEB_PORT/api/jolokia/read/java.lang:type=Runtime" > /dev/null 2>&1; then
  echo "ActiveMQ is ready - running initialization..."

  # Run initialization script (skip chmod since it's read-only, just run it)
  if [ -f /docker-entrypoint-initdb.d/init-activemq-queues.sh ]; then
    bash /docker-entrypoint-initdb.d/init-activemq-queues.sh || echo "Warning: ActiveMQ initialization script failed (may already be initialized)"
  fi
else
  echo "Warning: ActiveMQ is not fully ready, but continuing..."
fi

# Wait for ActiveMQ process (foreground)
wait $ACTIVEMQ_PID
