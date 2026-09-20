"""
devsweep.modules.ides
=====================

Scanner for IDE and editor bloat: orphaned workspace records, cached extension
installers, web-view render caches, and symbol-browsing databases.

What is inspected
-----------------
**VS Code–family IDEs** (VS Code, Cursor, Windsurf, VSCodium):
  Each IDE stores per-workspace state in ``<AppData>/<IDE>/User/workspaceStorage/``.
  Every entry is a hashed folder containing a ``workspace.json`` that records the
  absolute path to the project directory.  When you delete or move a project, the
  IDE does not clean up its workspace database entry.  These orphaned entries
  accumulate over time — this scanner finds them.

  Also inspected per IDE:
  * ``CachedExtensionVSIXs`` — downloaded extension `.vsix` installers that are
    no longer needed after installation.
  * ``WebStorage`` + ``Cache`` — Chromium renderer caches used for markdown
    preview, git-graph extensions, and similar web-view features.

**C/C++ IntelliSense** (vscode-cpptools):
  ``~/.cache/vscode-cpptools`` holds the intelliSense browsing database
  (``.ipch`` files).  It rebuilds automatically when you open a C/C++ project.

**JetBrains IDEs** (IntelliJ, PyCharm, WebStorm, GoLand, etc.):
  JetBrains stores system caches in ``~/Library/Caches/JetBrains`` (macOS) or
  ``~/.cache/JetBrains`` (Linux).  These include module indices, compilation
  caches, and gradle/maven daemon files.

Orphaned workspace detection algorithm
---------------------------------------
1. Enumerate every hash-named subdirectory under ``workspaceStorage/``.
2. Read ``workspace.json`` inside each one.
3. Extract the ``folder`` (single-root workspace) or ``workspace`` (multi-root)
   URI — these are ``file://`` URIs pointing to the project directory.
4. URL-decode the path and check ``os.path.exists()``.
5. If the path no longer exists on disk → the entry is orphaned.
"""

import json
import os
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import (
    get_app_data_dir,
    get_dir_size,
    get_home_dir,
    get_local_cache_dir,
    is_macos,
)


class IDEScanner(BaseScanner):
    """Scanner for IDE and editor storage bloat."""

    @property
    def name(self) -> str:
        return "ides_editors"

    @property
    def description(self) -> str:
        return (
            "Scans IDEs for orphaned workspace records, installer leftovers, "
            "and build/render caches"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        app_data = get_app_data_dir()
        cache_dir = get_local_cache_dir()

        # ------------------------------------------------------------------
        # VS Code–family IDEs
        #
        # Each entry maps an IDE name to its data/cache directory locations.
        # The ``data`` directory holds settings and workspaceStorage;
        # the ``cache`` directory holds Chromium render artefacts.
        # ------------------------------------------------------------------
        ide_targets = {
            "VS Code": {
                "data": app_data / "Code",
                # macOS uses a reverse-DNS bundle identifier for the cache dir;
                # Linux/Windows use the plain product name.
                "cache": cache_dir / "com.microsoft.VSCode" if is_macos() else cache_dir / "Code",
            },
            "Cursor": {
                "data": app_data / "Cursor",
                "cache": cache_dir / "Cursor",
            },
            "Windsurf": {
                "data": app_data / "Windsurf",
                "cache": cache_dir / "Windsurf",
            },
            "VSCodium": {
                "data": app_data / "VSCodium",
                "cache": cache_dir / "VSCodium",
            },
        }

        for ide_name, paths in ide_targets.items():
            ide_data = paths["data"]
            if not ide_data.exists():
                # This IDE is not installed — skip silently.
                continue

            # --------------------------------------------------------------
            # 1. Orphaned workspace storage entries
            #    <AppData>/<IDE>/User/workspaceStorage/<hash>/
            #
            #    Each hash folder contains a `workspace.json` that encodes the
            #    original project path as a `file://` URI.  We decode the URI
            #    and check whether the path still exists.
            # --------------------------------------------------------------
            ws_storage = ide_data / "User" / "workspaceStorage"
            if ws_storage.exists():
                orphans, orphan_size = self._find_orphaned_workspaces(ws_storage)
                if orphans and orphan_size > 5 * 1024 * 1024:  # > 5 MB
                    findings.append(Finding(
                        id=f"{ide_name.lower()}_orphaned_workspaces",
                        title=f"{ide_name} Orphaned Workspaces ({len(orphans)} folders)",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(ws_storage),
                        size_bytes=orphan_size,
                        item_count=len(orphans),
                        description=(
                            f"{len(orphans)} workspace database entries reference project directories "
                            "that no longer exist on your filesystem.  "
                            "These are completely safe to delete."
                        ),
                        cleanup_command=(
                            f"# Run: devsweep --generate-script cleanup.sh  "
                            f"# to auto-purge {len(orphans)} dead workspace entries"
                        ),
                    ))

            # --------------------------------------------------------------
            # 2. Cached extension installer packages (.vsix files)
            #    <AppData>/<IDE>/CachedExtensionVSIXs/
            #
            #    After an extension is installed from the Marketplace, the
            #    original `.vsix` download is left here as a backup.
            #    Extensions are already installed — these installers are dead weight.
            # --------------------------------------------------------------
            vsix_dir = ide_data / "CachedExtensionVSIXs"
            if vsix_dir.exists():
                vsix_size = get_dir_size(vsix_dir)
                if vsix_size > 10 * 1024 * 1024:  # > 10 MB
                    findings.append(Finding(
                        id=f"{ide_name.lower()}_cached_vsix",
                        title=f"{ide_name} Cached Extension Installers",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(vsix_dir),
                        size_bytes=vsix_size,
                        description=(
                            "Temporary downloaded extension installation packages (.vsix). "
                            "The extensions are already installed — these installers serve no purpose."
                        ),
                        cleanup_command=f'rm -rf "{vsix_dir}"/*',
                    ))

            # --------------------------------------------------------------
            # 3. Webview & Chromium render caches
            #    <AppData>/<IDE>/WebStorage/   — IndexedDB / localStorage for webviews
            #    <AppData>/<IDE>/Cache/         — HTTP cache for Chromium renderer
            #
            #    VS Code (and its forks) embed a Chromium renderer for web-view
            #    extensions (markdown preview, git-graph, browser-preview, etc.).
            #    Both folders are automatically rebuilt as you use the IDE.
            # --------------------------------------------------------------
            web_storage = ide_data / "WebStorage"
            code_cache = ide_data / "Cache"
            web_size = get_dir_size(web_storage) if web_storage.exists() else 0
            cache_size = get_dir_size(code_cache) if code_cache.exists() else 0
            combined_web_cache = web_size + cache_size

            if combined_web_cache > 100 * 1024 * 1024:  # > 100 MB combined
                # Build a compound cleanup command that clears all present paths.
                clean_paths = []
                if web_storage.exists():
                    clean_paths.append(f'rm -rf "{web_storage}"/*')
                if code_cache.exists():
                    clean_paths.append(f'rm -rf "{code_cache}"/*')

                findings.append(Finding(
                    id=f"{ide_name.lower()}_webview_cache",
                    title=f"{ide_name} Webview & Chromium Render Cache",
                    category=Category.IDES_EDITORS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(ide_data / "WebStorage"),
                    size_bytes=combined_web_cache,
                    description=(
                        "Temporary cached webview renders and network cache "
                        "(markdown preview, git graph, etc.).  Rebuilds automatically."
                    ),
                    cleanup_command=" && ".join(clean_paths),
                ))

            # --------------------------------------------------------------
            # 4. C/C++ IntelliSense browsing database (vscode-cpptools)
            #    ~/.cache/vscode-cpptools/
            #
            #    The C/C++ extension builds a per-project IntelliSense index
            #    (`.ipch` files) that is shared across workspaces.  It is rebuilt
            #    automatically when you open a C/C++ project in VS Code.
            # --------------------------------------------------------------
            cpp_cache = cache_dir / "vscode-cpptools"
            if cpp_cache.exists():
                cpp_size = get_dir_size(cpp_cache)
                if cpp_size > 50 * 1024 * 1024:  # > 50 MB
                    findings.append(Finding(
                        id="vscode_cpptools_cache",
                        title="VS Code C/C++ Intellisense Browsing Cache",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(cpp_cache),
                        size_bytes=cpp_size,
                        description=(
                            "C/C++ indexing database (.ipch symbols). "
                            "Rebuilds automatically on project open."
                        ),
                        cleanup_command=f'rm -rf "{cpp_cache}"/*',
                    ))

        # ------------------------------------------------------------------
        # 5. JetBrains IDE system & index caches
        #
        #    macOS: ~/Library/Caches/JetBrains/<ProductName><Version>/
        #    Linux: ~/.cache/JetBrains/<ProductName><Version>/
        #
        #    Covers IntelliJ IDEA, PyCharm, WebStorm, GoLand, CLion, etc.
        #    These caches hold compilation outputs, project indices, and
        #    Gradle/Maven daemon files.  They are rebuilt automatically.
        # ------------------------------------------------------------------
        jb_cache_dirs = [
            cache_dir / "JetBrains",        # macOS canonical location
            home / ".cache" / "JetBrains",  # Linux canonical location
        ]
        for jb_dir in jb_cache_dirs:
            if jb_dir.exists():
                jb_size = get_dir_size(jb_dir)
                if jb_size > 100 * 1024 * 1024:  # > 100 MB
                    findings.append(Finding(
                        id="jetbrains_system_caches",
                        title="JetBrains IDE System & Index Caches",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(jb_dir),
                        size_bytes=jb_size,
                        description=(
                            "IntelliJ / PyCharm / WebStorm system indices and compilation caches. "
                            "Rebuilt automatically when the IDE opens the project."
                        ),
                        cleanup_command=f'rm -rf "{jb_dir}"/*',
                    ))

        return findings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_orphaned_workspaces(
        self, ws_storage_path: Path
    ) -> Tuple[List[str], int]:
        """Scan ``workspaceStorage`` and return orphaned folder paths + their total size.

        An entry is considered **orphaned** when the project directory encoded
        in its ``workspace.json`` no longer exists on disk.

        Parameters
        ----------
        ws_storage_path : Path
            Absolute path to the IDE's ``User/workspaceStorage`` directory.

        Returns
        -------
        (orphans, total_size)
            ``orphans``    — list of absolute paths to orphaned hash folders.
            ``total_size`` — combined size in bytes of all orphaned entries.
        """
        orphans = []
        total_size = 0

        try:
            for item in os.listdir(ws_storage_path):
                entry_path = ws_storage_path / item
                if not entry_path.is_dir():
                    continue  # workspaceStorage only contains directories.

                ws_file = entry_path / "workspace.json"
                if not ws_file.exists():
                    continue  # Incomplete or corrupted entry — skip.

                try:
                    with open(ws_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # ``folder`` is set for single-root workspaces;
                    # ``workspace`` is set for multi-root workspace files.
                    folder_uri = data.get("folder") or data.get("workspace")
                    if folder_uri and folder_uri.startswith("file://"):
                        # Remove the ``file://`` prefix and URL-decode percent-encoded chars
                        # (e.g. spaces encoded as %20, non-ASCII path components).
                        unquoted = urllib.parse.unquote(folder_uri[7:])

                        # Windows file URIs look like file:///C:/path → strip leading slash.
                        if (
                            os.name == "nt"
                            and unquoted.startswith("/")
                            and len(unquoted) > 2
                            and unquoted[2] == ":"
                        ):
                            unquoted = unquoted[1:]

                        # If the path doesn't exist → orphaned entry.
                        if not os.path.exists(unquoted):
                            sz = get_dir_size(entry_path)
                            orphans.append(str(entry_path))
                            total_size += sz

                except Exception:
                    # JSON parse error or unexpected schema — skip this entry.
                    continue

        except Exception:
            # Could not list the workspaceStorage directory (permissions, etc.).
            pass

        return orphans, total_size
