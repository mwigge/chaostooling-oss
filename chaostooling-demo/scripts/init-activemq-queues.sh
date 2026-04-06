#!/bin/bash
# Initialize ActiveMQ queues for production-scale demo

set -e

ACTIVEMQ_HOST=${ACTIVEMQ_HOST:-activemq}
ACTIVEMQ_PORT=${ACTIVEMQ_PORT:-61616}
ACTIVEMQ_WEB_PORT=${ACTIVEMQ_WEB_PORT:-8161}
ACTIVEMQ_USER=${ACTIVEMQ_USER:-admin}
ACTIVEMQ_PASSWORD=${ACTIVEMQ_PASSWORD:-changeme}

echo "Waiting for ActiveMQ to be ready..."
until curl -s -u $ACTIVEMQ_USER:$ACTIVEMQ_PASSWORD "http://$ACTIVEMQ_HOST:$ACTIVEMQ_WEB_PORT/api/jolokia/read/java.lang:type=Runtime" > /dev/null 2>&1; do
  echo "ActiveMQ is unavailable - sleeping"
  sleep 2
done

echo "ActiveMQ is ready - initializing queues..."

# Create queues using ActiveMQ REST API
curl -s -u $ACTIVEMQ_USER:$ACTIVEMQ_PASSWORD \
  -X POST \
  "http://$ACTIVEMQ_HOST:$ACTIVEMQ_WEB_PORT/api/message/chaos.test?type=queue" \
  -H "Content-Type: application/json" \
  -d '{"body":"init"}' > /dev/null 2>&1 || true

curl -s -u $ACTIVEMQ_USER:$ACTIVEMQ_PASSWORD \
  -X POST \
  "http://$ACTIVEMQ_HOST:$ACTIVEMQ_WEB_PORT/api/message/chaos.events?type=queue" \
  -H "Content-Type: application/json" \
  -d '{"body":"init"}' > /dev/null 2>&1 || true

echo "ActiveMQ queues initialized successfully!"
echo "Queues created: chaos.test, chaos.events"
