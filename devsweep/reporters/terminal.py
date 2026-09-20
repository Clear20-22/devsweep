"""
devsweep.reporters.terminal
============================

Terminal reporter — renders the scan report to stdout using Rich tables when
available, or falls back to plain ANSI text when Rich is not installed.

Output structure
----------------
1. **Header panel** — OS, hostname, free disk space, total reclaimable space.
2. **Findings table** — one row per finding, sorted largest-first, with
   colour-coded safety badges.
3. **Summary breakdown table** — reclaimable bytes by safety tier.
4. **Cleanup commands panel** — ready-to-run commands (Tier 1 then Tier 2).
   Hidden when ``--no-commands`` is passed.

Rich vs. plain text
-------------------
* If ``rich`` is installed (listed in ``requirements.txt``), the reporter uses
  Rich's ``Console``, ``Table``, and ``Panel`` for coloured, boxed output.
* If ``rich`` is not installed (e.g. running stock Python 3 with no packages),
  the reporter falls back to plain ``print()`` statements so the tool always
  works with zero dependencies.

Usage
-----
::

    from devsweep.reporters.terminal import print_terminal_report
    print_terminal_report(report, show_commands=True)
"""

import shutil
import sys

from devsweep.core.models import Category, Finding, SafetyLevel, ScanReport
from devsweep.core.utils import format_bytes

# Try to import Rich; fall back gracefully if it is not installed.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_terminal_report(report: ScanReport, show_commands: bool = True) -> None:
    """Render ``report`` to stdout, using Rich if available.

    Parameters
    ----------
    report : ScanReport
        The scan result to display (may be a redacted copy).
    show_commands : bool
        When ``False``, the cleanup command panel is omitted (``--no-commands``).
    """
    if HAS_RICH:
        _print_rich_report(report, show_commands)
    else:
        _print_plain_report(report, show_commands)


# ---------------------------------------------------------------------------
# Rich renderer
# ---------------------------------------------------------------------------

def _print_rich_report(report: ScanReport, show_commands: bool) -> None:
    """Render a rich, coloured terminal report using the ``rich`` library."""
    console = Console()

    # --- Header panel ---
    total_reclaim = format_bytes(report.total_reclaimable_bytes)
    free_disk = format_bytes(report.free_disk_bytes)
    total_disk = format_bytes(report.total_disk_bytes)

    header_text = Text()
    header_text.append("🧹 devsweep Developer Bloat & Storage Auditor\n", style="bold magenta")
    header_text.append(
        f"OS: {report.system_os} | Free Disk: {free_disk} / {total_disk} | "
        f"Scan Time: {report.scan_duration_sec:.2f}s\n",
        style="dim",
    )
    header_text.append(f"Total Reclaimable Space Found: {total_reclaim}", style="bold green")
    console.print(Panel(header_text, border_style="cyan"))

    # Short-circuit if no findings were found.
    if not report.findings:
        console.print(
            "[bold green]✨ Your system is crystal clean! "
            "No significant developer bloat detected.[/bold green]"
        )
        return

    # --- Findings table ---
    table = Table(
        title="🔍 Identified Cleanup Targets",
        border_style="dim",
        header_style="bold cyan",
    )
    table.add_column("Category", style="dim", width=24)
    table.add_column("Target / Component", style="bold", width=34)
    table.add_column("Size", justify="right", style="bold yellow", width=12)
    table.add_column("Safety Level", justify="center", width=16)
    table.add_column("Details", style="white")

    # Sort findings by size descending — biggest space savings appear first.
    sorted_findings = sorted(report.findings, key=lambda f: f.size_bytes, reverse=True)

    for f in sorted_findings:
        # Colour-coded safety badge using Rich's inline markup.
        if f.safety == SafetyLevel.ZERO_RISK:
            safety_badge = "[bold white on green] ZERO RISK [/]"
        elif f.safety == SafetyLevel.SAFE_CACHE:
            safety_badge = "[bold black on yellow] SAFE CACHE [/]"
        else:
            safety_badge = "[bold white on blue] REVIEW [/]"

        table.add_row(
            f.category.value,
            f.title,
            f.formatted_size,
            safety_badge,
            f.description,
        )

    console.print(table)
    console.print()

    # --- Safety tier breakdown table ---
    summary_table = Table(title="📊 Space Savings Breakdown", border_style="dim")
    summary_table.add_column("Tier", style="bold")
    summary_table.add_column("Reclaimable Size", justify="right", style="bold")
    summary_table.add_column("Impact Description", style="dim")

    summary_table.add_row(
        "🟢 Low Risk (Dead data, orphans, installers)",
        format_bytes(report.zero_risk_bytes),
        "Verify the path and close the related app before deleting.",
    )
    summary_table.add_row(
        "🟡 Safe Caches (Dev/build/browser caches)",
        format_bytes(report.safe_cache_bytes),
        "Safe to clear. Rebuilds/redownloads automatically on demand.",
    )
    summary_table.add_row(
        "🔵 Review Required (Virtualenvs, VMs, duplicate apps)",
        format_bytes(report.review_required_bytes),
        "Contains project environments or VM images. Check before removing.",
    )
    console.print(summary_table)
    console.print()

    # --- Cleanup commands panel ---
    if show_commands:
        cmd_panel = Text()
        cmd_panel.append("🛠️ Recommended Cleanup Commands\n\n", style="bold cyan")

        # Tier 1: Zero Risk commands
        # Commands starting with ``#`` are human instructions — omit them from
        # the runnable command list.
        zero_risk = [
            f for f in sorted_findings
            if f.safety == SafetyLevel.ZERO_RISK
            and f.cleanup_command
            and not f.cleanup_command.startswith("#")
        ]
        if zero_risk:
            cmd_panel.append("# Tier 1: Low-Risk Cleanup (verify paths first)\n", style="bold green")
            for f in zero_risk:
                cmd_panel.append(f"{f.cleanup_command}\n", style="green")
            cmd_panel.append("\n")

        # Tier 2: Safe cache commands
        safe_cache = [
            f for f in sorted_findings
            if f.safety == SafetyLevel.SAFE_CACHE
            and f.cleanup_command
            and not f.cleanup_command.startswith("#")
        ]
        if safe_cache:
            cmd_panel.append("# Tier 2: Safe Cache Purge (Rebuilds automatically)\n", style="bold yellow")
            for f in safe_cache:
                cmd_panel.append(f"{f.cleanup_command}\n", style="yellow")
            cmd_panel.append("\n")

        console.print(Panel(cmd_panel, title="Actionable Commands", border_style="green"))


# ---------------------------------------------------------------------------
# Plain-text fallback renderer (no Rich dependency)
# ---------------------------------------------------------------------------

def _print_plain_report(report: ScanReport, show_commands: bool) -> None:
    """Render a plain-text report using only stdlib ``print()`` calls.

    Used when ``rich`` is not installed.  All essential information is still
    shown — just without colours or box-drawing characters.
    """
    sep = "=" * 70
    print(sep)
    print("🧹 devsweep Developer Bloat & Storage Auditor")
    print(
        f"OS: {report.system_os} | "
        f"Free Disk: {format_bytes(report.free_disk_bytes)} / {format_bytes(report.total_disk_bytes)}"
    )
    print(f"Total Reclaimable Space: {format_bytes(report.total_reclaimable_bytes)}")
    print(sep)

    if not report.findings:
        print("✨ Your system is clean! No significant bloat detected.")
        return

    sorted_findings = sorted(report.findings, key=lambda f: f.size_bytes, reverse=True)

    for f in sorted_findings:
        print(f"\n[{f.safety.value}] {f.title} - {f.formatted_size}")
        print(f"  Category: {f.category.value}")
        print(f"  Path:     {f.path}")
        print(f"  Details:  {f.description}")
        if show_commands and f.cleanup_command:
            print(f"  Command:  {f.cleanup_command}")

    print("\n" + sep)
    print(
        f"Summary: "
        f"Zero Risk: {format_bytes(report.zero_risk_bytes)} | "
        f"Safe Caches: {format_bytes(report.safe_cache_bytes)} | "
        f"Review: {format_bytes(report.review_required_bytes)}"
    )
    print(sep)
