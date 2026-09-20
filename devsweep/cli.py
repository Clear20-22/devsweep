"""
devsweep.cli
============

Command-line entry point for the devsweep storage auditor.

This module owns the argument parser, orchestrates the scanner pipeline, and
routes the final ``ScanReport`` to whichever output formats the user requested.

Pipeline overview
-----------------
::

    argparse
       ↓
    [IDEScanner, PackageManagerScanner, ContainerScanner,
     AIMLScanner, SystemBrowserScanner, ProjectScanner?]
       ↓  each returns List[Finding]
    ScanReport (assembled from all findings + disk/OS metadata)
       ↓
    ┌── terminal output   (always)
    ├── --json FILE        (optional)
    ├── --markdown FILE    (optional)
    └── --generate-script FILE  (optional)

All scanner calls are wrapped in individual try/except blocks so one broken
scanner (e.g. a permission issue) never prevents the rest from running.
"""

import argparse
import platform
import time
from pathlib import Path
from typing import List

from devsweep import __version__
from devsweep.core.models import Finding, ScanReport
from devsweep.core.utils import get_disk_usage, redact_report
from devsweep.modules.ai_ml import AIMLScanner
from devsweep.modules.containers import ContainerScanner
from devsweep.modules.data_science import DataScienceScanner
from devsweep.modules.ides import IDEScanner
from devsweep.modules.language_runtimes import LanguageRuntimeScanner
from devsweep.modules.package_managers import PackageManagerScanner
from devsweep.modules.projects import ProjectScanner
from devsweep.modules.system_browsers import SystemBrowserScanner
from devsweep.reporters.json_rep import generate_json_report
from devsweep.reporters.markdown_rep import generate_markdown_report
from devsweep.reporters.script_gen import generate_cleanup_script
from devsweep.reporters.terminal import print_terminal_report


def main():
    """Parse CLI arguments, run all scanner modules, and produce requested reports.

    This function is the entry point registered in ``pyproject.toml`` under
    ``[project.scripts]`` and also called directly by ``devsweep.py`` when
    the package is run as a script.
    """
    # Ensure Windows consoles don't crash on emoji characters (e.g. 🧹) under legacy cp1252/cp437
    if sys.platform.startswith("win"):
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Argument parser setup
    # ------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        prog="devsweep",
        description="🧹 devsweep: Non-destructive developer bloat and storage auditor.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    parser.add_argument(
        "--scan-projects",
        nargs="*",
        metavar="PATH",
        help=(
            "Additional project directories to scan for virtualenvs, "
            "node_modules, and build caches.  Accepts multiple paths."
        ),
    )

    parser.add_argument(
        "--skip-projects",
        action="store_true",
        help=(
            "Skip scanning project directories entirely.  Useful when you only "
            "want to audit global toolchain caches and system-level items."
        ),
    )

    parser.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="Export full audit results to a JSON file.",
    )

    parser.add_argument(
        "--markdown",
        type=Path,
        metavar="FILE",
        help="Export full audit results to a GitHub-flavored Markdown file.",
    )

    parser.add_argument(
        "--generate-script",
        type=Path,
        metavar="FILE",
        help=(
            "Generate an interactive, commented cleanup shell script "
            "(POSIX .sh or PowerShell .ps1 on Windows)."
        ),
    )

    parser.add_argument(
        "--no-commands",
        action="store_true",
        help="Hide recommended cleanup commands in terminal output.",
    )

    parser.add_argument(
        "--redact",
        action="store_true",
        help=(
            "Replace your hostname and home-directory path with safe placeholders "
            "in terminal, JSON, and Markdown output.  "
            "Cleanup scripts always retain local paths so they remain runnable."
        ),
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Build the scanner list
    # The order here determines the order sections appear in the terminal
    # table (sorted by size within each reporter, but categories follow this).
    # ------------------------------------------------------------------
    start_time = time.time()

    scanners = [
        IDEScanner(),            # VS Code, Cursor, Windsurf, JetBrains
        PackageManagerScanner(), # pip, npm, yarn, cargo, gradle, brew, etc.
        ContainerScanner(),      # Docker, Colima, Android AVDs, Xcode, UTM
        AIMLScanner(),           # HuggingFace, PyTorch Hub, Ollama, TF Hub
        SystemBrowserScanner(),  # Browser caches, updater leftovers, crash logs
        LanguageRuntimeScanner(), # Bun, Zig, Deno, Flutter/Dart
        DataScienceScanner(),    # Conda/Mamba, JupyterLab, Ruby/Gem, Composer, Snap, Flatpak
    ]

    # ProjectScanner is opt-out: skip it only if --skip-projects is set.
    if not args.skip_projects:
        # If the user provided explicit roots via --scan-projects, resolve
        # them to absolute Paths; otherwise ProjectScanner uses its defaults.
        custom_roots = (
            [Path(p).expanduser().resolve() for p in args.scan_projects]
            if args.scan_projects
            else None
        )
        scanners.append(ProjectScanner(search_roots=custom_roots))

    # ------------------------------------------------------------------
    # Execute all scanners — failures are non-fatal
    # ------------------------------------------------------------------
    all_findings: List[Finding] = []
    scan_errors = []

    for scanner in scanners:
        try:
            findings = scanner.scan()
            all_findings.extend(findings)
        except Exception as exc:
            # A scanner may fail due to missing permissions or platform-specific
            # quirks.  We record the error and continue with the remaining
            # scanners so users get a partial report rather than a crash.
            scan_errors.append(f"{scanner.name}: {exc}")

    scan_duration = time.time() - start_time

    # Query the mount that contains the home directory for an overall
    # free-space figure to display alongside the findings.
    total_disk, used_disk, free_disk = get_disk_usage()

    # Assemble the report object that all reporters will consume.
    report = ScanReport(
        system_os=platform.platform(),
        hostname=platform.node(),
        total_disk_bytes=total_disk,
        free_disk_bytes=free_disk,
        scan_duration_sec=scan_duration,
        findings=all_findings,
    )

    # ------------------------------------------------------------------
    # Output routing
    # ``output_report`` may be a redacted copy; ``report`` keeps real paths
    # for cleanup script generation (scripts must remain runnable locally).
    # ------------------------------------------------------------------

    # 1. Always print to terminal (redacted if requested)
    output_report = redact_report(report) if args.redact else report
    print_terminal_report(output_report, show_commands=not args.no_commands)

    # Print any non-fatal scanner errors after the main report.
    if scan_errors:
        print("\nWarning: some optional scanners could not complete:")
        for error in scan_errors:
            print(f"  - {error}")

    # 2. Export JSON if --json was provided
    if args.json:
        generate_json_report(output_report, args.json)
        print(f"\n📄 JSON report saved to: {args.json.resolve()}")

    # 3. Export Markdown if --markdown was provided
    if args.markdown:
        generate_markdown_report(output_report, args.markdown)
        print(f"\n📝 Markdown report saved to: {args.markdown.resolve()}")

    # 4. Generate an interactive cleanup shell script if --generate-script was provided
    #    Note: we pass the unredacted `report` so local paths are preserved.
    if args.generate_script:
        generate_cleanup_script(report, args.generate_script)
        print(f"\n🚀 Interactive cleanup script generated: {args.generate_script.resolve()}")


if __name__ == "__main__":
    main()
