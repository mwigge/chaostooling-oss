#!/bin/bash
# Cleanup script to stop and remove existing containers that might be using conflicting ports

echo "Stopping all containers..."
docker compose down

echo "Removing containers with postgres in the name..."
docker ps -a --filter "name=postgres" --format "{{.ID}}" | xargs -r docker rm -f

echo "Checking for containers using port 5432..."
docker ps -a --format "{{.Names}}\t{{.Ports}}" | grep 5432 || echo "No containers found using port 5432"

echo "Cleanup complete. You can now run 'docker compose up -d'"

