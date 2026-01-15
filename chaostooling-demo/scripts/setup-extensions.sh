#!/bin/bash
# Setup script for chaostooling extensions
# This script installs all extensions from the mounted /chaostooling-oss volume
# Can be sourced or executed directly

# Don't use set -e when sourcing, as it will exit the parent shell
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly
    set -e
fi

echo "=========================================="
echo "Setting up ChaosTooling Extensions"
echo "=========================================="

# Base directory where extensions are mounted
BASE_DIR="/chaostooling-oss"

# Check if base directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo "Warning: $BASE_DIR not found. Extensions may not be available."
    echo "This is normal if running outside Docker or if volumes are not mounted."
    # Only exit if script is executed directly, not when sourced
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
        exit 0
    fi
    return 0 2>/dev/null || true
fi

# Function to install extension if it has a setup.py or pyproject.toml
install_extension() {
    local ext_dir=$1
    local ext_name=$2
    
    if [ ! -d "$ext_dir" ]; then
        echo "  ⚠ Skipping $ext_name: directory not found"
        return
    fi
    
    cd "$ext_dir" || return
    
    # Check if it's a Python package (has __init__.py or setup.py or pyproject.toml)
    if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
        echo "  📦 Installing $ext_name in editable mode..."
        pip install -e . --quiet || {
            echo "  ⚠ Failed to install $ext_name, but continuing..."
        }
    else
        # Add to PYTHONPATH if it's a simple package
        if [ -d "$(basename $ext_dir)" ] || [ -f "__init__.py" ] || find . -name "*.py" -type f | head -1 | grep -q .; then
            echo "  📁 Adding $ext_name to PYTHONPATH..."
            export PYTHONPATH="$ext_dir:$PYTHONPATH"
        fi
    fi
    
    cd - > /dev/null
}

# Install extensions
echo ""
echo "Installing extensions from $BASE_DIR:"
echo ""

# chaostooling-generic (Generic controls and utilities)
if [ -d "$BASE_DIR/chaostooling-generic" ]; then
    echo "1. chaostooling-generic (chaosgeneric)"
    install_extension "$BASE_DIR/chaostooling-generic" "chaostooling-generic"
    echo "   ✓ chaosgeneric module available"
else
    echo "1. chaostooling-generic - not found at $BASE_DIR/chaostooling-generic"
fi

# chaostooling-otel (OpenTelemetry observability)
if [ -d "$BASE_DIR/chaostooling-otel" ]; then
    echo ""
    echo "2. chaostooling-otel (chaosotel)"
    install_extension "$BASE_DIR/chaostooling-otel" "chaostooling-otel"
    echo "   ✓ chaosotel module available"
else
    echo "2. chaostooling-otel - not found"
fi

# chaostooling-extension-db (Database and messaging extensions)
if [ -d "$BASE_DIR/chaostooling-extension-db" ]; then
    echo ""
    echo "3. chaostooling-extension-db (chaosdb)"
    install_extension "$BASE_DIR/chaostooling-extension-db" "chaostooling-extension-db"
    echo "   ✓ chaosdb module available"
else
    echo "3. chaostooling-extension-db - not found"
fi

# chaostooling-extension-compute (Compute resource extensions)
if [ -d "$BASE_DIR/chaostooling-extension-compute" ]; then
    echo ""
    echo "4. chaostooling-extension-compute (chaoscompute)"
    install_extension "$BASE_DIR/chaostooling-extension-compute" "chaostooling-extension-compute"
    echo "   ✓ chaoscompute module available"
else
    echo "4. chaostooling-extension-compute - not found"
fi

# chaostooling-extension-network (Network extensions)
if [ -d "$BASE_DIR/chaostooling-extension-network" ]; then
    echo ""
    echo "5. chaostooling-extension-network (chaosnetwork)"
    install_extension "$BASE_DIR/chaostooling-extension-network" "chaostooling-extension-network"
    echo "   ✓ chaosnetwork module available"
else
    echo "5. chaostooling-extension-network - not found"
fi

# chaostooling-reporting (Reporting and analytics)
if [ -d "$BASE_DIR/chaostooling-reporting" ]; then
    echo ""
    echo "6. chaostooling-reporting"
    install_extension "$BASE_DIR/chaostooling-reporting" "chaostooling-reporting"
    echo "   ✓ chaostooling_reporting module available"
else
    echo "6. chaostooling-reporting - not found"
fi

# chaostoolkit-extension-app (Application extensions)
if [ -d "$BASE_DIR/chaostoolkit-extension-app" ]; then
    echo ""
    echo "7. chaostoolkit-extension-app (chaosapp)"
    install_extension "$BASE_DIR/chaostoolkit-extension-app" "chaostoolkit-extension-app"
    echo "   ✓ chaosapp module available"
else
    echo "7. chaostoolkit-extension-app - not found"
fi

# Add all extension directories to PYTHONPATH as fallback
export PYTHONPATH="$BASE_DIR/chaostooling-generic:$BASE_DIR/chaostooling-otel:$BASE_DIR/chaostooling-extension-db:$BASE_DIR/chaostooling-extension-compute:$BASE_DIR/chaostooling-extension-network:$BASE_DIR/chaostooling-reporting:$BASE_DIR/chaostoolkit-extension-app:$PYTHONPATH"

# Write PYTHONPATH to a file so it can be sourced by the shell
PYTHONPATH_FILE="/etc/profile.d/chaostooling-pythonpath.sh"
mkdir -p "$(dirname "$PYTHONPATH_FILE")"
echo "export PYTHONPATH=\"$PYTHONPATH\"" > "$PYTHONPATH_FILE"
chmod 644 "$PYTHONPATH_FILE"

# Verify installations
echo ""
echo "=========================================="
echo "Verification"
echo "=========================================="

# Test imports
python3 -c "import chaosgeneric; print('  ✓ chaosgeneric imported successfully')" 2>/dev/null || echo "  ⚠ chaosgeneric import failed"
python3 -c "import chaosotel; print('  ✓ chaosotel imported successfully')" 2>/dev/null || echo "  ⚠ chaosotel import failed"
python3 -c "import chaosdb; print('  ✓ chaosdb imported successfully')" 2>/dev/null || echo "  ⚠ chaosdb import failed"
python3 -c "import chaoscompute; print('  ✓ chaoscompute imported successfully')" 2>/dev/null || echo "  ⚠ chaoscompute import failed (optional)"
python3 -c "import chaosnetwork; print('  ✓ chaosnetwork imported successfully')" 2>/dev/null || echo "  ⚠ chaosnetwork import failed (optional)"
python3 -c "import chaostooling_reporting; print('  ✓ chaostooling_reporting imported successfully')" 2>/dev/null || echo "  ⚠ chaostooling_reporting import failed"
python3 -c "import chaosapp; print('  ✓ chaosapp imported successfully')" 2>/dev/null || echo "  ⚠ chaosapp import failed (optional)"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Extensions are now available for Chaos Toolkit experiments."
echo "PYTHONPATH has been updated to include all extension directories."
echo ""
