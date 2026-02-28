#!/usr/bin/env bash
# setup.sh — One-click cloud VM setup for Sarvam AI Indic NLP notebooks
# Usage: bash setup.sh
# Idempotent — safe to run multiple times.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --------------------------------------------------------------------------
# Colors
# --------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --------------------------------------------------------------------------
# 1. OS detection
# --------------------------------------------------------------------------
info "Detecting OS..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "Detected: $PRETTY_NAME"
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        warn "This script is tested on Ubuntu/Debian. Your distro ($ID) may need manual adjustments."
    fi
else
    warn "Cannot detect OS. Proceeding anyway — install failures may need manual fixes."
fi

# --------------------------------------------------------------------------
# 2. System dependencies
# --------------------------------------------------------------------------
info "Installing system dependencies..."
sudo apt-get update -qq

PACKAGES=(
    python3
    python3-venv
    python3-pip
    git
    ffmpeg
    fonts-noto
)

for pkg in "${PACKAGES[@]}"; do
    if dpkg -s "$pkg" &>/dev/null; then
        info "  $pkg — already installed"
    else
        info "  $pkg — installing..."
        sudo apt-get install -y -qq "$pkg"
    fi
done

# Verify Python version >= 3.10
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    error "Python 3.10+ required (found $PYTHON_VERSION). Please install a newer Python."
    exit 1
fi
info "Python $PYTHON_VERSION OK"

# --------------------------------------------------------------------------
# 3. Python virtual environment
# --------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
else
    info "Virtual environment already exists."
fi

source venv/bin/activate
info "Upgrading pip..."
pip install --upgrade pip -q

# --------------------------------------------------------------------------
# 4. Python dependencies
# --------------------------------------------------------------------------
info "Installing Python packages from requirements.txt..."
pip install -r requirements.txt -q

# --------------------------------------------------------------------------
# 5. NLTK data
# --------------------------------------------------------------------------
info "Downloading NLTK data..."
python3 -c "
import nltk, os
nltk_data = os.path.expanduser('~/nltk_data')
for pkg in ('punkt', 'punkt_tab'):
    try:
        nltk.download(pkg, quiet=True, download_dir=nltk_data)
    except Exception:
        pass
"

# --------------------------------------------------------------------------
# 6. .env file
# --------------------------------------------------------------------------
if [ ! -f .env ]; then
    info "Creating .env from .env.example..."
    cp .env.example .env

    # SARVAM_API_KEY
    if [ -n "${SARVAM_API_KEY:-}" ]; then
        info "  SARVAM_API_KEY found in environment."
        sed -i "s|^SARVAM_API_KEY=.*|SARVAM_API_KEY=$SARVAM_API_KEY|" .env
    else
        echo ""
        read -rp "Enter your SARVAM_API_KEY (or press Enter to skip): " key
        if [ -n "$key" ]; then
            sed -i "s|^SARVAM_API_KEY=.*|SARVAM_API_KEY=$key|" .env
        else
            warn "SARVAM_API_KEY left empty — set it in .env before running notebooks."
        fi
    fi

    # KRUTRIM_CLOUD_API_KEY
    if [ -n "${KRUTRIM_CLOUD_API_KEY:-}" ]; then
        info "  KRUTRIM_CLOUD_API_KEY found in environment."
        sed -i "s|^KRUTRIM_CLOUD_API_KEY=.*|KRUTRIM_CLOUD_API_KEY=$KRUTRIM_CLOUD_API_KEY|" .env
    else
        read -rp "Enter your KRUTRIM_CLOUD_API_KEY (or press Enter to skip): " key
        if [ -n "$key" ]; then
            sed -i "s|^KRUTRIM_CLOUD_API_KEY=.*|KRUTRIM_CLOUD_API_KEY=$key|" .env
        else
            warn "KRUTRIM_CLOUD_API_KEY left empty — set it in .env before running notebooks."
        fi
    fi
else
    info ".env already exists — skipping."
fi

# --------------------------------------------------------------------------
# 7. Output directories
# --------------------------------------------------------------------------
mkdir -p outputs/audio outputs/figures
info "Output directories ready."

# --------------------------------------------------------------------------
# 8. Smoke test
# --------------------------------------------------------------------------
info "Running smoke test..."
if python3 -c "from utils.sarvam_helpers import load_client; load_client()" 2>/dev/null; then
    info "Smoke test passed — API client loads successfully."
else
    warn "Smoke test failed — check your SARVAM_API_KEY in .env (notebooks may still work in DEMO_MODE)."
fi

# --------------------------------------------------------------------------
# Done
# --------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env to add any missing API keys"
echo "  2. Run: bash run.sh"
echo "  3. Open the JupyterLab URL in your browser"
echo "  4. Start with notebooks/00_quick_start.ipynb"
echo ""
