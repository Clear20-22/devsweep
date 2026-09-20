"""
devsweep.modules.language_runtimes
====================================

Scanner for modern language runtime caches: Bun, Zig, Deno, and Flutter/Dart.

What is inspected
-----------------
**Bun** (JavaScript runtime & package manager)
  * ``~/.bun/install/cache`` — the global Bun package content-addressable cache.
    Bun re-downloads packages from the registry on the next ``bun install`` if
    the cache is cleared.

**Zig** (systems programming language)
  * ``~/.cache/zig`` — Zig's global download and compilation artifact cache.
    Contains package archives downloaded via ``zig fetch`` and cached compile
    outputs.  Rebuilt automatically on next ``zig build``.

**Deno** (JavaScript/TypeScript runtime)
  * ``~/.cache/deno`` (Linux/macOS) / ``%LOCALAPPDATA%\\deno`` (Windows).
    Stores downloaded remote modules (ES modules from URLs), compiled TS output,
    and the Language Server Protocol cache.  Rebuilt on next ``deno run``.

**Flutter / Dart**
  * ``~/.pub-cache`` — the Dart/Flutter pub package cache (downloaded package
    archives and extracted sources).  Re-populated on next ``flutter pub get``
    or ``dart pub get``.
  * ``~/.dart_tool`` — Dart tooling metadata and generated files for the *global*
    tool context (not per-project).
  * ``~/.flutter`` / ``~/.flutter_tool`` — Flutter tool stamp files, Dart SDK
    download artifacts, and engine binaries.

Safety tiers
-------------
* SAFE_CACHE — all of the above: every cache is rebuilt automatically the next
  time the relevant tool is run.  Clearing them causes a one-time slowdown while
  packages and modules are re-downloaded.

Size thresholds
---------------
* 50 MB for Bun, Zig, Deno caches
* 100 MB for Flutter/Dart pub-cache (package archives are typically larger)
"""

from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import (
    get_dir_size,
    get_home_dir,
    get_local_cache_dir,
    is_windows,
)


class LanguageRuntimeScanner(BaseScanner):
    """Scanner for Bun, Zig, Deno, and Flutter/Dart caches."""

    @property
    def name(self) -> str:
        return "language_runtimes"

    @property
    def description(self) -> str:
        return "Scans Bun, Zig, Deno, and Flutter/Dart toolchain caches"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_cache = get_local_cache_dir()

        # ------------------------------------------------------------------
        # 1. Bun package cache
        #    ~/.bun/install/cache
        #
        #    Bun uses a content-addressable store (similar to pnpm) where all
        #    packages across all projects are stored in a single global cache.
        #    Individual project ``node_modules`` are hard-linked from this cache,
        #    so clearing it only forces a re-download — it does not break any
        #    currently-installed project.
        # ------------------------------------------------------------------
        bun_cache = home / ".bun" / "install" / "cache"
        if bun_cache.exists():
            sz = get_dir_size(bun_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="bun_install_cache",
                    title="Bun Global Package Install Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(bun_cache),
                    size_bytes=sz,
                    description=(
                        "Bun's content-addressable package cache. "
                        "Re-populated on next `bun install`."
                    ),
                    cleanup_command="bun pm cache rm",
                ))

        # ------------------------------------------------------------------
        # 2. Zig download & compilation cache
        #    ~/.cache/zig   (Linux/macOS)
        #    %LOCALAPPDATA%\zig  (Windows)
        #
        #    ``zig fetch`` downloads package archives here; ``zig build``
        #    writes compiled object files.  Cleared with ``zig clean``
        #    (Zig >= 0.12) or by deleting the directory directly.
        # ------------------------------------------------------------------
        zig_caches = [
            local_cache / "zig",       # macOS: ~/Library/Caches/zig  |  Linux: ~/.cache/zig
            home / ".cache" / "zig",   # fallback for non-XDG Linux setups
        ]
        if is_windows():
            zig_caches = [local_cache / "zig"]  # Windows: %LOCALAPPDATA%\zig

        for zig_cache in zig_caches:
            if zig_cache.exists():
                sz = get_dir_size(zig_cache)
                if sz > 50 * 1024 * 1024:
                    findings.append(Finding(
                        id="zig_cache",
                        title="Zig Download & Compilation Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(zig_cache),
                        size_bytes=sz,
                        description=(
                            "Zig package archives fetched via `zig fetch` and "
                            "compiled build artefacts. Rebuilt on next `zig build`."
                        ),
                        cleanup_command=f'rm -rf "{zig_cache}"/*',
                    ))
                break  # Only report the first found cache location.

        # ------------------------------------------------------------------
        # 3. Deno module & LSP cache
        #    Linux/macOS: ~/.cache/deno
        #    Windows:     %LOCALAPPDATA%\deno
        #
        #    Deno downloads remote ES module URLs (e.g. https://deno.land/x/...)
        #    here, along with compiled TypeScript output and LSP type information.
        #    All of it is rebuilt on the next ``deno run`` / ``deno check``.
        # ------------------------------------------------------------------
        deno_caches = [
            home / ".cache" / "deno",  # Linux / macOS
            local_cache / "deno",       # Windows (%LOCALAPPDATA%\deno)
        ]
        for deno_cache in deno_caches:
            if deno_cache.exists():
                sz = get_dir_size(deno_cache)
                if sz > 50 * 1024 * 1024:
                    findings.append(Finding(
                        id="deno_cache",
                        title="Deno Module & TypeScript Compile Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(deno_cache),
                        size_bytes=sz,
                        description=(
                            "Deno cached remote modules, compiled TS output, and LSP data. "
                            "Re-downloaded on next `deno run`."
                        ),
                        cleanup_command="deno clean",
                    ))
                break  # Only report the first found.

        # ------------------------------------------------------------------
        # 4. Flutter / Dart pub package cache
        #    ~/.pub-cache
        #
        #    ``pub get`` / ``flutter pub get`` downloads package archives into
        #    ``~/.pub-cache/hosted/<pub.dartlang.org>/<package-version>/``
        #    and extracts them into ``~/.pub-cache/hosted/...``.  Clearing the
        #    cache forces a re-download on next ``pub get``.
        #    ``pub cache clean`` is the official CLI command (Dart SDK >= 2.14).
        # ------------------------------------------------------------------
        pub_cache = home / ".pub-cache"
        if pub_cache.exists():
            sz = get_dir_size(pub_cache)
            if sz > 100 * 1024 * 1024:  # Higher threshold — pub archives are larger.
                findings.append(Finding(
                    id="dart_pub_cache",
                    title="Dart/Flutter Pub Package Cache (~/.pub-cache)",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(pub_cache),
                    size_bytes=sz,
                    description=(
                        "Downloaded Dart/Flutter package archives from pub.dev. "
                        "Re-populated on next `flutter pub get` / `dart pub get`."
                    ),
                    cleanup_command="dart pub cache clean",
                ))

        # ------------------------------------------------------------------
        # 5. Flutter tool artifacts
        #    ~/.flutter  or  ~/.flutter_tool
        #
        #    The Flutter CLI stores its own Dart SDK download, tool stamp, and
        #    artifact cache in this directory.  On macOS the Dart SDK binary
        #    downloaded for the Flutter tool can be 150–250 MB.
        #    ``flutter --version`` triggers re-download if this is cleared.
        # ------------------------------------------------------------------
        flutter_dirs = [
            home / ".flutter",
            home / ".flutter_tool",
        ]
        for flutter_dir in flutter_dirs:
            if flutter_dir.exists():
                sz = get_dir_size(flutter_dir)
                if sz > 100 * 1024 * 1024:
                    findings.append(Finding(
                        id="flutter_tool_cache",
                        title="Flutter Tool Artifact Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(flutter_dir),
                        size_bytes=sz,
                        description=(
                            "Flutter CLI Dart SDK download and tool artefact cache. "
                            "Rebuilt on next `flutter` command."
                        ),
                        cleanup_command=f'rm -rf "{flutter_dir}"',
                    ))

        return findings
