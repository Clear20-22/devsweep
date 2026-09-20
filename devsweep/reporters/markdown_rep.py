"""Markdown report generator for devsweep."""

from pathlib import Path
from devsweep.core.models import SafetyLevel, ScanReport
from devsweep.core.utils import format_bytes


def generate_markdown_report(report: ScanReport, output_path: Path):
    """Generate a clean GitHub-flavored markdown report file."""
    lines = [
        "# 🧹 devsweep Storage & Developer Bloat Audit Report",
        "",
        f"- **Operating System**: {report.system_os}",
        f"- **Hostname**: `{report.hostname}`",
        f"- **Free Disk Space**: {format_bytes(report.free_disk_bytes)} (out of {format_bytes(report.total_disk_bytes)})",
        f"- **Total Reclaimable Space**: **{format_bytes(report.total_reclaimable_bytes)}**",
        f"- **Scan Time**: {report.scan_duration_sec:.2f} seconds",
        "",
        "## 📊 Space Savings Breakdown",
        "",
        "| Tier | Reclaimable Space | Impact & Description |",
        "| :--- | :---: | :--- |",
        f"| 🟢 **Zero Risk** | **{format_bytes(report.zero_risk_bytes)}** | Dead orphans, installer packages, update dumps. 100% safe. |",
        f"| 🟡 **Safe Caches** | **{format_bytes(report.safe_cache_bytes)}** | Dev toolchain, compiler, and browser caches. Auto-rebuilds on demand. |",
        f"| 🔵 **Requires Review** | **{format_bytes(report.review_required_bytes)}** | Project virtualenvs, Docker VMs, or duplicate app installations. |",
        "",
        "## 🔍 Detailed Findings",
        "",
        "| Category | Component / Target | Size | Safety | Details |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ]

    sorted_findings = sorted(report.findings, key=lambda f: f.size_bytes, reverse=True)
    for f in sorted_findings:
        safety_emoji = "🟢 Zero Risk" if f.safety == SafetyLevel.ZERO_RISK else ("🟡 Safe Cache" if f.safety == SafetyLevel.SAFE_CACHE else "🔵 Review")
        lines.append(f"| {f.category.value} | `{f.title}` | **{f.formatted_size}** | {safety_emoji} | {f.description} |")

    lines.extend([
        "",
        "## 🛠️ Recommended Cleanup Commands",
        "",
        "### 🟢 Tier 1: Zero Risk Instant Cleanup",
        "```bash",
    ])

    zero_risk_cmds = [f.cleanup_command for f in sorted_findings if f.safety == SafetyLevel.ZERO_RISK and f.cleanup_command and not f.cleanup_command.startswith("#")]
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

    safe_cache_cmds = [f.cleanup_command for f in sorted_findings if f.safety == SafetyLevel.SAFE_CACHE and f.cleanup_command and not f.cleanup_command.startswith("#")]
    if safe_cache_cmds:
        lines.extend(safe_cache_cmds)
    else:
        lines.append("# No safe cache targets detected.")

    lines.extend([
        "```",
        "",
        "---",
        "*Generated automatically by [devsweep](https://github.com/jubayerahmedsojib/devsweep) — Non-destructive developer bloat auditor.*",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
