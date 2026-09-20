"""
tests.test_cli
==============

Tests for devsweep CLI entry points, argument parsing, and exit codes.
"""

import sys
import unittest
from unittest.mock import patch

from devsweep.cli import main


class CLITests(unittest.TestCase):
    """Test CLI argument parsing and execution."""

    def test_cli_help_exits_cleanly(self):
        """--help must exit with code 0 without raising exceptions."""
        with patch.object(sys, "argv", ["devsweep", "--help"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)

    def test_cli_version_exits_cleanly(self):
        """--version must exit with code 0."""
        with patch.object(sys, "argv", ["devsweep", "--version"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
