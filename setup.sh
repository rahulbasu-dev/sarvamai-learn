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
PKG_MANAGER=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "Detected: $PRETTY_NAME"
    case "$ID" in
        ubuntu|debian)  PKG_MANAGER="apt" ;;
        rocky|rhel|centos|alma|fedora) PKG_MANAGER="dnf" ;;
        *) warn "Unknown distro ($ID). Will try to auto-detect package manager." ;;
    esac
else
    warn "Cannot detect OS. Will try to auto-detect package manager."
fi

# Auto-detect package manager if not set
if [ -z "$PKG_MANAGER" ]; then
    if command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt"
    elif command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MANAGER="yum"
    else
        error "No supported package manager found (apt, dnf, yum). Install dependencies manually."
        exit 1
    fi
fi
info "Using package manager: $PKG_MANAGER"

# --------------------------------------------------------------------------
# 2. System dependencies
# --------------------------------------------------------------------------
install_packages() {
    if [ "$PKG_MANAGER" = "apt" ]; then
        sudo apt-get update -qq
        local PACKAGES=(python3 python3-venv python3-pip git ffmpeg fonts-noto)
        for pkg in "${PACKAGES[@]}"; do
            if dpkg -s "$pkg" &>/dev/null; then
                info "  $pkg — already installed"
            else
                info "  $pkg — installing..."
                sudo apt-get install -y -qq "$pkg"
            fi
        done
    else
        # dnf/yum (Rocky, RHEL, CentOS, Alma, Fedora)
        local MGR="$PKG_MANAGER"
        local PACKAGES=(python3 python3-pip git ffmpeg google-noto-sans-fonts)
        for pkg in "${PACKAGES[@]}"; do
            if rpm -q "$pkg" &>/dev/null; then
                info "  $pkg — already installed"
            else
                info "  $pkg — installing..."
                sudo "$MGR" install -y -q "$pkg"
            fi
        done
        # Enable EPEL + CRB for ffmpeg if not already available
        if ! command -v ffmpeg &>/dev/null; then
            warn "ffmpeg not found — trying EPEL/RPM Fusion..."
            sudo "$MGR" install -y -q epel-release 2>/dev/null || true
            sudo "$MGR" config-manager --set-enabled crb 2>/dev/null || true
            sudo "$MGR" install -y -q --enablerepo=epel ffmpeg 2>/dev/null || \
                warn "Could not install ffmpeg. Audio notebooks may not work. Install it manually."
        fi
    fi
}

info "Installing system dependencies..."
install_packages

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
pip install --upgrade pip
info "pip version: $(pip --version)"

# --------------------------------------------------------------------------
# 4. Python dependencies
# --------------------------------------------------------------------------
echo ""
info "============================================"
info "  Installing Python packages"
info "============================================"
info ""
info "Core packages:"
info "  sarvamai        — Sarvam AI Python SDK"
info "  python-dotenv   — .env file loader"
info "  jupyter         — JupyterLab notebook server"
info "  matplotlib      — plotting & visualisation"
info "  seaborn         — statistical plots"
info "  numpy           — numerical computing"
info "  pandas          — data manipulation"
info "  nltk            — NLP tokenizers & corpora"
info "  IPython         — rich display in notebooks"
info "  requests        — HTTP client"
info "  Pillow          — image processing"
info ""
info "AI SDK packages:"
info "  krutrim-cloud   — Krutrim AI SDK"
info "  openai          — OpenAI-compatible client (used by Krutrim)"
info ""
info "Bonus cell packages (larger downloads):"
info "  transformers    — Hugging Face model hub (~500 MB with models)"
info "  sentencepiece   — subword tokeniser"
info "  sentence-transformers — multilingual embeddings"
info "  torch           — PyTorch deep learning framework (~800 MB)"
info "  sacrebleu       — BLEU score evaluation"
info "  sacremoses      — Moses tokenizer for MT"
info "  scipy           — scientific computing"
info ""
info "Installing from requirements.txt (this may take a few minutes)..."
echo ""
pip install -r requirements.txt
echo ""
info "All Python packages installed."

# Show installed package versions
info ""
info "Installed package versions:"
pip list --format=columns | grep -iE "sarvamai|dotenv|jupyter|matplotlib|seaborn|numpy|pandas|nltk|requests|Pillow|krutrim|openai|transformers|sentencepiece|sentence-trans|torch|sacrebleu|sacremoses|scipy" || true
info ""

# --------------------------------------------------------------------------
# 5. NLTK data
# --------------------------------------------------------------------------
info "Downloading NLTK data (punkt tokenizer)..."
python3 -c "
import nltk, os
nltk_data = os.path.expanduser('~/nltk_data')
for pkg in ('punkt', 'punkt_tab'):
    try:
        nltk.download(pkg, quiet=False, download_dir=nltk_data)
    except Exception as e:
        print(f'  Warning: could not download {pkg}: {e}')
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
