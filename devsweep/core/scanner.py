"""
devsweep.core.scanner
=====================

Abstract base class (ABC) for all devsweep scanner modules.

How to add a new scanner
------------------------
1. Create a new file under ``devsweep/modules/``, e.g. ``my_tool.py``.
2. Define a class that inherits from ``BaseScanner``.
3. Implement the three abstract members:

   * ``name``        — a short snake_case identifier (e.g. ``"my_tool"``)
   * ``description`` — one sentence describing what is inspected
   * ``scan()``      — the actual inspection logic; must return a list of
                       ``Finding`` objects and must **never** delete or
                       modify any files.

4. Import and add your scanner to the list in ``devsweep/cli.py``.

Example skeleton
----------------
::

    from devsweep.core.models import Category, Finding, SafetyLevel
    from devsweep.core.scanner import BaseScanner
    from devsweep.core.utils import get_dir_size, get_home_dir

    class MyToolScanner(BaseScanner):
        @property
        def name(self) -> str:
            return "my_tool"

        @property
        def description(self) -> str:
            return "Scans ~/.mytool cache for stale downloads"

        def scan(self) -> list:
            findings = []
            cache = get_home_dir() / ".mytool" / "cache"
            if cache.exists():
                sz = get_dir_size(cache)
                if sz > 50 * 1024 * 1024:   # only report when > 50 MB
                    findings.append(Finding(
                        id="my_tool_cache",
                        title="MyTool Download Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(cache),
                        size_bytes=sz,
                        description="Cached packages from mytool installs.",
                        cleanup_command="mytool cache purge",
                    ))
            return findings
"""

from abc import ABC, abstractmethod
from typing import List

from devsweep.core.models import Finding


class BaseScanner(ABC):
    """Abstract base class that every scanner module must implement.

    All concrete scanners are registered in ``cli.py`` and invoked through
    this interface so the CLI does not need to know the internal details of
    any specific scanner.

    **Contract for implementors**

    * ``scan()`` MUST be non-destructive — read-only filesystem operations only.
    * ``scan()`` MUST handle ``PermissionError`` and ``OSError`` internally and
      continue gracefully rather than crashing.
    * ``scan()`` SHOULD only emit a ``Finding`` when the reclaimable size
      exceeds a meaningful threshold (the modules use 20–500 MB depending on
      context) to avoid noise in reports.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short snake_case identifier for this scanner (e.g. ``"npm_cache"``).

        Used in error messages when a scanner fails so the user can identify
        which module had a problem.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """One-sentence human-readable summary of what this scanner inspects.

        Shown in verbose / debug output.  Keep it concise.
        """

    @abstractmethod
    def scan(self) -> List[Finding]:
        """Execute a non-destructive inspection and return discovered findings.

        Returns
        -------
        list of Finding
            May be empty if nothing reclaimable was found or if the relevant
            tooling is not installed.  Must never be ``None``.

        Raises
        ------
        Exception
            Callers (``cli.main``) wrap each ``scan()`` call in a try/except so
            a single misbehaving module cannot crash the whole run.  Modules
            *should* still catch expected errors (``PermissionError``, missing
            binaries, JSON decode errors) themselves and either skip the
            affected path or log a warning finding.
        """
