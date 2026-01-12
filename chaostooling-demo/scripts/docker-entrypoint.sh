#!/bin/bash
set -e

# Convert Windows line endings to Unix for all env and shell files
find /experiments -type f \( -name "*.sh" -o -name "*.example" -o -name "*.env" -o -name "env.*" \) -exec dos2unix {} \; 2>/dev/null || true

# Setup extensions from mounted volumes
/setup-extensions.sh

# Execute the original command
exec "$@"
