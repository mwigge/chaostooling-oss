#!/bin/bash
# Entrypoint script for chaos-runner to ensure logs are written to the correct location

# Ensure log directory exists and is writable
mkdir -p /var/log/chaostoolkit
chmod 777 /var/log/chaostoolkit

# Change to log directory so Chaos Toolkit writes logs there
cd /var/log/chaostoolkit

# Run setup-extensions.sh from the mounted volume to ensure latest version and PYTHONPATH
SETUP_SCRIPT="/chaostooling-oss/chaostooling-demo/scripts/setup-extensions.sh"
if [ -f "$SETUP_SCRIPT" ]; then
    echo "Running extension setup from $SETUP_SCRIPT..."
    source "$SETUP_SCRIPT"
else
    echo "Warning: $SETUP_SCRIPT not found, falling back to image version..."
    if [ -f /setup-extensions.sh ]; then
        source /setup-extensions.sh
    fi
fi

# Execute the original command (chaos run, bash, etc.)
exec "$@"

