"""IDE and editor bloat scanner (VS Code, Cursor, Windsurf, JetBrains)."""

import json
import os
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_app_data_dir, get_dir_size, get_home_dir, get_local_cache_dir


class IDEScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "ides_editors"

    @property
    def description(self) -> str:
        return "Scans IDEs for orphaned workspace records, installer leftovers, and build/render caches"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        app_data = get_app_data_dir()
        cache_dir = get_local_cache_dir()

        # Target IDE configurations across platforms
        ide_targets = {
            "VS Code": {
                "data": app_data / "Code",
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
                continue

            # 1. Orphaned Workspace Storage
            ws_storage = ide_data / "User" / "workspaceStorage"
            if ws_storage.exists():
                orphans, orphan_size = self._find_orphaned_workspaces(ws_storage)
                if orphans and orphan_size > 5 * 1024 * 1024:  # > 5MB
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
                            "that no longer exist on your filesystem."
                        ),
                        cleanup_command=f"# Run devsweep with cleanup to purge {len(orphans)} dead workspace entries"
                    ))

            # 2. Cached Extension Installers (VSIXs)
            vsix_dir = ide_data / "CachedExtensionVSIXs"
            if vsix_dir.exists():
                vsix_size = get_dir_size(vsix_dir)
                if vsix_size > 10 * 1024 * 1024:  # > 10MB
                    findings.append(Finding(
                        id=f"{ide_name.lower()}_cached_vsix",
                        title=f"{ide_name} Cached Extension Installers",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(vsix_dir),
                        size_bytes=vsix_size,
                        description="Temporary downloaded extension installation packages that are already installed.",
                        cleanup_command=f"rm -rf \"{vsix_dir}\"/*"
                    ))

            # 3. WebStorage & Chromium Render Caches
            web_storage = ide_data / "WebStorage"
            code_cache = ide_data / "Cache"
            web_size = get_dir_size(web_storage) if web_storage.exists() else 0
            cache_size = get_dir_size(code_cache) if code_cache.exists() else 0
            combined_web_cache = web_size + cache_size

            if combined_web_cache > 100 * 1024 * 1024:  # > 100MB
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
                    description="Temporary cached webview renders and network cache (markdown preview, git graph, etc.).",
                    cleanup_command=" && ".join(clean_paths)
                ))

            # 4. C/C++ Symbol Browsing Cache (vscode-cpptools)
            cpp_cache = cache_dir / "vscode-cpptools"
            if cpp_cache.exists():
                cpp_size = get_dir_size(cpp_cache)
                if cpp_size > 50 * 1024 * 1024:
                    findings.append(Finding(
                        id="vscode_cpptools_cache",
                        title="VS Code C/C++ Intellisense Browsing Cache",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(cpp_cache),
                        size_bytes=cpp_size,
                        description="C/C++ indexing database (.ipch symbols). Rebuilds automatically on project open.",
                        cleanup_command=f"rm -rf \"{cpp_cache}\"/*"
                    ))

        # 5. JetBrains IDE Caches
        jb_cache_dirs = [
            cache_dir / "JetBrains",
            home / ".cache" / "JetBrains",
        ]
        for jb_dir in jb_cache_dirs:
            if jb_dir.exists():
                jb_size = get_dir_size(jb_dir)
                if jb_size > 100 * 1024 * 1024:
                    findings.append(Finding(
                        id="jetbrains_system_caches",
                        title="JetBrains IDE System & Index Caches",
                        category=Category.IDES_EDITORS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(jb_dir),
                        size_bytes=jb_size,
                        description="IntelliJ / PyCharm / WebStorm system indices and compilation caches.",
                        cleanup_command=f"rm -rf \"{jb_dir}\"/*"
                    ))

        return findings

    def _find_orphaned_workspaces(self, ws_storage_path: Path) -> Tuple[List[str], int]:
        """Scan workspace storage and identify orphaned folders."""
        orphans = []
        total_size = 0

        try:
            for item in os.listdir(ws_storage_path):
                entry_path = ws_storage_path / item
                if not entry_path.is_dir():
                    continue

                ws_file = entry_path / "workspace.json"
                if not ws_file.exists():
                    continue

                try:
                    with open(ws_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    folder_uri = data.get("folder") or data.get("workspace")
                    if folder_uri and folder_uri.startswith("file://"):
                        unquoted = urllib.parse.unquote(folder_uri[7:])
                        # On Windows, file:///C:/path -> strip leading slash if needed
                        if os.name == "nt" and unquoted.startswith("/") and len(unquoted) > 2 and unquoted[2] == ":":
                            unquoted = unquoted[1:]

                        if not os.path.exists(unquoted):
                            sz = get_dir_size(entry_path)
                            orphans.append(str(entry_path))
                            total_size += sz
                except Exception:
                    continue
        except Exception:
            pass

        return orphans, total_size
