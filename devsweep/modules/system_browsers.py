"""System caches, updater artifacts, crash logs, and browser caches scanner."""

import os
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_app_data_dir, get_dir_size, get_home_dir, get_local_cache_dir, is_macos


class SystemBrowserScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "system_browsers"

    @property
    def description(self) -> str:
        return "Audits browser disk caches, updater downloads, crash reports, and system trash"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_cache = get_local_cache_dir()
        app_data = get_app_data_dir()

        # -------------------------------------------------------------
        # 1. Browser Caches (Only caches, NEVER passwords, cookies, or logins)
        # -------------------------------------------------------------
        browser_targets = [
            ("Arc Browser Cache", local_cache / "Arc"),
            ("Google Chrome Cache", local_cache / "Google" / "Chrome" if is_macos() else local_cache / "google-chrome"),
            ("Brave Browser Cache", local_cache / "BraveSoftware" / "Brave-Browser" if is_macos() else local_cache / "BraveSoftware"),
            ("Firefox Cache", local_cache / "Firefox" if is_macos() else local_cache / "mozilla" / "firefox"),
            ("Microsoft Edge Cache", local_cache / "Microsoft Edge" if is_macos() else local_cache / "microsoft-edge"),
        ]

        for name, path in browser_targets:
            if path.exists():
                sz = get_dir_size(path)
                if sz > 200 * 1024 * 1024:  # > 200MB
                    findings.append(Finding(
                        id=f"{name.lower().replace(' ', '_')}",
                        title=name,
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(path),
                        size_bytes=sz,
                        description="Temporary HTTP asset and media cache. Safely rebuilds as you browse.",
                        cleanup_command=f'rm -rf "{path}"/*'
                    ))

        # Safari (macOS container)
        if is_macos():
            safari_cache = home / "Library" / "Containers" / "com.apple.Safari" / "Data" / "Library" / "Caches"
            safari_webkit = home / "Library" / "Containers" / "com.apple.Safari" / "Data" / "Library" / "WebKit"
            combined_safari = (get_dir_size(safari_cache) if safari_cache.exists() else 0) + \
                              (get_dir_size(safari_webkit) if safari_webkit.exists() else 0)
            if combined_safari > 200 * 1024 * 1024:
                findings.append(Finding(
                    id="safari_cache_webkit",
                    title="Safari WebKit & HTTP Disk Cache",
                    category=Category.SYSTEM_BROWSERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(safari_cache),
                    size_bytes=combined_safari,
                    description="Safari temporary website asset and render caches.",
                    cleanup_command="# Clear via Safari > Settings > Privacy > Manage Website Data, or empty cache folders"
                ))

        # Arc Service Workers
        arc_sw = app_data / "Arc" / "User Data" / "Default" / "Service Worker"
        if arc_sw.exists():
            sz = get_dir_size(arc_sw)
            if sz > 500 * 1024 * 1024:
                findings.append(Finding(
                    id="arc_service_worker_cache",
                    title="Arc Browser Service Worker Offline Cache",
                    category=Category.SYSTEM_BROWSERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(arc_sw),
                    size_bytes=sz,
                    description="Offline website service worker scripts cached by Arc Browser.",
                    cleanup_command=f'rm -rf "{arc_sw}"/*'
                ))

        # -------------------------------------------------------------
        # 2. App Updater Leftovers & Build Dumps
        # -------------------------------------------------------------
        # Telegram Sparkle updater bug (PersistentDownloads)
        if is_macos():
            telegram_updates = home / "Library" / "Group Containers" / "6N38VWS5BX.ru.keepcoder.Telegram" / "appstore" / "updates" / "PersistentDownloads"
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
                        description="Historical auto-update installer packages left behind by Telegram's updater.",
                        cleanup_command=f'rm -rf "{telegram_updates}"/*'
                    ))

        # Hidden ~/.net/Updates directory
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
                    description="Historical duplicate .NET preview runtime assemblies.",
                    cleanup_command=f'rm -rf "{net_updates}"/*'
                ))

        # -------------------------------------------------------------
        # 3. Crash Reports & Diagnostic Logs
        # -------------------------------------------------------------
        diag_dirs = [
            home / "Library" / "Logs" / "DiagnosticReports",
            Path("/var/crash"),
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
                        description="Historical system process crash dumps (.ips / core dumps).",
                        cleanup_command=f'rm -rf "{d}"/*'
                    ))

        # -------------------------------------------------------------
        # 4. System Trash / Recycle Bin
        # -------------------------------------------------------------
        trash_paths = [
            home / ".Trash",
            home / ".local" / "share" / "Trash",
        ]
        for t in trash_paths:
            if t.exists():
                sz = get_dir_size(t)
                if sz > 100 * 1024 * 1024:  # > 100MB
                    findings.append(Finding(
                        id="system_trash",
                        title="System Trash / Recycle Bin",
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.ZERO_RISK,
                        path=str(t),
                        size_bytes=sz,
                        description="Files already moved to Trash by user.",
                        cleanup_command=f'rm -rf "{t}"/*'
                    ))
                break

        return findings
