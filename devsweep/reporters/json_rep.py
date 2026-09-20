"""
devsweep.reporters.json_rep
============================

JSON report generator for devsweep scan results.

Produces a structured JSON file suitable for machine consumption, CI pipelines,
or feeding into other tools.  The schema mirrors the ``ScanReport`` dataclass
and is intentionally stable across patch releases.

Output schema
-------------
::

    {
      "system_os":          "<platform.platform() string>",
      "hostname":           "<machine hostname or '<redacted>'>",
      "total_disk_bytes":   <int>,
      "free_disk_bytes":    <int>,
      "scan_duration_sec":  <float>,
      "summary": {
        "total_reclaimable_bytes": <int>,
        "zero_risk_bytes":         <int>,
        "safe_cache_bytes":        <int>,
        "review_required_bytes":   <int>
      },
      "findings": [
        {
          "id":              "<snake_case_identifier>",
          "title":           "<Human-readable title>",
          "category":        "<Category enum value>",
          "safety":          "<SafetyLevel enum value>",
          "path":            "<absolute or redacted path>",
          "size_bytes":      <int>,
          "description":     "<one-sentence explanation>",
          "cleanup_command": "<shell command or # comment>",
          "item_count":      <int | null>,
          "metadata":        {}
        },
        ...
      ]
    }

Usage
-----
::

    from devsweep.reporters.json_rep import generate_json_report
    generate_json_report(report, Path("audit.json"))

The file is written atomically via ``Path.write_text`` with UTF-8 encoding
and 2-space indentation for readability.
"""

import json
from dataclasses import asdict
from pathlib import Path

from devsweep.core.models import ScanReport


def generate_json_report(report: ScanReport, output_path: Path) -> None:
    """Serialise ``report`` to a JSON file at ``output_path``.

    The function writes a hand-crafted dict rather than relying solely on
    ``dataclasses.asdict(report)`` so it can include the pre-computed summary
    properties (``total_reclaimable_bytes``, ``zero_risk_bytes``, etc.) that
    live as ``@property`` methods on ``ScanReport`` and are not automatically
    included by ``asdict``.

    Parameters
    ----------
    report : ScanReport
        The scan result to serialise.  May be a redacted copy (via
        ``utils.redact_report``) when ``--redact`` is active.
    output_path : Path
        Destination file path.  Parent directories must exist.
        The file is overwritten if it already exists.
    """
    data = {
        # Top-level system metadata
        "system_os": report.system_os,
        "hostname": report.hostname,
        "total_disk_bytes": report.total_disk_bytes,
        "free_disk_bytes": report.free_disk_bytes,
        "scan_duration_sec": report.scan_duration_sec,

        # Pre-computed breakdown totals — handy for quick summaries without
        # having to re-aggregate the findings list.
        "summary": {
            "total_reclaimable_bytes": report.total_reclaimable_bytes,
            "zero_risk_bytes": report.zero_risk_bytes,
            "safe_cache_bytes": report.safe_cache_bytes,
            "review_required_bytes": report.review_required_bytes,
        },

        # Full finding list — ``asdict`` converts all fields including nested
        # dataclasses and Enum members to plain Python types.
        "findings": [asdict(f) for f in report.findings],
    }

    # Write with UTF-8 encoding and pretty-print indentation.
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
