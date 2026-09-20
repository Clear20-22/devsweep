#!/usr/bin/env bash
# =============================================================================
# devsweep — One-Time Setup Script
# =============================================================================
# Run this ONCE after cloning the repo:
#
#   bash scripts/install.sh
#
# What it does:
#   1. Checks that Python 3.8+ is available.
#   2. Creates a local .venv virtual environment in the project root.
#   3. Installs required packages (rich for coloured terminal output).
#   4. Makes launcher scripts (ds, scripts/run.sh) executable.
#
# After this you never need to run install.sh again.
# =============================================================================

set -e  # Exit immediately if any command fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Always execute operations from the repository root
cd "$ROOT_DIR"

# ---------------------------------------------------------------------------
# Colour codes for install script output
# ---------------------------------------------------------------------------
BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

print_step()  { echo -e "${CYAN}${BOLD}▶ $1${RESET}"; }
print_ok()    { echo -e "${GREEN}✔ $1${RESET}"; }
print_warn()  { echo -e "${YELLOW}⚠ $1${RESET}"; }
print_error() { echo -e "${RED}✖ $1${RESET}"; }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║  🧹  devsweep — Setup & Installation         ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Step 1 — Verify Python 3.8+ is available
# ---------------------------------------------------------------------------
print_step "Checking Python version..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(sys.version_info.major * 10 + sys.version_info.minor)")
        if [ "$version" -ge 38 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    print_error "Python 3.8 or newer is required but was not found."
    echo "  Install it from: https://python.org/downloads"
    exit 1
fi

PY_VERSION=$("$PYTHON" --version 2>&1)
print_ok "Found $PY_VERSION"

# ---------------------------------------------------------------------------
# Step 2 — Create virtual environment
# ---------------------------------------------------------------------------
print_step "Creating virtual environment (.venv)..."

if [ -d ".venv" ]; then
    print_warn ".venv already exists — skipping creation."
else
    "$PYTHON" -m venv .venv
    print_ok ".venv created."
fi

# Activate the venv for the rest of this script.
# shellcheck source=/dev/null
source .venv/bin/activate

# ---------------------------------------------------------------------------
# Step 3 — Upgrade pip silently
# ---------------------------------------------------------------------------
print_step "Upgrading pip..."
python -m ensurepip --quiet 2>/dev/null || true
python -m pip install --upgrade pip --quiet 2>/dev/null || true
print_ok "pip is ready."

# ---------------------------------------------------------------------------
# Step 4 — Install dependencies
# ---------------------------------------------------------------------------
print_step "Installing dependencies (rich)..."

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet 2>/dev/null || print_warn "Could not install rich (offline?); devsweep will fall back to built-in ASCII mode."
    print_ok "Dependencies processed."
else
    pip install "rich>=13.0.0" --quiet 2>/dev/null || print_warn "Could not install rich (offline?); devsweep will fall back to built-in ASCII mode."
    print_ok "Dependencies processed."
fi

# ---------------------------------------------------------------------------
# Step 5 — Make run.sh and ds launchers executable
# ---------------------------------------------------------------------------
print_step "Configuring launcher scripts..."
chmod +x "$ROOT_DIR/ds" "$ROOT_DIR/scripts/run.sh" "$ROOT_DIR/scripts/install.sh"
print_ok "Launchers are executable."

# ---------------------------------------------------------------------------
# Done!
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  ✨  Setup complete! Run devsweep with:       ║${RESET}"
echo -e "${BOLD}${GREEN}║                                               ║${RESET}"
echo -e "${BOLD}${GREEN}║     ./ds            ← interactive launcher    ║${RESET}"
echo -e "${BOLD}${GREEN}║     ./ds help       ← instructions & commands ║${RESET}"
echo -e "${BOLD}${GREEN}║     ./ds scan       ← quick audit scan        ║${RESET}"
echo -e "${BOLD}${GREEN}║                                               ║${RESET}"
echo -e "${BOLD}${GREEN}║  (Or: bash scripts/run.sh)                    ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════╝${RESET}"
echo ""
