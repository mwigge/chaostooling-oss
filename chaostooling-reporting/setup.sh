#!/bin/bash
# Setup script for chaostooling-reporting

set -e

echo "Setting up chaostooling-reporting..."

# Install the package in development mode
pip install -e .

echo "✓ chaostooling-reporting installed successfully"
echo ""
echo "To use in an experiment, add the following to your experiment controls:"
echo ""
echo '  "controls": ['
echo '    {'
echo '      "name": "reporting",'
echo '      "provider": {'
echo '        "type": "python",'
echo '        "module": "chaostooling_reporting.control"'
echo '      }'
echo '    }'
echo '  ]'
echo ""

