#!/bin/bash
# Initialize Redis data structures for production-scale demo

set -e

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

echo "Waiting for Redis to be ready..."
until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping 2>/dev/null | grep -q PONG; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done

echo "Redis is ready - initializing data structures..."

# Create some initial keys for testing
redis-cli -h $REDIS_HOST -p $REDIS_PORT << EOF
-- Set initial cache keys
SET cache:user:1 "{\"id\":1,\"name\":\"test\"}" EX 3600
SET cache:user:2 "{\"id\":2,\"name\":\"test2\"}" EX 3600

-- Create sets for tracking
SADD chaos:active:users 1 2 3
SADD chaos:active:orders 100 101 102

-- Create sorted sets for leaderboards
ZADD chaos:leaderboard 100 "user1" 200 "user2" 150 "user3"

-- Create lists for queues
LPUSH chaos:queue:notifications "{\"type\":\"welcome\",\"user\":1}"
LPUSH chaos:queue:notifications "{\"type\":\"welcome\",\"user\":2}"
EOF

echo "Redis data structures initialized successfully!"
