"""Regression tests for portable, non-destructive report output."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devsweep.core.models import Category, Finding, SafetyLevel, ScanReport
from devsweep.core.utils import redact_report
from devsweep.reporters.json_rep import generate_json_report
from devsweep.reporters.script_gen import generate_cleanup_script


def sample_report():
    return ScanReport(
        system_os="test-os", hostname="test-host", total_disk_bytes=1000,
        free_disk_bytes=500, scan_duration_sec=0.01,
        findings=[
            Finding("cache", "Bob's cache", Category.PROJECTS, SafetyLevel.SAFE_CACHE,
                    "/tmp/cache", 100, "Rebuildable test cache", "npm cache clean --force"),
            Finding("review", "A VM", Category.VIRTUALIZATION, SafetyLevel.REQUIRES_REVIEW,
                    "/tmp/vm", 200, "Must not be automated", "docker system prune -a --volumes"),
        ],
    )


class ReporterTests(unittest.TestCase):
    def test_redaction_hides_hostname_and_home_path(self):
        report = sample_report()
        report.hostname = "private-machine"
        report.findings[0].path = str(Path.home() / "private-cache")
        report.findings[0].cleanup_command = "rm -rf " + str(Path.home() / "private-cache")
        redacted = redact_report(report)
        self.assertEqual(redacted.hostname, "<redacted>")
        self.assertEqual(redacted.findings[0].path, "~/private-cache")
        self.assertNotIn(str(Path.home()), redacted.findings[0].cleanup_command)
        self.assertEqual(report.hostname, "private-machine")

    def test_json_report_serializes_enum_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            generate_json_report(sample_report(), output)
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["findings"][0]["safety"], "SAFE_CACHE")
        self.assertEqual(data["findings"][0]["category"], "Project Artifacts & Repositories")

    def test_posix_script_excludes_review_items_and_quotes_labels(self):
        with tempfile.TemporaryDirectory() as directory, patch("devsweep.reporters.script_gen.is_windows", return_value=False):
            output = Path(directory) / "cleanup.sh"
            generate_cleanup_script(sample_report(), output)
            script = output.read_text(encoding="utf-8")
        self.assertIn("Bob'\\\"'\\\"'s cache", script)
        self.assertIn("npm cache clean --force", script)
        self.assertNotIn("docker system prune -a --volumes", script)

    def test_windows_script_is_powershell_and_excludes_review_items(self):
        with tempfile.TemporaryDirectory() as directory, patch("devsweep.reporters.script_gen.is_windows", return_value=True):
            output = Path(directory) / "cleanup.ps1"
            generate_cleanup_script(sample_report(), output)
            script = output.read_text(encoding="utf-8")
        self.assertIn("$ErrorActionPreference", script)
        self.assertIn("npm cache clean --force", script)
        self.assertNotIn("docker system prune -a --volumes", script)


if __name__ == "__main__":
    unittest.main()
