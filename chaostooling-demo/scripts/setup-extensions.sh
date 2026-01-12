#!/bin/bash
set -e

# Install extensions from mounted volumes
# These are mounted from sibling directories at runtime

echo "=========================================="
echo "Setting up Chaos Toolkit extensions..."
echo "=========================================="

# Install monorepo root extensions
echo "Installing chaostooling-oss monorepo..."
if pip install --no-cache-dir -e /chaostooling-oss; then
    echo "✓ chaostooling-oss installed successfully"
else
    echo "✗ Failed to install chaostooling-oss"
    exit 1
fi

echo "=========================================="
echo "Extension setup complete!"
echo "=========================================="
echo "Installed chaos/otel packages:"
pip list | grep -E "(chaos|otel)" || echo "  (none found)"
echo ""

