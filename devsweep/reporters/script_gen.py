"""Generator for opt-in, interactive cleanup scripts."""

from pathlib import Path
from devsweep.core.models import SafetyLevel, ScanReport
from devsweep.core.utils import format_bytes, is_windows


def _posix_echo(value: str) -> str:
    """Quote filesystem-derived labels for a POSIX shell echo."""
    return "'" + value.replace("'", "'\\\"'\\\"'") + "'"


def _powershell_string(value: str) -> str:
    """Quote a value for a single-quoted PowerShell string literal."""
    return "'" + value.replace("'", "''") + "'"


def generate_cleanup_script(report: ScanReport, output_path: Path):
    """Generate an interactive, commented shell script for cleanup."""
    if is_windows():
        _generate_windows_batch(report, output_path)
    else:
        _generate_posix_script(report, output_path)


def _generate_posix_script(report: ScanReport, output_path: Path):
    lines = [
        "#!/usr/bin/env bash",
        "# =====================================================================",
        "# devsweep Auto-Generated Interactive Cleanup Script",
        f"# System: {report.system_os} | Total Reclaimable: {format_bytes(report.total_reclaimable_bytes)}",
        "# =====================================================================",
        "set -e",
        "",
        'echo "🧹 Starting devsweep cleanup..."',
        'echo "This script will prompt before running each cleanup tier."',
        "",
        "# ---------------------------------------------------------------------",
        "# TIER 1: Zero Risk (Dead orphans, download dumps, installer caches)",
        f"# Potential space: {format_bytes(report.zero_risk_bytes)}",
        "# ---------------------------------------------------------------------",
        'read -p "Execute Tier 1 (Zero-Risk cleanup)? [y/N] " confirm_tier1',
        'if [[ "$confirm_tier1" =~ ^[Yy]$ ]]; then',
    ]

    zero_risk = [f for f in report.findings if f.safety == SafetyLevel.ZERO_RISK and f.cleanup_command and not f.cleanup_command.startswith("#")]
    if zero_risk:
        for f in zero_risk:
            lines.append(f"  echo {_posix_echo('Cleaning: ' + f.title + ' (' + f.formatted_size + ')...')}\n  {f.cleanup_command} || true")
    else:
        lines.append('  echo "No Tier 1 items to clean."')

    lines.extend([
        "fi",
        "",
        "# ---------------------------------------------------------------------",
        "# TIER 2: Safe Caches (Dev toolchains, build caches, browser caches)",
        f"# Potential space: {format_bytes(report.safe_cache_bytes)}",
        "# ---------------------------------------------------------------------",
        'read -p "Execute Tier 2 (Safe Caches cleanup)? [y/N] " confirm_tier2',
        'if [[ "$confirm_tier2" =~ ^[Yy]$ ]]; then',
    ])

    safe_cache = [f for f in report.findings if f.safety == SafetyLevel.SAFE_CACHE and f.cleanup_command and not f.cleanup_command.startswith("#")]
    if safe_cache:
        for f in safe_cache:
            lines.append(f"  echo {_posix_echo('Cleaning: ' + f.title + ' (' + f.formatted_size + ')...')}\n  {f.cleanup_command} || true")
    else:
        lines.append('  echo "No Tier 2 items to clean."')

    lines.extend([
        "fi",
        "",
        'echo "✨ Cleanup sequence completed!"',
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    output_path.chmod(0o755)


def _generate_windows_batch(report: ScanReport, output_path: Path):
    """Generate a usable PowerShell script (the supplied suffix is preserved)."""
    lines = [
        "# devsweep generated PowerShell cleanup script",
        "# It excludes all REVIEW findings. Inspect commands before running.",
        "$ErrorActionPreference = 'Continue'",
        f"Write-Host {_powershell_string('devsweep cleanup — potential reclaim: ' + format_bytes(report.total_reclaimable_bytes))}",
    ]
    for label, safety, size in (
        ("Tier 1 (low-risk cleanup)", SafetyLevel.ZERO_RISK, report.zero_risk_bytes),
        ("Tier 2 (rebuildable caches)", SafetyLevel.SAFE_CACHE, report.safe_cache_bytes),
    ):
        candidates = [f for f in report.findings if f.safety == safety and f.cleanup_command
                      and not f.cleanup_command.startswith("#") and "rm -rf" not in f.cleanup_command
                      and " && " not in f.cleanup_command]
        lines.extend(["", f"# {label}; potential reclaim: {format_bytes(size)}",
                      f"$answer = Read-Host {_powershell_string('Run ' + label + '? [y/N]')}",
                      "if ($answer -match '^[Yy]$') {"])
        if candidates:
            for finding in candidates:
                lines.append(f"  Write-Host {_powershell_string('Cleaning: ' + finding.title + ' (' + finding.formatted_size + ')...')}")
                lines.append(f"  & {finding.cleanup_command}")
        else:
            lines.append("  Write-Host 'No Windows-compatible automated commands were found in this tier.'")
        lines.append("}")
    lines.extend(["", "Write-Host 'Cleanup sequence completed.'"])
    output_path.write_text("\n".join(lines), encoding="utf-8")
