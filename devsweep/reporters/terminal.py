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

import os
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
    """Render an adaptive, responsive terminal report using the ``rich`` library.

    Automatically detects terminal width and switches between:
    * Compact Card Mode (< 75 cols): For split panes, mobile, and small windows.
    * Responsive Table Mode (75–109 cols): 4-column balanced table with dynamic ratios.
    * Expanded Table Mode (>= 110 cols): 5-column comprehensive view with details.
    """
    term_width = None
    if "COLUMNS" in os.environ:
        try:
            term_width = int(os.environ["COLUMNS"])
        except ValueError:
            pass
    if not term_width:
        term_width = shutil.get_terminal_size((80, 24)).columns

    console = Console(width=term_width)

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
    console.print(Panel(header_text, border_style="cyan", expand=True))

    # Short-circuit if no findings were found.
    if not report.findings:
        console.print(
            "[bold green]✨ Your system is crystal clean! "
            "No significant developer bloat detected.[/bold green]"
        )
        return

    # Sort findings by size descending — biggest space savings appear first.
    sorted_findings = sorted(report.findings, key=lambda f: f.size_bytes, reverse=True)

    # ------------------------------------------------------------------
    # Responsive Display Strategy based on terminal window width
    # ------------------------------------------------------------------
    if term_width < 75:
        # --- Mode 1: Compact Card Stream (Narrow Terminals < 75 cols) ---
        console.print("[bold cyan]🔍 Identified Cleanup Targets[/bold cyan]\n")
        for f in sorted_findings:
            if f.safety == SafetyLevel.ZERO_RISK:
                badge = "[bold green]● ZERO RISK[/]"
                border_color = "green"
            elif f.safety == SafetyLevel.SAFE_CACHE:
                badge = "[bold yellow]● SAFE CACHE[/]"
                border_color = "yellow"
            else:
                badge = "[bold blue]● REVIEW[/]"
                border_color = "blue"

            card = Text()
            card.append(f"{f.title}\n", style="bold white")
            card.append(f"Category: {f.category.value}  ·  ", style="dim")
            card.append(f"{f.formatted_size}\n", style="bold yellow")
            if f.description:
                card.append(f"{f.description}\n", style="dim white")
            if f.path:
                card.append(f"Path: {f.path}\n", style="dim")
            if show_commands and f.cleanup_command and not f.cleanup_command.startswith("#"):
                card.append(f"Command: {f.cleanup_command}", style="cyan")

            console.print(Panel(card, title=badge, title_align="left", border_style=border_color, expand=True))

    elif term_width < 110:
        # --- Mode 2: Standard 4-Column Table (75–109 cols) ---
        table = Table(
            title="🔍 Identified Cleanup Targets",
            border_style="dim",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Category", style="dim", ratio=2, overflow="ellipsis")
        table.add_column("Target / Component", style="bold", ratio=3)
        table.add_column("Size", justify="right", style="bold yellow", min_width=10, max_width=12)
        table.add_column("Safety Level", justify="center", min_width=14, max_width=16)

        for f in sorted_findings:
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
            )

        console.print(table)
        console.print()

    else:
        # --- Mode 3: Wide 5-Column Table with Full Details (>= 110 cols) ---
        table = Table(
            title="🔍 Identified Cleanup Targets",
            border_style="dim",
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Category", style="dim", ratio=2, overflow="ellipsis")
        table.add_column("Target / Component", style="bold", ratio=3)
        table.add_column("Size", justify="right", style="bold yellow", min_width=10, max_width=12)
        table.add_column("Safety Level", justify="center", min_width=14, max_width=16)
        table.add_column("Details", style="white", ratio=4)

        for f in sorted_findings:
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

    # --- Safety tier breakdown table (Responsive) ---
    summary_table = Table(title="📊 Space Savings Breakdown", border_style="dim", expand=True)
    summary_table.add_column("Tier", style="bold", ratio=2)
    summary_table.add_column("Reclaimable Size", justify="right", style="bold yellow", min_width=10, max_width=14)

    if term_width >= 80:
        summary_table.add_column("Impact Description", style="dim", ratio=3)
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
    else:
        summary_table.add_row(
            "🟢 Low Risk (Orphans / Installers)",
            format_bytes(report.zero_risk_bytes),
        )
        summary_table.add_row(
            "🟡 Safe Caches (Toolchains / Build)",
            format_bytes(report.safe_cache_bytes),
        )
        summary_table.add_row(
            "🔵 Review Required (VMs / Envs)",
            format_bytes(report.review_required_bytes),
        )

    console.print(summary_table)
    console.print()

    # --- Cleanup commands panel ---
    if show_commands:
        cmd_panel = Text()
        cmd_panel.append("🛠️ Recommended Cleanup Commands\n\n", style="bold cyan")

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

        console.print(Panel(cmd_panel, title="Actionable Commands", border_style="green", expand=True))


# ---------------------------------------------------------------------------
# Plain-text fallback renderer (no Rich dependency)
# ---------------------------------------------------------------------------

def _print_plain_report(report: ScanReport, show_commands: bool) -> None:
    """Render a plain-text report using only stdlib ``print()`` calls.

    Used when ``rich`` is not installed.  All essential information is still
    shown — just without colours or box-drawing characters.
    """
    term_w = shutil.get_terminal_size((70, 20)).columns
    sep_w = min(max(term_w, 35), 90)
    sep = "=" * sep_w
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
