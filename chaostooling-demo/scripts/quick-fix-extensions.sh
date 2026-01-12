#!/bin/bash
# Quick fix to reinstall extensions if they're missing

echo "Reinstalling Chaos Toolkit extensions..."

# Install chaostooling-otel
if [ -d "/chaostooling-otel" ]; then
    echo "[1/3] Installing chaostooling-otel..."
    pip install --no-cache-dir -e /chaostooling-otel
fi

# Install chaostooling-reporting
if [ -d "/chaostooling-reporting" ]; then
    echo "[2/3] Installing chaostooling-reporting..."
    pip install --no-cache-dir -e /chaostooling-reporting
fi

# Install chaostooling-extension-db
if [ -d "/chaostooling-extension-db" ]; then
    echo "[3/3] Installing chaostooling-extension-db..."
    pip install --no-cache-dir -e /chaostooling-extension-db
    
    # Verify
    python -c "from chaosdb.probes.postgres.postgres_connectivity import probe_postgres_connectivity; print('✓ Extension verified')" || echo "✗ Verification failed"
fi

echo "Done!"

