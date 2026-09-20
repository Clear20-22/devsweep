"""JSON report generator for devsweep."""

import json
from dataclasses import asdict
from pathlib import Path
from devsweep.core.models import ScanReport


def generate_json_report(report: ScanReport, output_path: Path):
    """Serialize scan report to JSON file."""
    data = {
        "system_os": report.system_os,
        "hostname": report.hostname,
        "total_disk_bytes": report.total_disk_bytes,
        "free_disk_bytes": report.free_disk_bytes,
        "scan_duration_sec": report.scan_duration_sec,
        "summary": {
            "total_reclaimable_bytes": report.total_reclaimable_bytes,
            "zero_risk_bytes": report.zero_risk_bytes,
            "safe_cache_bytes": report.safe_cache_bytes,
            "review_required_bytes": report.review_required_bytes,
        },
        "findings": [asdict(f) for f in report.findings]
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
