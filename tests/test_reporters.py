"""
tests.test_reporters
=====================

Regression tests for the devsweep reporter pipeline.

What is tested
--------------
* **Redaction** — ``utils.redact_report`` correctly replaces the hostname and
  home-directory path without mutating the original report.
* **JSON serialisation** — ``generate_json_report`` produces valid JSON with
  enum values serialised as their string names.
* **POSIX cleanup script** — ``generate_cleanup_script`` includes safe-tier
  commands and correctly quotes labels with embedded single quotes.
  REQUIRES_REVIEW commands must be excluded.
* **Windows PowerShell script** — ``generate_cleanup_script`` on Windows
  produces a PowerShell script that includes safe-tier commands and excludes
  REQUIRES_REVIEW items.

All tests use temporary directories (``tempfile.TemporaryDirectory``) so they
leave no artefacts on disk.  Platform-specific code branches (``is_windows``)
are exercised via ``unittest.mock.patch`` so tests run on any OS.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devsweep.core.models import Category, Finding, SafetyLevel, ScanReport
from devsweep.core.utils import redact_report
from devsweep.reporters.json_rep import generate_json_report
from devsweep.reporters.script_gen import generate_cleanup_script


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def sample_report() -> ScanReport:
    """Return a minimal ``ScanReport`` with one SAFE_CACHE and one REQUIRES_REVIEW finding.

    The SAFE_CACHE finding has a command that should appear in generated scripts.
    The REQUIRES_REVIEW finding must *not* appear in any generated script.
    """
    return ScanReport(
        system_os="test-os",
        hostname="test-host",
        total_disk_bytes=1000,
        free_disk_bytes=500,
        scan_duration_sec=0.01,
        findings=[
            Finding(
                "cache",
                # Label contains a single quote — tests that POSIX quoting is correct.
                "Bob's cache",
                Category.PROJECTS,
                SafetyLevel.SAFE_CACHE,
                "/tmp/cache",
                100,
                "Rebuildable test cache",
                "npm cache clean --force",
            ),
            Finding(
                "review",
                "A VM",
                Category.VIRTUALIZATION,
                SafetyLevel.REQUIRES_REVIEW,
                "/tmp/vm",
                200,
                "Must not be automated",
                "docker system prune -a --volumes",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class ReporterTests(unittest.TestCase):

    def test_redaction_hides_hostname_and_home_path(self):
        """redact_report must replace hostname and home path without mutating the original."""
        report = sample_report()
        # Set up a realistic private path inside the report.
        report.hostname = "private-machine"
        report.findings[0].path = str(Path.home() / "private-cache")
        report.findings[0].cleanup_command = "rm -rf " + str(Path.home() / "private-cache")

        redacted = redact_report(report)

        # Redacted report must hide the sensitive data.
        self.assertEqual(redacted.hostname, "<redacted>")
        expected_path = str(Path("~") / "private-cache")
        self.assertEqual(redacted.findings[0].path, expected_path)
        self.assertNotIn(str(Path.home()), redacted.findings[0].cleanup_command)

        # The original report must be unchanged (redact_report must not mutate).
        self.assertEqual(report.hostname, "private-machine")

    def test_json_report_serializes_enum_values(self):
        """generate_json_report must write enum values as their string names, not integers."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            generate_json_report(sample_report(), output)
            data = json.loads(output.read_text(encoding="utf-8"))

        # Enum values should be serialised as the human-readable string name.
        self.assertEqual(data["findings"][0]["safety"], "SAFE_CACHE")
        self.assertEqual(data["findings"][0]["category"], "Project Artifacts & Repositories")

    def test_posix_script_includes_review_items_with_individual_prompts(self):
        """POSIX script must include Tier 3 REQUIRES_REVIEW items, each with its own prompt."""
        with tempfile.TemporaryDirectory() as directory:
            with patch("devsweep.reporters.script_gen.is_windows", return_value=False):
                output = Path(directory) / "cleanup.sh"
                generate_cleanup_script(sample_report(), output)
                script = output.read_text(encoding="utf-8")

        # The label "Bob's cache" must be safely quoted in the echo call.
        self.assertIn("Bob'\\''s cache", script)
        # The safe cache npm command must appear in the Tier 2 block.
        self.assertIn("npm cache clean --force", script)
        # The REQUIRES_REVIEW docker command must appear in Tier 3 (it is now included).
        self.assertIn("docker system prune -a --volumes", script)
        # Tier 3 must use an individual per-item prompt, not the bulk Tier 1/2 confirm.
        self.assertIn("TIER 3", script)
        self.assertIn("Delete this? [y/N]", script)

    def test_windows_script_includes_review_items_with_individual_prompts(self):
        """PowerShell script must include Tier 3 REQUIRES_REVIEW items with individual prompts."""
        with tempfile.TemporaryDirectory() as directory:
            with patch("devsweep.reporters.script_gen.is_windows", return_value=True):
                output = Path(directory) / "cleanup.ps1"
                generate_cleanup_script(sample_report(), output)
                script = output.read_text(encoding="utf-8")

        # PowerShell scripts must use $ErrorActionPreference (PS-specific).
        self.assertIn("$ErrorActionPreference", script)
        # Safe cache commands should be present.
        self.assertIn("npm cache clean --force", script)
        # Tier 3 section must be present.
        self.assertIn("Tier 3", script)
        # The per-item prompt must be used for review items.
        self.assertIn("Delete this? [y/N]", script)


if __name__ == "__main__":
    unittest.main()
