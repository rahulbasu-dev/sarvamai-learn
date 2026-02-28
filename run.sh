#!/usr/bin/env bash
# run.sh — Launch JupyterLab for remote access
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "ERROR: venv not found. Run 'bash setup.sh' first."
    exit 1
fi

source venv/bin/activate

echo "Starting JupyterLab on 0.0.0.0:8888 ..."
echo "Access URL will be printed below (use your VM's public IP)."
echo ""

exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
