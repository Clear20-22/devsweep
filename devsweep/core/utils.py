"""Cross-platform utility functions for devsweep."""

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple


def get_os() -> str:
    """Return OS identifier: 'macos', 'linux', or 'windows'."""
    sys_plat = sys.platform.lower()
    if sys_plat.startswith("darwin"):
        return "macos"
    elif sys_plat.startswith("win"):
        return "windows"
    return "linux"


def is_macos() -> bool:
    return get_os() == "macos"


def is_windows() -> bool:
    return get_os() == "windows"


def is_linux() -> bool:
    return get_os() == "linux"


def get_home_dir() -> Path:
    """Return current user home directory."""
    return Path.home()


def get_app_data_dir() -> Path:
    """Return platform-specific Application Support / AppData directory."""
    home = get_home_dir()
    if is_macos():
        return home / "Library" / "Application Support"
    elif is_windows():
        appdata = os.environ.get("APPDATA")
        return Path(appdata) if appdata else home / "AppData" / "Roaming"
    return home / ".config"


def get_local_cache_dir() -> Path:
    """Return platform-specific user cache directory."""
    home = get_home_dir()
    if is_macos():
        return home / "Library" / "Caches"
    elif is_windows():
        localappdata = os.environ.get("LOCALAPPDATA")
        return Path(localappdata) if localappdata else home / "AppData" / "Local"
    return home / ".cache"


def get_file_allocated_size(path: Path) -> int:
    """Return physical allocated disk size in bytes (handles sparse files on macOS/Linux)."""
    try:
        st = os.stat(path)
        # On POSIX, st_blocks is count of 512-byte blocks allocated
        if hasattr(st, "st_blocks") and st.st_blocks > 0:
            allocated = st.st_blocks * 512
            # allocated might slightly exceed st_size due to block alignment; take min unless sparse
            return min(allocated, st.st_size) if allocated < st.st_size else allocated
        return st.st_size
    except (OSError, PermissionError):
        return 0


def get_dir_size(path: Path, max_depth: Optional[int] = None) -> int:
    """
    Calculate total physical allocated size of a directory in bytes, handling permission errors,
    sparse virtual disk files, and skipping symlinks to avoid circular recursion.
    """
    if not path.exists():
        return 0

    if path.is_file():
        return get_file_allocated_size(path)

    total_size = 0
    base_depth = len(path.parts)

    try:
        for root, dirs, files in os.walk(path, followlinks=False):
            current_depth = len(Path(root).parts) - base_depth
            if max_depth is not None and current_depth > max_depth:
                dirs.clear()
                continue

            for f in files:
                file_path = os.path.join(root, f)
                try:
                    if not os.path.islink(file_path):
                        total_size += get_file_allocated_size(Path(file_path))
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass

    return total_size


def get_disk_usage(path: Optional[Path] = None) -> Tuple[int, int, int]:
    """Return (total_bytes, used_bytes, free_bytes) for the given or root mount."""
    target = path or get_home_dir()
    try:
        usage = shutil.disk_usage(str(target))
        return usage.total, usage.used, usage.free
    except Exception:
        return 0, 0, 0


def format_bytes(size_bytes: int) -> str:
    """Format bytes into readable string."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"
