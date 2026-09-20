"""
tests.test_scanners
===================

Unit tests for devsweep scanner modules, including LanguageRuntimeScanner
and DataScienceScanner.

All tests use temporary directories and monkeypatched home/cache paths to
ensure no real filesystem state is modified or read during tests.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devsweep.core.models import Category, SafetyLevel
from devsweep.modules.ai_ml import AIMLScanner
from devsweep.modules.containers import ContainerScanner
from devsweep.modules.data_science import DataScienceScanner
from devsweep.modules.ides import IDEScanner
from devsweep.modules.language_runtimes import LanguageRuntimeScanner
from devsweep.modules.package_managers import PackageManagerScanner
from devsweep.modules.projects import ProjectScanner
from devsweep.modules.system_browsers import SystemBrowserScanner


class ScannerInterfaceTests(unittest.TestCase):
    """Verify all scanners implement the required BaseScanner properties and methods."""

    def test_all_scanners_instantiate_and_expose_metadata(self):
        scanners = [
            IDEScanner(),
            PackageManagerScanner(),
            ContainerScanner(),
            AIMLScanner(),
            SystemBrowserScanner(),
            LanguageRuntimeScanner(),
            DataScienceScanner(),
            ProjectScanner(),
        ]

        for s in scanners:
            self.assertTrue(isinstance(s.name, str) and len(s.name) > 0)
            self.assertTrue(isinstance(s.description, str) and len(s.description) > 0)


class LanguageRuntimeScannerTests(unittest.TestCase):
    """Test LanguageRuntimeScanner detection of Bun, Zig, Deno, Dart caches."""

    def test_bun_cache_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bun_cache = home / ".bun" / "install" / "cache"
            bun_cache.mkdir(parents=True)

            # Create mock large file exceeding 50 MB threshold
            dummy_file = bun_cache / "dummy.pkg"
            dummy_file.write_bytes(b"x" * 1024)

            scanner = LanguageRuntimeScanner()
            with (
                patch("devsweep.modules.language_runtimes.get_home_dir", return_value=home),
                patch("devsweep.modules.language_runtimes.get_dir_size", return_value=60 * 1024 * 1024),
            ):
                findings = scanner.scan()

            bun_findings = [f for f in findings if f.id == "bun_install_cache"]
            self.assertEqual(len(bun_findings), 1)
            self.assertEqual(bun_findings[0].category, Category.PACKAGE_MANAGERS)
            self.assertEqual(bun_findings[0].safety, SafetyLevel.SAFE_CACHE)
            self.assertIn("bun pm cache rm", bun_findings[0].cleanup_command)

    def test_dart_pub_cache_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            pub_cache = home / ".pub-cache"
            pub_cache.mkdir(parents=True)

            scanner = LanguageRuntimeScanner()
            with (
                patch("devsweep.modules.language_runtimes.get_home_dir", return_value=home),
                patch("devsweep.modules.language_runtimes.get_dir_size", return_value=120 * 1024 * 1024),
            ):
                findings = scanner.scan()

            pub_findings = [f for f in findings if f.id == "dart_pub_cache"]
            self.assertEqual(len(pub_findings), 1)
            self.assertEqual(pub_findings[0].safety, SafetyLevel.SAFE_CACHE)
            self.assertIn("dart pub cache clean", pub_findings[0].cleanup_command)


class DataScienceScannerTests(unittest.TestCase):
    """Test DataScienceScanner detection of Conda, Jupyter, Composer caches."""

    def test_conda_pkg_tarballs_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            conda_pkgs = home / "miniconda3" / "pkgs"
            conda_pkgs.mkdir(parents=True)

            scanner = DataScienceScanner()
            with (
                patch("devsweep.modules.data_science.get_home_dir", return_value=home),
                patch("devsweep.modules.data_science.get_dir_size", return_value=200 * 1024 * 1024),
            ):
                findings = scanner.scan()

            conda_findings = [f for f in findings if f.id == "conda_pkg_cache"]
            self.assertEqual(len(conda_findings), 1)
            self.assertEqual(conda_findings[0].category, Category.AI_ML)
            self.assertEqual(conda_findings[0].safety, SafetyLevel.SAFE_CACHE)
            self.assertIn("conda clean --all -y", conda_findings[0].cleanup_command)

    def test_jupyter_share_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            jupyter_share = home / ".local" / "share" / "jupyter"
            jupyter_share.mkdir(parents=True)

            scanner = DataScienceScanner()
            with (
                patch("devsweep.modules.data_science.get_home_dir", return_value=home),
                patch("devsweep.modules.data_science.get_dir_size", return_value=150 * 1024 * 1024),
            ):
                findings = scanner.scan()

            jupyter_findings = [f for f in findings if f.id == "jupyter_share"]
            self.assertEqual(len(jupyter_findings), 1)
            self.assertEqual(jupyter_findings[0].category, Category.AI_ML)
            self.assertEqual(jupyter_findings[0].safety, SafetyLevel.SAFE_CACHE)
            self.assertIn("jupyter lab clean --all", jupyter_findings[0].cleanup_command)


if __name__ == "__main__":
    unittest.main()
