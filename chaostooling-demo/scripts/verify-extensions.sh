#!/bin/bash
# Verify that all extensions are properly installed

echo "=========================================="
echo "Verifying Chaos Toolkit Extensions"
echo "=========================================="

echo ""
echo "1. Checking Python environment..."
python --version
echo ""

echo "2. Checking installed chaos packages..."
pip list | grep -E "(chaos|otel)" || echo "  (none found)"
echo ""

echo "3. Testing chaosdb import..."
if python -c "import chaosdb; print('  ✓ chaosdb imported')"; then
    echo "  ✓ chaosdb module is available"
    
    echo ""
    echo "4. Testing postgres_connectivity probe..."
    if python -c "from chaosdb.probes.postgres.postgres_connectivity import probe_postgres_connectivity; print('  ✓ postgres_connectivity probe imported')"; then
        echo "  ✓ postgres_connectivity probe is available"
    else
        echo "  ✗ ERROR: postgres_connectivity probe cannot be imported"
        echo ""
        echo "  Attempting to reinstall chaostooling-extension-db..."
        if [ -d "/chaostooling-extension-db" ]; then
            pip install --no-cache-dir -e /chaostooling-extension-db
            echo "  Reinstallation complete. Please try again."
        else
            echo "  ✗ ERROR: /chaostooling-extension-db not found"
        fi
    fi
else
    echo "  ✗ ERROR: chaosdb module cannot be imported"
    echo ""
    echo "  Attempting to reinstall chaostooling-extension-db..."
    if [ -d "/chaostooling-extension-db" ]; then
        pip install --no-cache-dir -e /chaostooling-extension-db
        echo "  Reinstallation complete. Please try again."
    else
        echo "  ✗ ERROR: /chaostooling-extension-db not found"
    fi
fi

echo ""
echo "5. Testing chaostooling-reporting import..."
if python -c "import chaostooling_reporting; print('  ✓ chaostooling_reporting imported')"; then
    echo "  ✓ chaostooling_reporting module is available"
else
    echo "  ⚠ Warning: chaostooling_reporting module not found (optional)"
fi

echo ""
echo "6. Testing chaosotel import..."
if python -c "import chaosotel; print('  ✓ chaosotel imported')"; then
    echo "  ✓ chaosotel module is available"
else
    echo "  ✗ ERROR: chaosotel module cannot be imported"
fi

echo ""
echo "=========================================="
echo "Verification complete!"
echo "=========================================="

