#!/usr/bin/env bash
# =============================================================================
# devsweep — Responsive Terminal Runner & Interactive Dashboard
# =============================================================================
# Dynamically adapts to any terminal window size (small, standard, or wide).
#
# Usage:
#   ./ds                         Interactive dashboard (from project root)
#   bash scripts/run.sh          Interactive dashboard (direct script run)
#   ./ds help                    Instructions: how to do, what to do, commands
#   ./ds scan                    Quick scan (global toolchains & caches)
#   ./ds full [path]             Full scan (includes project repositories)
#   ./ds report [file.md]        Export safe redacted Markdown report
#   ./ds json [file.json]        Export full JSON audit report
#   ./ds script [file.sh]        Generate interactive cleanup script
#   ./ds clean                   Generate + run cleanup script with confirmations
#   ./ds alias                   Add 'devsweep' & 'ds' commands to your shell
# =============================================================================

set -e

# ---------------------------------------------------------------------------
# Directory Resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve Python & pip inside .venv (handles both Unix and Windows layout)
if [ -f "$ROOT_DIR/.venv/Scripts/python.exe" ]; then
    VENV_PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
    VENV_PIP="$ROOT_DIR/.venv/Scripts/pip.exe"
elif [ -f "$ROOT_DIR/.venv/Scripts/python" ]; then
    VENV_PYTHON="$ROOT_DIR/.venv/Scripts/python"
    VENV_PIP="$ROOT_DIR/.venv/Scripts/pip"
else
    VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
    VENV_PIP="$ROOT_DIR/.venv/bin/pip"
fi

# ---------------------------------------------------------------------------
# Terminal Dimensions & Responsiveness
# ---------------------------------------------------------------------------
get_cols() {
    local cols
    cols=$(tput cols 2>/dev/null || echo 80)
    if [ -z "$cols" ] || [ "$cols" -lt 35 ]; then
        cols=80
    fi
    echo "$cols"
}

draw_hr() {
    local char="${1:-─}"
    local cols
    cols=$(get_cols)
    local width=$(( cols > 76 ? 76 : (cols < 38 ? 38 : cols - 4) ))
    local line=""
    for ((i=0; i<width; i++)); do line="${line}${char}"; done
    echo "$line"
}

# ---------------------------------------------------------------------------
# Terminal Colours (works in bash/zsh on macOS, Linux, and WSL)
# ---------------------------------------------------------------------------
BOLD="\033[1m";   RESET="\033[0m"
RED="\033[31m";   GREEN="\033[32m";  YELLOW="\033[33m"
BLUE="\033[34m";  CYAN="\033[36m";   MAGENTA="\033[35m"
WHITE="\033[97m"; DIM="\033[2m"

c()  { echo -e "${1}${2}${RESET}"; }
cb() { echo -e "${BOLD}${1}${2}${RESET}"; }

# ---------------------------------------------------------------------------
# Self-Bootstrapping Setup (runs automatically if .venv is missing)
# ---------------------------------------------------------------------------
bootstrap_setup() {
    echo ""
    cb "$CYAN" "  ╔══════════════════════════════════════════════════════════╗"
    cb "$CYAN" "  ║  🧹  First-Time Setup: Initialising devsweep...          ║"
    cb "$CYAN" "  ╚══════════════════════════════════════════════════════════╝"
    echo ""

    # Detect Python 3.8+
    local py=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(sys.version_info.major * 10 + sys.version_info.minor)" 2>/dev/null || echo "0")
            if [ "$ver" -ge 38 ]; then
                py="$cmd"
                break
            fi
        fi
    done

    if [ -z "$py" ]; then
        cb "$RED" "  ✖ Python 3.8 or newer is required but was not found."
        c  "$YELLOW" "    Please install Python from: https://python.org/downloads"
        echo ""
        exit 1
    fi

    c "$CYAN" "  ▶ Creating virtual environment (.venv)..."
    "$py" -m venv "$ROOT_DIR/.venv"

    local venv_pip="$ROOT_DIR/.venv/bin/pip"
    if [ -f "$ROOT_DIR/.venv/Scripts/pip.exe" ]; then
        venv_pip="$ROOT_DIR/.venv/Scripts/pip.exe"
    elif [ -f "$ROOT_DIR/.venv/Scripts/pip" ]; then
        venv_pip="$ROOT_DIR/.venv/Scripts/pip"
    fi

    c "$CYAN" "  ▶ Installing dependencies (rich for formatted output)..."
    if [ -f "$ROOT_DIR/requirements.txt" ]; then
        "$venv_pip" install -r "$ROOT_DIR/requirements.txt" --quiet 2>/dev/null || true
    else
        "$venv_pip" install "rich>=13.0.0" --quiet 2>/dev/null || true
    fi

    chmod +x "$ROOT_DIR/ds" "$ROOT_DIR/scripts/run.sh" "$ROOT_DIR/scripts/install.sh" 2>/dev/null || true

    cb "$GREEN" "  ✔ Setup complete! Ready to run."
    echo ""
}

# Auto-run setup if .venv does not exist yet
if [ ! -f "$VENV_PYTHON" ]; then
    bootstrap_setup
fi

# Run devsweep Python entry point with passed arguments and pass terminal COLUMNS
run_devsweep() {
    export COLUMNS
    COLUMNS=$(get_cols)
    "$VENV_PYTHON" "$ROOT_DIR/devsweep.py" "$@"
}

# ---------------------------------------------------------------------------
# Responsive Header Banner
# ---------------------------------------------------------------------------
show_banner() {
    local cols
    cols=$(get_cols)
    echo ""
    if [ "$cols" -lt 68 ]; then
        cb "$CYAN" "  🧹 devsweep — Developer Bloat Auditor"
        c  "$DIM"  "  Non-destructive · Cross-platform · Open Source"
        c  "$DIM"  "  $(draw_hr '─')"
    else
        cb "$CYAN" "  ╔$(draw_hr '═')╗"
        cb "$CYAN" "  ║  🧹  devsweep — Developer Bloat & Storage Auditor"
        c  "$DIM"  "  ║  Non-destructive · Cross-platform · Open Source"
        cb "$CYAN" "  ╚$(draw_hr '═')╝"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Responsive Help & Instructions: How to do, What to do, Commands
# ---------------------------------------------------------------------------
show_instructions() {
    show_banner
    local cols
    cols=$(get_cols)

    cb "$WHITE"   "  📖 1. HOW TO DO (HOW DEVSWEEP WORKS)"
    c  "$DIM"     "  $(draw_hr '─')"
    c  "$GREEN"   "  • Non-Destructive by Design:"
    c  "$DIM"     "    devsweep NEVER deletes any files on its own."
    c  "$DIM"     "    It audits disk space, categorises bloat, and provides"
    c  "$DIM"     "    transparent recommendations with exact file sizes."
    echo ""
    c  "$YELLOW"  "  • Understand the 3 Safety Tiers:"
    c  "$GREEN"   "    🟢 ZERO RISK    : Dead data (orphaned IDE storage, old updater caches)."
    c  "$YELLOW"  "    🟡 SAFE CACHE   : Rebuildable packages & toolchains (pip, npm, cargo, bun)."
    c  "$BLUE"    "    🔵 REVIEW       : User assets (dormant .venv, Docker VMs, git repos)."
    echo ""
    c  "$MAGENTA" "  • Safe Remediation:"
    c  "$DIM"     "    Generate a cleanup script (./ds script) so you can review"
    c  "$DIM"     "    every command before executing, or run ./ds clean for"
    c  "$DIM"     "    guided step-by-step confirmation."
    echo ""

    cb "$WHITE"   "  🎯 2. WHAT TO DO (RECOMMENDED ACTIONS)"
    c  "$DIM"     "  $(draw_hr '─')"
    c  "$CYAN"    "  • First time running devsweep?"
    c  "$DIM"     "    Run a Quick Scan: ./ds scan"
    c  "$DIM"     "    Audits system caches and toolchains in 1–2 seconds."
    echo ""
    c  "$CYAN"    "  • Need to free up gigabytes of project storage?"
    c  "$DIM"     "    Run a Full Scan: ./ds full"
    c  "$DIM"     "    Audits local project directories for stale virtualenvs & node_modules."
    echo ""
    c  "$CYAN"    "  • Want to share findings safely?"
    c  "$DIM"     "    Export a Redacted Report: ./ds report"
    c  "$DIM"     "    Personal usernames, home paths, and hostnames are hidden."
    echo ""

    cb "$WHITE"   "  ⌨️  3. WHAT CAN DO WITH COMMANDS (TERMINAL CHEAT-SHEET)"
    c  "$DIM"     "  $(draw_hr '─')"

    if [ "$cols" -lt 75 ]; then
        # Compact command format for narrow screens
        c "$GREEN"   "  ./ds"
        c "$DIM"     "    Interactive menu dashboard"
        c "$GREEN"   "  ./ds help"
        c "$DIM"     "    Show this instruction guide"
        c "$CYAN"    "  ./ds scan"
        c "$DIM"     "    Quick scan (caches only)"
        c "$CYAN"    "  ./ds full"
        c "$DIM"     "    Full scan (includes project repos)"
        c "$CYAN"    "  ./ds full ~/Work"
        c "$DIM"     "    Full scan with custom directory"
        c "$YELLOW"  "  ./ds report [f.md]"
        c "$DIM"     "    Save anonymised Markdown report"
        c "$YELLOW"  "  ./ds json [f.json]"
        c "$DIM"     "    Save machine-readable JSON report"
        c "$MAGENTA" "  ./ds script [f.sh]"
        c "$DIM"     "    Generate interactive cleanup script"
        c "$MAGENTA" "  ./ds clean"
        c "$DIM"     "    Generate & run cleanup script"
        c "$WHITE"   "  ./ds alias"
        c "$DIM"     "    Install 'devsweep' & 'ds' to your shell"
    else
        # Standard side-by-side table format for regular/wide screens
        printf "  %-24s %s\n" "$(c "$GREEN" "./ds")" "Open interactive menu dashboard"
        printf "  %-24s %s\n" "$(c "$GREEN" "./ds help")" "Show this instruction guide"
        printf "  %-24s %s\n" "$(c "$CYAN"  "./ds scan")" "Quick scan (global toolchains & caches)"
        printf "  %-24s %s\n" "$(c "$CYAN"  "./ds full")" "Full scan (includes project repos)"
        printf "  %-24s %s\n" "$(c "$CYAN"  "./ds full ~/Work")" "Full scan with custom directory"
        printf "  %-24s %s\n" "$(c "$YELLOW" "./ds report [f.md]")" "Save anonymized Markdown report"
        printf "  %-24s %s\n" "$(c "$YELLOW" "./ds json [f.json]")" "Save machine-readable JSON report"
        printf "  %-24s %s\n" "$(c "$MAGENTA" "./ds script [f.sh]")" "Generate interactive cleanup script"
        printf "  %-24s %s\n" "$(c "$MAGENTA" "./ds clean")" "Generate & run cleanup script"
        printf "  %-24s %s\n" "$(c "$WHITE" "./ds alias")" "Install 'devsweep' & 'ds' to your shell"
    fi
    echo ""
    c "$DIM" "  Tip: You can also run 'bash scripts/run.sh' with any of the above commands."
    echo ""

    if [ "${1:-}" = "from_menu" ]; then
        _wait_for_key
    fi
}

# ---------------------------------------------------------------------------
# Shell Alias / Special Keyword Installer
# ---------------------------------------------------------------------------
cmd_install_alias() {
    echo ""
    cb "$CYAN" "  ⚡ Configure Terminal Keyword / Alias"
    c  "$DIM"  "  $(draw_hr '─')"
    c  "$WHITE" "  This lets you run 'devsweep' or 'ds' from ANY folder in your terminal."
    echo ""

    local shell_rc=""
    local current_shell
    current_shell="$(basename "${SHELL:-bash}")"

    if [ "$current_shell" = "zsh" ] && [ -f "$HOME/.zshrc" ]; then
        shell_rc="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        shell_rc="$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then
        shell_rc="$HOME/.zshrc"
    elif [ -f "$HOME/.bash_profile" ]; then
        shell_rc="$HOME/.bash_profile"
    fi

    if [ -z "$shell_rc" ]; then
        cb "$YELLOW" "  Could not find a standard ~/.zshrc or ~/.bashrc file."
        c  "$DIM"    "  Add this manually to your shell profile:"
        echo ""
        c  "$CYAN"   "  alias devsweep=\"$ROOT_DIR/ds\""
        c  "$CYAN"   "  alias ds=\"$ROOT_DIR/ds\""
        echo ""
        _wait_for_key
        return
    fi

    c "$WHITE" "  Detected shell config file: $shell_rc"
    echo ""
    printf "  %b" "${BOLD}${WHITE}Add 'devsweep' and 'ds' aliases to $shell_rc? [Y/n]: ${RESET}"
    read -r confirm
    confirm="${confirm:-y}"

    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        if grep -q "alias devsweep=" "$shell_rc" 2>/dev/null; then
            c "$YELLOW" "  devsweep alias is already configured in $shell_rc."
        else
            {
                echo ""
                echo "# devsweep CLI shortcuts"
                echo "alias devsweep=\"$ROOT_DIR/ds\""
                echo "alias ds=\"$ROOT_DIR/ds\""
            } >> "$shell_rc"
            cb "$GREEN" "  ✔ Successfully added 'devsweep' and 'ds' to $shell_rc!"
        fi
        echo ""
        c "$DIM" "  To activate now in this terminal window, run:"
        c "$CYAN" "  source $shell_rc"
        echo ""
        c "$DIM" "  Then you can simply type:"
        c "$GREEN" "  devsweep        (or: ds)"
        echo ""
    else
        c "$DIM" "  Skipped."
        echo ""
    fi
    _wait_for_key
}

# ---------------------------------------------------------------------------
# Interactive Menu Loop
# ---------------------------------------------------------------------------
show_menu() {
    while true; do
        show_banner

        cb "$WHITE"   "  SELECT AN OPTION:"
        c  "$DIM"     "  $(draw_hr '─')"
        c  "$CYAN"    "  1)  🔍  Quick Scan         (toolchains & caches, 1-2 sec)"
        c  "$CYAN"    "  2)  📁  Full Scan          (caches + project repos)"
        c  "$CYAN"    "  3)  📂  Custom Path Scan   (scan custom directory)"
        c  "$YELLOW"  "  4)  📝  Save Markdown      (anonymised report → audit-report.md)"
        c  "$YELLOW"  "  5)  📄  Save JSON Report   (audit-report.json)"
        c  "$MAGENTA" "  6)  🚀  Generate Script    (reviewable cleanup.sh)"
        c  "$MAGENTA" "  7)  🧹  Clean Up Now       (generate + guided prompts)"
        c  "$WHITE"   "  8)  ⚡  Install Keyword    (use 'devsweep' or 'ds' anywhere)"
        c  "$GREEN"   "  9)  📖  Help & Manual      (how to do, what to do, commands)"
        c  "$RED"     "  q)  ✖   Quit"
        echo ""
        printf "  %b" "${BOLD}${WHITE}Enter choice [1-9 or q]: ${RESET}"
        read -r choice

        case "$choice" in
            1) cmd_scan ;;
            2) cmd_full ;;
            3) cmd_custom_scan ;;
            4) cmd_report ;;
            5) cmd_json ;;
            6) cmd_script ;;
            7) cmd_clean ;;
            8) cmd_install_alias ;;
            9) show_instructions "from_menu" ;;
            q|Q) echo "" ; c "$DIM" "  Goodbye!" ; echo "" ; exit 0 ;;
            *) c "$RED" "  Invalid choice. Please select 1-9 or q." ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Action Implementations
# ---------------------------------------------------------------------------
cmd_scan() {
    echo ""
    cb "$CYAN" "  🔍 Running quick scan (toolchain & system caches)..."
    echo ""
    run_devsweep --skip-projects --redact
    echo ""
    cb "$GREEN" "  ✔ Quick scan complete."
    _ask_next_step
}

cmd_full() {
    local extra_root="${1:-}"
    echo ""
    cb "$CYAN" "  🔍 Running full scan (caches + project repositories)..."
    echo ""
    if [ -n "$extra_root" ]; then
        run_devsweep --redact --scan-projects "$extra_root"
    else
        run_devsweep --redact
    fi
    echo ""
    cb "$GREEN" "  ✔ Full scan complete."
    _ask_next_step
}

cmd_custom_scan() {
    echo ""
    printf "  %b" "${BOLD}${WHITE}Enter directory path to scan [e.g. ~/Work]: ${RESET}"
    read -r target_path
    if [ -z "$target_path" ]; then
        c "$DIM" "  No path provided. Returning to menu."
        return
    fi
    # Expand tilde if present
    target_path="${target_path/#\~/$HOME}"
    cmd_full "$target_path"
}

cmd_report() {
    local output_file="${1:-}"
    if [ -z "$output_file" ]; then
        printf "  %b" "${BOLD}${WHITE}Enter filename [default: audit-report.md]: ${RESET}"
        read -r input_file
        output_file="${input_file:-audit-report.md}"
    fi

    echo ""
    cb "$YELLOW" "  📝 Generating anonymised Markdown report → $output_file"
    echo ""
    run_devsweep --redact --skip-projects --markdown "$output_file"
    echo ""
    cb "$GREEN"  "  ✔ Report saved: $output_file"
    c  "$DIM"    "  Paths and hostnames are redacted (~/) so it is safe to share."
    echo ""
    _wait_for_key
}

cmd_json() {
    local output_file="${1:-}"
    if [ -z "$output_file" ]; then
        printf "  %b" "${BOLD}${WHITE}Enter filename [default: audit-report.json]: ${RESET}"
        read -r input_file
        output_file="${input_file:-audit-report.json}"
    fi

    echo ""
    cb "$YELLOW" "  📄 Generating JSON report → $output_file"
    echo ""
    run_devsweep --redact --skip-projects --json "$output_file"
    echo ""
    cb "$GREEN"  "  ✔ JSON report saved: $output_file"
    echo ""
    _wait_for_key
}

cmd_script() {
    local output_file="${1:-}"
    if [ -z "$output_file" ]; then
        printf "  %b" "${BOLD}${WHITE}Enter script filename [default: cleanup.sh]: ${RESET}"
        read -r input_file
        output_file="${input_file:-cleanup.sh}"
    fi

    echo ""
    cb "$MAGENTA" "  🚀 Generating interactive cleanup script → $output_file"
    echo ""
    run_devsweep --skip-projects --generate-script "$output_file"
    echo ""
    cb "$GREEN"  "  ✔ Cleanup script generated: $output_file"
    echo ""
    c  "$DIM"    "  You can inspect the script before running:"
    c  "$CYAN"   "    cat $output_file"
    c  "$DIM"    "  Then run it whenever you are ready:"
    c  "$CYAN"   "    bash $output_file"
    echo ""
    _wait_for_key
}

cmd_clean() {
    local output_file="cleanup.sh"
    echo ""
    cb "$MAGENTA" "  🚀 Generating cleanup script → $output_file"
    run_devsweep --skip-projects --generate-script "$output_file"
    echo ""
    cb "$YELLOW"  "  ─────────────────────────────────────────────────────────"
    cb "$YELLOW"  "  ⚠  SAFETY CHECK BEFORE RUNNING"
    c  "$DIM"     "  The script will prompt you before executing each tier."
    c  "$DIM"     "  You can decline (N) on any step you wish to skip."
    cb "$YELLOW"  "  ─────────────────────────────────────────────────────────"
    echo ""
    printf "  %b" "${BOLD}${WHITE}Run cleanup.sh now? [y/N]: ${RESET}"
    read -r run_now
    if [[ "$run_now" =~ ^[Yy]$ ]]; then
        echo ""
        bash "$output_file"
    else
        c "$DIM" "  Skipped. You can inspect or run it later with: bash $output_file"
    fi
    echo ""
    _wait_for_key
}

_ask_next_step() {
    echo ""
    cb "$WHITE" "  What would you like to do next?"
    c  "$YELLOW"  "  r) Save Markdown report"
    c  "$MAGENTA" "  s) Generate cleanup script"
    c  "$MAGENTA" "  c) Clean up now (guided interactive)"
    c  "$GREEN"   "  m) Return to main menu"
    c  "$DIM"     "  q) Quit"
    echo ""
    printf "  %b" "${BOLD}${WHITE}Choice [r/s/c/m/q]: ${RESET}"
    read -r next
    case "$next" in
        r|R) cmd_report ;;
        s|S) cmd_script ;;
        c|C) cmd_clean ;;
        m|M|"") ;;  # Continues back to show_menu loop
        q|Q) echo "" ; c "$DIM" "  Goodbye!" ; echo "" ; exit 0 ;;
        *) ;;
    esac
}

_wait_for_key() {
    echo ""
    printf "  %b" "${DIM}Press [Enter] to return to the menu...${RESET}"
    read -r _
    echo ""
}

# ---------------------------------------------------------------------------
# CLI Argument Dispatcher
# ---------------------------------------------------------------------------
COMMAND="${1:-}"

case "$COMMAND" in
    ""                  ) show_menu ;;
    help|-h|--help      ) show_instructions ;;
    scan                ) cmd_scan ;;
    full                ) cmd_full "${2:-}" ;;
    report              ) cmd_report "${2:-}" ;;
    json                ) cmd_json "${2:-}" ;;
    script              ) cmd_script "${2:-}" ;;
    clean               ) cmd_clean ;;
    alias|install-alias ) cmd_install_alias ;;
    *)
        c "$RED" "  Unknown command: $COMMAND"
        c "$DIM" "  Run './ds help' to see all available commands and instructions."
        echo ""
        exit 1
        ;;
esac
