#!/bin/bash
set -e

# This script runs on replica initialization
# The actual replication setup is done via pg_basebackup in docker-compose command
echo "Replica initialization script - replication setup handled by pg_basebackup"

