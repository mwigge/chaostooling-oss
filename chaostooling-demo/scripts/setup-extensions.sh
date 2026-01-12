#!/bin/bash
set -e

# Install extensions from mounted volumes
# These are mounted from sibling directories at runtime

echo "=========================================="
echo "Setting up Chaos Toolkit extensions..."
echo "=========================================="

# Install extensions in dependency order
# Note: We install WITH dependencies (no --no-deps flag) to ensure all required packages are available
if [ -d "/chaostooling-otel" ]; then
    echo "[1/5] Installing chaostooling-otel (chaosotel)..."
    if pip install --no-cache-dir -e /chaostooling-otel; then
        echo "✓ chaostooling-otel installed"
        python -c "import chaosotel; print('  ✓ chaosotel module verified')" || echo "  ⚠ Warning: chaosotel import failed"
    else
        echo "✗ Failed to install chaostooling-otel"
        exit 1
    fi
else
    echo "⚠ /chaostooling-otel not found, skipping..."
fi

# Install active extensions from chaostooling-* mounts
# chaostooling-reporting (install early as it may be used by other extensions)
if [ -d "/chaostooling-reporting" ]; then
    echo "[2/6] Installing chaostooling-reporting..."
    if pip install --no-cache-dir -e /chaostooling-reporting; then
        echo "✓ chaostooling-reporting installed"
        python -c "import chaostooling_reporting; print('  ✓ chaostooling_reporting module verified')" || echo "  ⚠ Warning: chaostooling_reporting import failed"
    else
        echo "✗ Failed to install chaostooling-reporting"
        exit 1
    fi
else
    echo "⚠ /chaostooling-reporting not found, skipping..."
fi

# chaostooling-extension-db depends on chaostooling-otel, so install it first
if [ -d "/chaostooling-extension-db" ]; then
    echo "[3/6] Installing chaostooling-extension-db (with dependencies)..."
    if pip install --no-cache-dir -e /chaostooling-extension-db; then
        echo "✓ chaostooling-extension-db installed"
        echo "  Verifying chaosdb module..."
        if python -c "import chaosdb; print('  ✓ chaosdb imported successfully')"; then
            python -c "from chaosdb.probes.postgres.postgres_connectivity import probe_postgres_connectivity; print('  ✓ postgres_connectivity probe verified')" || echo "  ⚠ Warning: postgres_connectivity probe import failed"
        else
            echo "  ✗ ERROR: chaosdb module not importable!"
            exit 1
        fi
    else
        echo "✗ Failed to install chaostooling-extension-db"
        exit 1
    fi
else
    echo "⚠ /chaostooling-extension-db not found, skipping..."
fi

if [ -d "/chaostooling-extension-compute" ]; then
    echo "[4/6] Installing chaostooling-extension-compute..."
    pip install --no-cache-dir -e /chaostooling-extension-compute && echo "✓ chaostooling-extension-compute installed" || echo "⚠ Warning: chaostooling-extension-compute installation had issues"
fi

if [ -d "/chaostooling-extension-app" ]; then
    echo "[5/6] Installing chaostooling-extension-app..."
    pip install --no-cache-dir -e /chaostooling-extension-app && echo "✓ chaostooling-extension-app installed" || echo "⚠ Warning: chaostooling-extension-app installation had issues"
fi

if [ -d "/chaostooling-extension-network" ]; then
    echo "[6/6] Installing chaostooling-extension-network..."
    pip install --no-cache-dir -e /chaostooling-extension-network && echo "✓ chaostooling-extension-network installed" || echo "⚠ Warning: chaostooling-extension-network installation had issues"
fi

echo "=========================================="
echo "Extension setup complete!"
echo "=========================================="
echo "Installed chaos/otel packages:"
pip list | grep -E "(chaos|otel)" || echo "  (none found)"
echo ""

