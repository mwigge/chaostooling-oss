#!/bin/bash
# Helper script to run chaos experiments with proper environment setup
# This ensures all extensions are properly installed and PYTHONPATH is set

# Set up extensions
if [ -f "/chaostooling-oss/chaostooling-demo/scripts/setup-extensions.sh" ]; then
    source /chaostooling-oss/chaostooling-demo/scripts/setup-extensions.sh
elif [ -f "/setup-extensions.sh" ]; then
    source /setup-extensions.sh
fi

# Source PYTHONPATH if set
if [ -f /etc/profile.d/chaostooling-pythonpath.sh ]; then
    source /etc/profile.d/chaostooling-pythonpath.sh
fi

# Export for subprocesses
export PYTHONPATH

# Run the chaos command with all arguments
exec chaos "$@"
