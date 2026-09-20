"""CLI interface for devsweep developer bloat auditor."""

import argparse
import os
import platform
import sys
import time
from pathlib import Path
from typing import List

from devsweep import __version__
from devsweep.core.models import Finding, ScanReport
from devsweep.core.utils import get_disk_usage, get_os
from devsweep.modules.ai_ml import AIMLScanner
from devsweep.modules.containers import ContainerScanner
from devsweep.modules.ides import IDEScanner
from devsweep.modules.package_managers import PackageManagerScanner
from devsweep.modules.projects import ProjectScanner
from devsweep.modules.system_browsers import SystemBrowserScanner
from devsweep.reporters.json_rep import generate_json_report
from devsweep.reporters.markdown_rep import generate_markdown_report
from devsweep.reporters.script_gen import generate_cleanup_script
from devsweep.reporters.terminal import print_terminal_report


def main():
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
        help="Additional project directories to scan for virtualenvs, node_modules, and build caches.",
    )

    parser.add_argument(
        "--skip-projects",
        action="store_true",
        help="Skip scanning project directories (focus only on global toolchains, IDEs, and system caches).",
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
        help="Generate an interactive, commented cleanup shell script.",
    )

    parser.add_argument(
        "--no-commands",
        action="store_true",
        help="Hide recommended cleanup commands in terminal output.",
    )

    args = parser.parse_args()

    start_time = time.time()

    # Initialize scanners
    scanners = [
        IDEScanner(),
        PackageManagerScanner(),
        ContainerScanner(),
        AIMLScanner(),
        SystemBrowserScanner(),
    ]

    if not args.skip_projects:
        custom_roots = [Path(p).expanduser().resolve() for p in args.scan_projects] if args.scan_projects else None
        scanners.append(ProjectScanner(search_roots=custom_roots))

    # Execute non-destructive scans
    all_findings: List[Finding] = []
    for scanner in scanners:
        try:
            findings = scanner.scan()
            all_findings.extend(findings)
        except Exception as e:
            # Continue running other scanners if one encounters an OS-specific permission or path glitch
            pass

    scan_duration = time.time() - start_time
    total_disk, used_disk, free_disk = get_disk_usage()

    report = ScanReport(
        system_os=platform.platform(),
        hostname=platform.node(),
        total_disk_bytes=total_disk,
        free_disk_bytes=free_disk,
        scan_duration_sec=scan_duration,
        findings=all_findings,
    )

    # 1. Print terminal summary
    print_terminal_report(report, show_commands=not args.no_commands)

    # 2. Export JSON if requested
    if args.json:
        generate_json_report(report, args.json)
        print(f"\n📄 JSON report saved to: {args.json.resolve()}")

    # 3. Export Markdown if requested
    if args.markdown:
        generate_markdown_report(report, args.markdown)
        print(f"\n📝 Markdown report saved to: {args.markdown.resolve()}")

    # 4. Generate Cleanup Script if requested
    if args.generate_script:
        generate_cleanup_script(report, args.generate_script)
        print(f"\n🚀 Interactive cleanup script generated: {args.generate_script.resolve()}")


if __name__ == "__main__":
    main()
