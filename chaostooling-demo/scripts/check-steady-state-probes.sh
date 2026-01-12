#!/bin/bash
# Wrapper script to check steady state probes in all experiments
# Can be run from any directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "$SCRIPT_DIR/../../chaostooling-experiments" && pwd)"

python3 "$EXPERIMENTS_DIR/scripts/check-steady-state-probes.py"

