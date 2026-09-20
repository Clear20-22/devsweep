"""
devsweep.modules.system_browsers
==================================

Scanner for browser HTTP caches, application updater leftovers, system crash
reports, and the Trash / Recycle Bin.

What is inspected
-----------------
**Browser HTTP caches** (never cookies, passwords, or personal browsing data):
  * Arc Browser cache + Service Worker offline cache
  * Google Chrome cache
  * Brave Browser cache
  * Firefox cache
  * Microsoft Edge cache
  * Safari WebKit cache (macOS sandboxed container)

**Application updater artefacts** (ZERO_RISK — accumulated orphan dumps):
  * Telegram Sparkle updater retained DMGs (macOS) — a known Telegram bug where
    historical update installers are not deleted after applying updates.
  * ``.net/Updates`` assembly dumps — leftover .NET runtime preview assemblies
    created by some .NET tools or Playwright browser managers.

**System diagnostic logs** (ZERO_RISK):
  * ``~/Library/Logs/DiagnosticReports`` (macOS) — ``.ips`` crash reports.
  * ``/var/crash`` (Linux) — core dump files.

**Trash / Recycle Bin**:
  * ``~/.Trash`` (macOS)
  * ``~/.local/share/Trash`` (Linux XDG)

Privacy guarantee
-----------------
Only *cache* directories are inspected — never profile directories, password
stores, extension data, cookies, or bookmarks.  All browser profile data is
intentionally excluded from all path patterns.
"""

import os
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import (
    get_app_data_dir,
    get_dir_size,
    get_home_dir,
    get_local_cache_dir,
    is_macos,
)


class SystemBrowserScanner(BaseScanner):
    """Scanner for browser caches, updater leftovers, crash logs, and Trash."""

    @property
    def name(self) -> str:
        return "system_browsers"

    @property
    def description(self) -> str:
        return (
            "Audits browser disk caches, updater downloads, "
            "crash reports, and system trash"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_cache = get_local_cache_dir()
        app_data = get_app_data_dir()

        # ------------------------------------------------------------------
        # 1. Browser HTTP disk caches
        #
        #    These are Chromium / Gecko network caches — HTML, images, JS,
        #    fonts downloaded while browsing.  They are *never* cookies,
        #    passwords, history, or saved login data.
        #
        #    The threshold is 200 MB to avoid reporting normal-sized caches.
        # ------------------------------------------------------------------
        browser_targets = [
            # (Display name, cache directory path)
            ("Arc Browser Cache", local_cache / "Arc"),
            # macOS Chrome uses a reverse-DNS bundle ID; Linux uses product name.
            (
                "Google Chrome Cache",
                local_cache / "Google" / "Chrome"
                if is_macos()
                else local_cache / "google-chrome",
            ),
            (
                "Brave Browser Cache",
                local_cache / "BraveSoftware" / "Brave-Browser"
                if is_macos()
                else local_cache / "BraveSoftware",
            ),
            (
                "Firefox Cache",
                local_cache / "Firefox"
                if is_macos()
                else local_cache / "mozilla" / "firefox",
            ),
            (
                "Microsoft Edge Cache",
                local_cache / "Microsoft Edge"
                if is_macos()
                else local_cache / "microsoft-edge",
            ),
        ]

        for name, path in browser_targets:
            if path.exists():
                sz = get_dir_size(path)
                if sz > 200 * 1024 * 1024:  # > 200 MB
                    findings.append(Finding(
                        id=f"{name.lower().replace(' ', '_')}",
                        title=name,
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(path),
                        size_bytes=sz,
                        description=(
                            "Temporary HTTP asset and media cache. "
                            "Safely rebuilds as you browse."
                        ),
                        cleanup_command=f'rm -rf "{path}"/*',
                    ))

        # Safari (macOS sandboxed container)
        # Safari runs in an App Sandbox, so its caches are inside a container
        # bundle rather than the standard ~/Library/Caches location.
        if is_macos():
            safari_cache = (
                home
                / "Library"
                / "Containers"
                / "com.apple.Safari"
                / "Data"
                / "Library"
                / "Caches"
            )
            safari_webkit = (
                home
                / "Library"
                / "Containers"
                / "com.apple.Safari"
                / "Data"
                / "Library"
                / "WebKit"
            )
            # Combine both Safari cache folders for a single, comprehensive finding.
            combined_safari = (
                (get_dir_size(safari_cache) if safari_cache.exists() else 0)
                + (get_dir_size(safari_webkit) if safari_webkit.exists() else 0)
            )
            if combined_safari > 200 * 1024 * 1024:
                findings.append(Finding(
                    id="safari_cache_webkit",
                    title="Safari WebKit & HTTP Disk Cache",
                    category=Category.SYSTEM_BROWSERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(safari_cache),
                    size_bytes=combined_safari,
                    description=(
                        "Safari temporary website asset and render caches."
                    ),
                    # Safari's sandboxed container can't be cleared with a plain rm -rf
                    # without disabling SIP, so we guide the user to the Settings UI.
                    cleanup_command=(
                        "# Clear via Safari > Settings > Privacy > Manage Website Data"
                    ),
                ))

        # Arc Browser Service Worker offline cache
        # Arc caches Progressive Web App (PWA) service-worker scripts inside
        # its Application Support directory.  These can grow very large if you
        # use many web apps and rarely clear the browser data.
        arc_sw = app_data / "Arc" / "User Data" / "Default" / "Service Worker"
        if arc_sw.exists():
            sz = get_dir_size(arc_sw)
            if sz > 500 * 1024 * 1024:  # > 500 MB (service worker caches can be huge)
                findings.append(Finding(
                    id="arc_service_worker_cache",
                    title="Arc Browser Service Worker Offline Cache",
                    category=Category.SYSTEM_BROWSERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(arc_sw),
                    size_bytes=sz,
                    description=(
                        "Offline website service worker scripts cached by Arc Browser. "
                        "Rebuilds automatically as you browse."
                    ),
                    cleanup_command=f'rm -rf "{arc_sw}"/*',
                ))

        # ------------------------------------------------------------------
        # 2. Application updater leftovers & build dumps (ZERO_RISK)
        # ------------------------------------------------------------------

        # Telegram Sparkle updater retained DMGs (macOS)
        # Telegram for Mac uses the Sparkle update framework, which has a known
        # bug where it writes each update's DMG to PersistentDownloads and does
        # not delete old entries after applying the update.  The result is a
        # growing collection of historical Telegram installer DMGs.
        if is_macos():
            telegram_updates = (
                home
                / "Library"
                / "Group Containers"
                / "6N38VWS5BX.ru.keepcoder.Telegram"
                / "appstore"
                / "updates"
                / "PersistentDownloads"
            )
            if telegram_updates.exists():
                sz = get_dir_size(telegram_updates)
                if sz > 100 * 1024 * 1024:
                    findings.append(Finding(
                        id="telegram_updater_dumps",
                        title="Telegram Sparkle Updater Retained DMGs",
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(telegram_updates),
                        size_bytes=sz,
                        description=(
                            "Historical auto-update installer packages left behind by "
                            "Telegram's Sparkle updater.  Already applied — completely safe to remove."
                        ),
                        cleanup_command=f'rm -rf "{telegram_updates}"/*',
                    ))

        # .NET Tools / Playwright update assembly dumps
        # Some .NET CLI global tools (including Playwright's browser manager) write
        # temporary preview runtime assemblies to ``~/.net/Updates``.
        # These are not cleaned up after the tool finishes.
        net_updates = home / ".net" / "Updates"
        if net_updates.exists():
            sz = get_dir_size(net_updates)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="dotnet_updates_dumps",
                    title=".NET Tools / Playwright Updates Assembly Dumps",
                    category=Category.SYSTEM_BROWSERS,
                    safety=SafetyLevel.ZERO_RISK,
                    path=str(net_updates),
                    size_bytes=sz,
                    description=(
                        "Historical duplicate .NET preview runtime assemblies "
                        "from .NET global tools or Playwright."
                    ),
                    cleanup_command=f'rm -rf "{net_updates}"/*',
                ))

        # ------------------------------------------------------------------
        # 3. Crash reports & diagnostic core dumps (ZERO_RISK)
        #
        #    macOS writes ``.ips`` crash reports to DiagnosticReports when any
        #    application or the OS itself crashes.  Linux writes core dump files
        #    to /var/crash.  These are safe to delete; the OS generates new
        #    ones for future crashes.
        # ------------------------------------------------------------------
        diag_dirs = [
            home / "Library" / "Logs" / "DiagnosticReports",  # macOS
            Path("/var/crash"),                                  # Linux
        ]
        for d in diag_dirs:
            if d.exists():
                sz = get_dir_size(d)
                if sz > 50 * 1024 * 1024:
                    findings.append(Finding(
                        id="diagnostic_crash_reports",
                        title="System Crash & Diagnostic Core Dumps",
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(d),
                        size_bytes=sz,
                        description=(
                            "Historical system process crash dumps (.ips / core dumps). "
                            "New dumps are created automatically for future crashes."
                        ),
                        cleanup_command=f'rm -rf "{d}"/*',
                    ))

        # ------------------------------------------------------------------
        # 4. System Trash / Recycle Bin
        #
        #    Files here have already been intentionally deleted by the user
        #    but not permanently removed.  We only report when > 100 MB to
        #    avoid nagging about normal everyday use of the Trash.
        # ------------------------------------------------------------------
        trash_paths = [
            home / ".Trash",                          # macOS
            home / ".local" / "share" / "Trash",     # Linux (XDG Base Directory)
        ]
        for t in trash_paths:
            if t.exists():
                sz = get_dir_size(t)
                if sz > 100 * 1024 * 1024:  # > 100 MB
                    findings.append(Finding(
                        id="system_trash",
                        title="System Trash / Recycle Bin",
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(t),
                        size_bytes=sz,
                        description=(
                            "Files already moved to Trash by the user. "
                            "Empty via Finder / Files > Empty Trash, or use the command below."
                        ),
                        cleanup_command=f'rm -rf "{t}"/*',
                    ))
                break  # Only the first existing Trash path is reported.

        return findings
