"""
devsweep.core.utils
===================

Cross-platform helper functions used by scanner modules and reporters.

This module is intentionally kept free of any scanner logic so it can be
imported by every layer of the pipeline without creating circular imports.

Public API
----------
* ``get_os()``              — OS identifier string
* ``is_macos()`` / ``is_windows()`` / ``is_linux()`` — platform predicates
* ``get_home_dir()``        — current user's home directory
* ``get_app_data_dir()``    — platform-specific Application Support / AppData
* ``get_local_cache_dir()`` — platform-specific user cache directory
* ``get_file_allocated_size(path)`` — physical disk allocation for one file
* ``get_dir_size(path)``    — recursive physical allocation for a directory
* ``get_disk_usage(path)``  — (total, used, free) bytes for a mount point
* ``format_bytes(n)``       — human-readable byte string
* ``redact_report(report)`` — return a copy with hostname + home paths removed
"""

import os
import platform
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional, Tuple

from devsweep.core.models import Finding, ScanReport


# ---------------------------------------------------------------------------
# Platform detection helpers
# ---------------------------------------------------------------------------

def get_os() -> str:
    """Return a normalised OS identifier: ``'macos'``, ``'linux'``, or ``'windows'``.

    Derived from ``sys.platform`` rather than ``platform.system()`` so it
    works consistently inside virtual environments and CI containers.
    """
    sys_plat = sys.platform.lower()
    if sys_plat.startswith("darwin"):
        return "macos"
    elif sys_plat.startswith("win"):
        return "windows"
    return "linux"  # Covers 'linux', 'linux2', FreeBSD, etc.


def is_macos() -> bool:
    """Return ``True`` when running on macOS / Darwin."""
    return get_os() == "macos"


def is_windows() -> bool:
    """Return ``True`` when running on Windows."""
    return get_os() == "windows"


def is_linux() -> bool:
    """Return ``True`` when running on Linux (or any POSIX non-macOS OS)."""
    return get_os() == "linux"


# ---------------------------------------------------------------------------
# Standard directory resolution — always use these instead of hard-coding
# paths so the code works for every user on every OS.
# ---------------------------------------------------------------------------

def get_home_dir() -> Path:
    """Return the current user's home directory as a ``pathlib.Path``.

    Equivalent to ``~`` in the shell.  Uses ``Path.home()`` which reads the
    ``HOME`` environment variable on POSIX and ``USERPROFILE`` on Windows.
    """
    return Path.home()


def get_app_data_dir() -> Path:
    """Return the platform-specific application configuration directory.

    * macOS   → ``~/Library/Application Support``
    * Windows → ``%APPDATA%`` (e.g. ``C:\\Users\\Name\\AppData\\Roaming``)
    * Linux   → ``~/.config``

    IDEs and apps typically store their settings and workspace databases here.
    """
    home = get_home_dir()
    if is_macos():
        return home / "Library" / "Application Support"
    elif is_windows():
        # %APPDATA% is set by Windows; fall back to the canonical path if not.
        appdata = os.environ.get("APPDATA")
        return Path(appdata) if appdata else home / "AppData" / "Roaming"
    return home / ".config"


def get_local_cache_dir() -> Path:
    """Return the platform-specific user *cache* directory.

    * macOS   → ``~/Library/Caches``
    * Windows → ``%LOCALAPPDATA%`` (e.g. ``C:\\Users\\Name\\AppData\\Local``)
    * Linux   → ``~/.cache``

    This is where toolchains and browsers write download and build caches.
    """
    home = get_home_dir()
    if is_macos():
        return home / "Library" / "Caches"
    elif is_windows():
        # %LOCALAPPDATA% differs from %APPDATA% — it is machine-local storage.
        localappdata = os.environ.get("LOCALAPPDATA")
        return Path(localappdata) if localappdata else home / "AppData" / "Local"
    return home / ".cache"


# ---------------------------------------------------------------------------
# Disk-size calculation
# ---------------------------------------------------------------------------

def get_file_allocated_size(path: Path) -> int:
    """Return the **physical allocated** disk size of a single file in bytes.

    Why not just ``os.path.getsize``?
    ``os.path.getsize`` (and ``stat().st_size``) returns the *logical* file
    size — the number of bytes of content — not the number of bytes actually
    stored on disk.  Sparse files (like Docker's ``Docker.raw`` or QEMU's
    ``.qcow2``) have a large logical size but a much smaller physical
    footprint because most of their blocks are holes.

    On POSIX systems, ``stat().st_blocks`` returns the count of 512-byte
    filesystem blocks actually allocated.  Multiplying by 512 gives the true
    on-disk footprint.

    On Windows (no ``st_blocks``), we fall back to ``st_size`` — acceptable
    because Windows doesn't expose sparse-file allocation through the standard
    ``stat`` API.
    """
    try:
        st = os.stat(path)
        if hasattr(st, "st_blocks") and st.st_blocks > 0:
            # st_blocks is in 512-byte units regardless of filesystem block size.
            allocated = st.st_blocks * 512
            # For a non-sparse file, allocated ≥ st_size (due to block rounding).
            # For a sparse file, allocated < st_size, so we return the smaller
            # allocated value to accurately reflect on-disk usage.
            return min(allocated, st.st_size) if allocated < st.st_size else allocated
        return st.st_size
    except (OSError, PermissionError):
        # File disappeared, is a broken symlink, or is not accessible.
        return 0


def get_dir_size(path: Path, max_depth: Optional[int] = None) -> int:
    """Recursively calculate the physical allocated size of a directory in bytes.

    Handles the following edge cases:
    * **Permission errors** on individual files or subdirectories are silently
      skipped so a single unreadable file doesn't abort the whole measurement.
    * **Symlinks** are never followed (``followlinks=False``) to prevent
      circular directory structures from causing an infinite loop.
    * **Sparse virtual disks** are measured by allocated blocks, not logical
      size (see ``get_file_allocated_size``).
    * **Depth limit** — pass ``max_depth=N`` to stop recursing after N levels.
      Useful for project scanners that only need a shallow look.

    Parameters
    ----------
    path : Path
        Directory (or single file) to measure.
    max_depth : int, optional
        Maximum recursion depth relative to ``path``.  ``None`` means unlimited.

    Returns
    -------
    int
        Total physical bytes allocated on disk.  Returns 0 if ``path`` does
        not exist.
    """
    if not path.exists():
        return 0

    # Single-file fast path — no need to walk a tree.
    if path.is_file():
        return get_file_allocated_size(path)

    total_size = 0
    # ``len(path.parts)`` is the "base depth" — we measure relative to this.
    base_depth = len(path.parts)

    try:
        for root, dirs, files in os.walk(path, followlinks=False):
            # Check depth before processing this level.
            current_depth = len(Path(root).parts) - base_depth
            if max_depth is not None and current_depth > max_depth:
                dirs.clear()  # Prevent os.walk from descending further.
                continue

            for f in files:
                file_path = os.path.join(root, f)
                try:
                    # Skip symlinks — their targets may already be counted
                    # elsewhere, or could point outside the directory tree.
                    if not os.path.islink(file_path):
                        total_size += get_file_allocated_size(Path(file_path))
                except (OSError, PermissionError):
                    continue  # Unreadable file — skip and continue.
    except (OSError, PermissionError):
        pass  # Unreadable root directory — return whatever we collected so far.

    return total_size


def get_disk_usage(path: Optional[Path] = None) -> Tuple[int, int, int]:
    """Return ``(total_bytes, used_bytes, free_bytes)`` for the filesystem mount.

    Uses the mount that contains ``path`` (defaults to the home directory).
    This gives a meaningful free-space number relative to where the user's
    files typically live.

    Returns ``(0, 0, 0)`` on any error to avoid crashing the report.
    """
    target = path or get_home_dir()
    try:
        usage = shutil.disk_usage(str(target))
        return usage.total, usage.used, usage.free
    except Exception:
        return 0, 0, 0


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_bytes(size_bytes: int) -> str:
    """Format a byte count as a human-readable string.

    Uses the most readable unit:
    * ≥ 1 GiB → ``"X.XX GB"``
    * ≥ 1 MiB → ``"X.X MB"``
    * ≥ 1 KiB → ``"X.X KB"``
    * otherwise → ``"X B"``
    """
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


# ---------------------------------------------------------------------------
# Privacy / redaction
# ---------------------------------------------------------------------------

def redact_report(report: ScanReport) -> ScanReport:
    """Return a **copy** of ``report`` with hostname and home-directory path removed.

    This is used when the user passes ``--redact`` on the CLI so they can
    safely share terminal output, JSON, or Markdown reports without exposing:
    * their hostname (replaced with ``"<redacted>"``)
    * their home directory path (replaced with ``"~"``)

    **The original report object is never modified.**  Cleanup scripts are
    generated from the unredacted original so the embedded commands still
    contain usable absolute paths.

    Implementation uses ``dataclasses.replace`` (shallow copy with field
    overrides) on both the ``ScanReport`` and each ``Finding`` so the caller
    never needs to worry about which fields contain paths.
    """
    home_text = str(get_home_dir())

    def _redact_str(value: str) -> str:
        """Replace the literal home-directory path with ``~``."""
        return value.replace(home_text, "~")

    # Build a new list of Finding objects with paths replaced.
    redacted_findings = [
        replace(
            finding,
            path=_redact_str(finding.path),
            cleanup_command=_redact_str(finding.cleanup_command),
            # Also redact any path values stored in the metadata dict.
            metadata={key: _redact_str(value) for key, value in finding.metadata.items()},
        )
        for finding in report.findings
    ]

    # Return a new ScanReport with the redacted hostname and findings.
    return replace(report, hostname="<redacted>", findings=redacted_findings)
