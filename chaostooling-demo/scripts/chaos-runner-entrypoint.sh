#!/bin/bash
# Entrypoint script for chaos-runner to ensure logs are written to the correct location

# Ensure log directory exists and is writable
mkdir -p /var/log/chaostoolkit
chmod 777 /var/log/chaostoolkit

# Change to log directory so Chaos Toolkit writes logs there
cd /var/log/chaostoolkit

# Run setup-extensions.sh first (from original entrypoint)
# Source the script to preserve PYTHONPATH
if [ -f /setup-extensions.sh ]; then
    source /setup-extensions.sh || /setup-extensions.sh
    # Also source the PYTHONPATH file if it exists
    if [ -f /etc/profile.d/chaostooling-pythonpath.sh ]; then
        source /etc/profile.d/chaostooling-pythonpath.sh
    fi
fi

# Execute the original command (chaos run, bash, etc.)
exec "$@"

