#!/usr/bin/env python3
"""
devsweep — top-level entry-point script.

This file allows the tool to be run directly from the repository root without
installing the package:

    python3 devsweep.py

It adds the repository root to ``sys.path`` so Python can find the ``devsweep``
package directory, then delegates immediately to ``devsweep.cli.main``.

If you have installed the package (via ``pip install -e .`` or
``pip install devsweep``), you can also run it as:

    devsweep          # via the console_scripts entry point in pyproject.toml
    python -m devsweep.cli  # via the module interface
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repository root is on sys.path so `import devsweep` works even
# when the package is not installed in the active Python environment.
# This is a no-op if the package is already installed (the installed location
# takes precedence), but it makes standalone `python3 devsweep.py` work
# without any `pip install` step.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from devsweep.cli import main

if __name__ == "__main__":
    main()
