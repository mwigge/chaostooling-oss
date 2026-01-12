#!/bin/bash
# Quick fix script to reinstall extensions if import fails

echo "Reinstalling chaostooling-extension-db..."

if [ -d "/chaostooling-extension-db" ]; then
    pip install --no-cache-dir -e /chaostooling-extension-db
    echo "✓ Reinstalled chaostooling-extension-db"
    
    echo ""
    echo "Verifying installation..."
    python -c "from chaosdb.probes.postgres.postgres_connectivity import probe_postgres_connectivity; print('✓ postgres_connectivity probe is now available')" || echo "✗ Still having issues"
else
    echo "✗ ERROR: /chaostooling-extension-db not found"
fi

