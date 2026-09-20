"""
devsweep.reporters.script_gen
==============================

Generator for interactive, opt-in cleanup shell scripts.

The generated script prompts the user before running each tier so they remain
in full control.  It is the only output that uses *unredacted* absolute paths
(i.e. it is always generated from the original ``report``, not a redacted copy)
so the commands are immediately runnable on the same machine.

Output formats
--------------
* **POSIX bash script** (``.sh``) — generated on macOS and Linux.  Uses
  ``read -p`` to prompt before Tier 1 & 2 (bulk) and individually for each
  Tier 3 item.  Uses ``|| true`` after each command so a single failure does
  not abort the whole script (``set -e`` is still active for unexpected errors).
* **PowerShell script** (``.ps1``) — generated on Windows.  Uses
  ``Read-Host`` for prompts.  Only includes commands that are
  natively usable on Windows (skips bare ``rm -rf`` and compound ``&&``
  chains which are not PowerShell-compatible).

Safety
------
All three safety tiers are included in the generated script:

* **Tier 1 — Zero Risk**: prompted once for the whole tier (bulk confirm).
* **Tier 2 — Safe Caches**: prompted once for the whole tier (bulk confirm).
* **Tier 3 — Requires Review**: each item is prompted *individually* with its
  full description printed before the ``[y/N]`` prompt.  This forces a
  conscious decision per virtualenv / VM / duplicate app.

POSIX shell quoting
-------------------
Labels embedded in ``echo`` calls may contain single quotes (e.g. a project
called "Bob's app").  The ``_posix_echo`` helper encodes them using the
"string gluing" pattern: ``'part1'"'"'part2'`` — the outer single-quoted
segments avoid most special characters, and the inner ``"'"`` is a
double-quoted single-quote literal.  This is fully POSIX-portable and works
in dash, bash, and zsh.
"""

from pathlib import Path

from devsweep.core.models import SafetyLevel, ScanReport
from devsweep.core.utils import format_bytes, is_windows


# ---------------------------------------------------------------------------
# Quoting helpers
# ---------------------------------------------------------------------------

def _posix_echo(value: str) -> str:
    """Return ``value`` as a safely single-quoted POSIX shell argument.

    Single-quoting prevents any interpretation of special characters inside
    the label.  The only character that cannot appear inside a single-quoted
    string is a single quote itself, so we break the string and inject a
    double-quoted single quote:

        ``'it''"'"'s a label'``  →  ``it's a label``

    This approach works in POSIX sh, bash, dash, and zsh.
    """
    return "'" + value.replace("'", "'\\\"'\\\"'") + "'"


def _powershell_string(value: str) -> str:
    """Return ``value`` as a safely single-quoted PowerShell string literal.

    In PowerShell, single-quoted strings are literal (no variable expansion).
    The only escape inside a single-quoted string is ``''`` (two single quotes)
    to represent one single quote.
    """
    return "'" + value.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cleanup_script(report: ScanReport, output_path: Path) -> None:
    """Generate an interactive cleanup script for the detected findings.

    Dispatches to the appropriate OS-specific generator based on the current
    platform.

    Parameters
    ----------
    report : ScanReport
        The **unredacted** scan report.  The script needs real absolute paths
        so the generated ``rm -rf`` commands are immediately runnable.
    output_path : Path
        Destination file.  For POSIX the file is chmod-ed to ``0o755``
        (executable) after writing.
    """
    if is_windows():
        _generate_windows_batch(report, output_path)
    else:
        _generate_posix_script(report, output_path)


# ---------------------------------------------------------------------------
# POSIX bash script generator
# ---------------------------------------------------------------------------

def _generate_posix_script(report: ScanReport, output_path: Path) -> None:
    """Write a POSIX bash cleanup script to ``output_path``.

    The script uses ``set -e`` so it aborts on unexpected errors, but appends
    ``|| true`` to each cleanup command so a single command failure (e.g. a
    file that was already deleted) does not abort the whole session.
    """
    lines = [
        "#!/usr/bin/env bash",
        # Header banner
        "# =====================================================================",
        "# devsweep Auto-Generated Interactive Cleanup Script",
        f"# System: {report.system_os} | Total Reclaimable: {format_bytes(report.total_reclaimable_bytes)}",
        "#",
        "# This script prompts before running each cleanup tier.",
        "# Review the commands below before running.",
        "# =====================================================================",
        "set -e",
        "",
        'echo "🧹 Starting devsweep cleanup..."',
        'echo "This script will prompt before running each cleanup tier."',
        "",
        # -------------------------------------------------------------------
        # Tier 1: Zero Risk
        # -------------------------------------------------------------------
        "# ---------------------------------------------------------------------",
        "# TIER 1: Zero Risk (Dead orphans, download dumps, installer caches)",
        f"# Potential space reclaimed: {format_bytes(report.zero_risk_bytes)}",
        "# ---------------------------------------------------------------------",
        'read -p "Execute Tier 1 (Zero-Risk cleanup)? [y/N] " confirm_tier1',
        'if [[ "$confirm_tier1" =~ ^[Yy]$ ]]; then',
    ]

    zero_risk = [
        f for f in report.findings
        if f.safety == SafetyLevel.ZERO_RISK
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")  # Skip human-instruction comments.
    ]
    if zero_risk:
        for f in zero_risk:
            # Embed a labelled echo before each command so the user can follow
            # progress.  The label is safely quoted using _posix_echo.
            label = _posix_echo(f"Cleaning: {f.title} ({f.formatted_size})...")
            lines.append(f"  echo {label}\n  {f.cleanup_command} || true")
    else:
        lines.append('  echo "No Tier 1 items to clean."')

    lines.extend([
        "fi",
        "",
        # -------------------------------------------------------------------
        # Tier 2: Safe Caches
        # -------------------------------------------------------------------
        "# ---------------------------------------------------------------------",
        "# TIER 2: Safe Caches (Dev toolchains, build caches, browser caches)",
        f"# Potential space reclaimed: {format_bytes(report.safe_cache_bytes)}",
        "# ---------------------------------------------------------------------",
        'read -p "Execute Tier 2 (Safe Caches cleanup)? [y/N] " confirm_tier2',
        'if [[ "$confirm_tier2" =~ ^[Yy]$ ]]; then',
    ])

    safe_cache = [
        f for f in report.findings
        if f.safety == SafetyLevel.SAFE_CACHE
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")
    ]
    if safe_cache:
        for f in safe_cache:
            label = _posix_echo(f"Cleaning: {f.title} ({f.formatted_size})...")
            lines.append(f"  echo {label}\n  {f.cleanup_command} || true")
    else:
        lines.append('  echo "No Tier 2 items to clean."')

    lines.extend([
        "fi",
        "",
        # -------------------------------------------------------------------
        # Tier 3: Requires Review
        # These items need human judgement — virtualenvs may still be needed,
        # Docker VMs may hold live data, etc.  Each item is prompted individually
        # so the user makes a deliberate choice for every one.
        # -------------------------------------------------------------------
        "# ---------------------------------------------------------------------",
        "# TIER 3: Requires Review (virtualenvs, Docker VMs, AVDs, duplicate apps)",
        f"# Potential space reclaimed: {format_bytes(report.review_required_bytes)}",
        "# READ CAREFULLY: these items may contain data you still need.",
        "# Each item below will ask for individual confirmation.",
        "# ---------------------------------------------------------------------",
    ])

    review = [
        f for f in report.findings
        if f.safety == SafetyLevel.REQUIRES_REVIEW
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")
    ]
    if review:
        for f in review:
            # Prompt per-item so the user consciously approves each deletion.
            label = _posix_echo(f"[REVIEW] {f.title} ({f.formatted_size}) — {f.description}")
            confirm_var = f"confirm_review_{f.id.replace('-', '_')}"
            lines.extend([
                "echo ''",  # blank line for readability between items
                f"echo {label}",
                f'read -p "  Delete this? [y/N] " {confirm_var}',
                f'if [[ "${confirm_var}" =~ ^[Yy]$ ]]; then',
                f"  {f.cleanup_command} || true",
                "fi",
            ])
    else:
        lines.append('echo "No Tier 3 (review-required) items detected."')

    lines.extend([
        "",
        'echo "✨ Cleanup sequence completed!"',
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    # Make the script executable immediately after writing.
    output_path.chmod(0o755)


# ---------------------------------------------------------------------------
# Windows PowerShell script generator
# ---------------------------------------------------------------------------

def _generate_windows_batch(report: ScanReport, output_path: Path) -> None:
    """Write a PowerShell cleanup script to ``output_path``.

    Limitations vs. the POSIX script:
    * Only includes findings whose cleanup command does not use ``rm -rf``
      or ``&&`` (these are bash-isms not supported natively in PowerShell).
    * REQUIRES_REVIEW findings are excluded from both POSIX and PowerShell scripts.
    """
    lines = [
        "# devsweep generated PowerShell cleanup script",
        "# Inspect all commands carefully before running.",
        "# REQUIRES_REVIEW items are excluded — handle those manually.",
        "$ErrorActionPreference = 'Continue'",
        f"Write-Host {_powershell_string('devsweep cleanup — potential reclaim: ' + format_bytes(report.total_reclaimable_bytes))}",
    ]

    # Process Zero Risk and Safe Cache tiers together (same automated flow).
    for label, safety, size in (
        ("Tier 1 (low-risk cleanup)", SafetyLevel.ZERO_RISK, report.zero_risk_bytes),
        ("Tier 2 (rebuildable caches)", SafetyLevel.SAFE_CACHE, report.safe_cache_bytes),
    ):
        # Filter out bash-specific commands that would break in PowerShell.
        candidates = [
            f for f in report.findings
            if f.safety == safety
            and f.cleanup_command
            and not f.cleanup_command.startswith("#")
            and "rm -rf" not in f.cleanup_command  # PowerShell uses Remove-Item
            and " && " not in f.cleanup_command      # PowerShell uses ; or separate statements
        ]

        lines.extend([
            "",
            f"# {label}; potential reclaim: {format_bytes(size)}",
            f"$answer = Read-Host {_powershell_string('Run ' + label + '? [y/N]')}",
            "if ($answer -match '^[Yy]$') {",
        ])

        if candidates:
            for finding in candidates:
                lines.append(
                    f"  Write-Host {_powershell_string('Cleaning: ' + finding.title + ' (' + finding.formatted_size + ')...')}"
                )
                lines.append(f"  & {finding.cleanup_command}")
        else:
            lines.append(
                "  Write-Host 'No Windows-compatible automated commands were found in this tier.'"
            )
        lines.append("}")

    # Tier 3: Requires Review — prompted individually per item.
    # These items may hold live data (VMs, active virtualenvs, etc.).
    review_candidates = [
        f for f in report.findings
        if f.safety == SafetyLevel.REQUIRES_REVIEW
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")
        and "rm -rf" not in f.cleanup_command
        and " && " not in f.cleanup_command
    ]
    lines.extend([
        "",
        f"# Tier 3 (requires review); potential reclaim: {format_bytes(report.review_required_bytes)}",
        "# Each item below is prompted individually — read carefully before confirming.",
    ])
    if review_candidates:
        for finding in review_candidates:
            lines.extend([
                f"Write-Host ''",
                f"Write-Host {_powershell_string('[REVIEW] ' + finding.title + ' (' + finding.formatted_size + ')')} ",
                f"Write-Host {_powershell_string('  ' + finding.description)}",
                f"$r = Read-Host {_powershell_string('  Delete this? [y/N]')}",
                "if ($r -match '^[Yy]$') {",
                f"  & {finding.cleanup_command}",
                "}",
            ])
    else:
        lines.append("Write-Host 'No Windows-compatible Tier 3 commands found.'")

    lines.extend(["", "Write-Host 'Cleanup sequence completed.'"])
    output_path.write_text("\n".join(lines), encoding="utf-8")
