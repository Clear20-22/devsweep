#!/usr/bin/env python3
"""
devsweep: Non-destructive developer bloat and storage auditor.
Run directly with standard python3: python3 devsweep.py
"""

import sys
from pathlib import Path

# Add package directory to sys.path so it runs standalone seamlessly
sys.path.insert(0, str(Path(__file__).parent))

from devsweep.cli import main

if __name__ == "__main__":
    main()
