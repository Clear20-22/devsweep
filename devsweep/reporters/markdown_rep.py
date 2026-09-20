"""
devsweep.reporters.markdown_rep
================================

GitHub-flavored Markdown (GFM) report generator for devsweep scan results.

The generated file is designed to be committed to a gist, pasted into a GitHub
issue, or viewed in any Markdown renderer.  It contains:

1. **Header block** — OS, hostname, disk usage, total reclaimable space.
2. **Space Savings Breakdown** — summary table by safety tier.
3. **Detailed Findings** — one row per finding, sorted largest-first.
4. **Recommended Cleanup Commands** — copy-pasteable bash code blocks grouped
   by tier (Zero Risk → Safe Caches).  REQUIRES_REVIEW findings are listed in
   the findings table but intentionally omitted from the command blocks.

Usage
-----
::

    from devsweep.reporters.markdown_rep import generate_markdown_report
    generate_markdown_report(report, Path("audit-report.md"))

Privacy note
------------
Pass a ``redact_report(report)`` copy to this function when the user has
specified ``--redact``, so the hostname and home path are replaced with
``<redacted>`` and ``~`` respectively before writing to disk.
"""

from pathlib import Path

from devsweep.core.models import SafetyLevel, ScanReport
from devsweep.core.utils import format_bytes


def generate_markdown_report(report: ScanReport, output_path: Path) -> None:
    """Write a GitHub-flavored Markdown audit report to ``output_path``.

    Findings are sorted by ``size_bytes`` descending so the biggest savings
    appear first in the table.  Only ``ZERO_RISK`` and ``SAFE_CACHE`` findings
    with non-comment commands are included in the cleanup code blocks.

    Parameters
    ----------
    report : ScanReport
        The scan result (may be redacted).
    output_path : Path
        Destination ``.md`` file.  Parent directories must exist.
    """
    # Build the report as a list of strings, then join once at the end.
    # This avoids repeated string concatenation and is easier to extend.
    lines = [
        "# 🧹 devsweep Storage & Developer Bloat Audit Report",
        "",
        # --- System summary header ---
        f"- **Operating System**: {report.system_os}",
        f"- **Hostname**: `{report.hostname}`",
        f"- **Free Disk Space**: {format_bytes(report.free_disk_bytes)} (out of {format_bytes(report.total_disk_bytes)})",
        f"- **Total Reclaimable Space**: **{format_bytes(report.total_reclaimable_bytes)}**",
        f"- **Scan Time**: {report.scan_duration_sec:.2f} seconds",
        "",
        # --- Safety tier breakdown table ---
        "## 📊 Space Savings Breakdown",
        "",
        "| Tier | Reclaimable Space | Impact & Description |",
        "| :--- | :---: | :--- |",
        f"| 🟢 **Low Risk** | **{format_bytes(report.zero_risk_bytes)}** | Dead orphans, installer packages, update dumps. Verify paths first. |",
        f"| 🟡 **Safe Caches** | **{format_bytes(report.safe_cache_bytes)}** | Dev toolchain, compiler, and browser caches. Auto-rebuilds on demand. |",
        f"| 🔵 **Requires Review** | **{format_bytes(report.review_required_bytes)}** | Project virtualenvs, Docker VMs, or duplicate app installations. |",
        "",
        # --- Per-finding detail table ---
        "## 🔍 Detailed Findings",
        "",
        "| Category | Component / Target | Size | Safety | Details |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ]

    # Sort findings largest-first so the most impactful items appear at the top.
    sorted_findings = sorted(report.findings, key=lambda f: f.size_bytes, reverse=True)

    for f in sorted_findings:
        # Map the enum value to a coloured emoji badge for the table cell.
        if f.safety == SafetyLevel.ZERO_RISK:
            safety_emoji = "🟢 Zero Risk"
        elif f.safety == SafetyLevel.SAFE_CACHE:
            safety_emoji = "🟡 Safe Cache"
        else:
            safety_emoji = "🔵 Review"

        lines.append(
            f"| {f.category.value} | `{f.title}` | **{f.formatted_size}** | {safety_emoji} | {f.description} |"
        )

    # --- Cleanup command blocks ---
    # We deliberately omit REQUIRES_REVIEW findings from command blocks because
    # they need human judgement before running.
    lines.extend([
        "",
        "## 🛠️ Recommended Cleanup Commands",
        "",
        "### 🟢 Tier 1: Zero Risk Instant Cleanup",
        "```bash",
    ])

    # Commands starting with ``#`` are human-readable instructions, not shell commands.
    # We include them in the detail table but skip them in runnable code blocks.
    zero_risk_cmds = [
        f.cleanup_command
        for f in sorted_findings
        if f.safety == SafetyLevel.ZERO_RISK
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")
    ]
    if zero_risk_cmds:
        lines.extend(zero_risk_cmds)
    else:
        lines.append("# No zero-risk targets detected.")

    lines.extend([
        "```",
        "",
        "### 🟡 Tier 2: Safe Cache Purge (Rebuilds automatically as needed)",
        "```bash",
    ])

    safe_cache_cmds = [
        f.cleanup_command
        for f in sorted_findings
        if f.safety == SafetyLevel.SAFE_CACHE
        and f.cleanup_command
        and not f.cleanup_command.startswith("#")
    ]
    if safe_cache_cmds:
        lines.extend(safe_cache_cmds)
    else:
        lines.append("# No safe cache targets detected.")

    lines.extend([
        "```",
        "",
        "---",
        "*Generated automatically by [devsweep](https://github.com/your-username/devsweep)"
        " — Non-destructive developer bloat auditor.*",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
