"""
devsweep.modules.package_managers
==================================

Scanner for developer language toolchain caches and package manager stores.

What is inspected
-----------------
**Python**
  * ``pip`` wheel and download cache (``~/.cache/pip``)
  * ``uv`` fast-cache (``~/.cache/uv``)
  * ``poetry`` virtualenv and wheel cache (``~/.cache/pypoetry``)

**Node.js / JavaScript**
  * ``npm`` content-addressable download cache (``~/.npm``)
  * ``npx`` ephemeral runner packages (``~/.npm/_npx``) — ZERO_RISK
  * ``yarn`` (v1/v2/v3) package cache (``~/.cache/Yarn``)
  * ``pnpm`` global content-addressable store (``~/.local/share/pnpm/store``)
  * ``node-gyp`` native C++ header cache (``~/.node-gyp``)

**Rust**
  * ``cargo`` downloaded crates archive (``~/.cargo/registry/cache``)
  * ``rustup`` multiple installed toolchains (``~/.rustup/toolchains``) — REQUIRES_REVIEW

**JVM / Java**
  * ``gradle`` multi-version dependency cache (``~/.gradle/caches``)
  * ``maven`` local repository (``~/.m2/repository``)

**Go**
  * Go build output cache (``~/.cache/go-build``)
  * Go module download cache (``~/go/pkg/mod/cache``)

**System package managers**
  * ``Homebrew`` bottle cache (``~/Library/Caches/Homebrew``)
  * ``APT`` package archives (``/var/cache/apt/archives``) — Linux
  * ``Pacman`` package cache (``/var/cache/pacman/pkg``) — Arch Linux

All of the above are ``SAFE_CACHE`` (auto-rebuilt on next install) except
``rustup`` toolchains which are ``REQUIRES_REVIEW`` because removing a
toolchain requires a subsequent ``rustup toolchain install`` to restore it.

Size thresholds
---------------
Thresholds vary by ecosystem:
* 20 MB for Python caches (small individual packages)
* 50 MB for npm, cargo, go, node-gyp, gradle, maven
* 100 MB for pnpm (global store), gradle JVM, homebrew
* 30 MB for homebrew bottles
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import (
    get_dir_size,
    get_home_dir,
    get_local_cache_dir,
    is_macos,
    is_windows,
)


class PackageManagerScanner(BaseScanner):
    """Scanner for language toolchain download caches and package stores."""

    @property
    def name(self) -> str:
        return "package_managers"

    @property
    def description(self) -> str:
        return (
            "Audits dev toolchain caches "
            "(pip, uv, npm, yarn, pnpm, cargo, gradle, maven, brew)"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_cache = get_local_cache_dir()

        # ------------------------------------------------------------------
        # 1. Python toolchain caches
        # ------------------------------------------------------------------

        # pip wheel & download cache
        # Platform-specific paths because pip respects XDG on Linux but uses
        # the AppData/Roaming path on Windows.
        pip_caches = (
            [
                local_cache / "pip" / "Cache",
                home / "AppData" / "Roaming" / "pip" / "Cache",
            ]
            if is_windows()
            else [
                local_cache / "pip",        # macOS: ~/Library/Caches/pip
                home / ".cache" / "pip",    # Linux: ~/.cache/pip
            ]
        )
        for p in pip_caches:
            if p.exists():
                sz = get_dir_size(p)
                if sz > 20 * 1024 * 1024:
                    findings.append(Finding(
                        id="pip_cache",
                        title="Python pip Wheel & Download Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(p),
                        size_bytes=sz,
                        description=(
                            "Cached downloaded wheels and source tarballs from past pip installations. "
                            "Reinstalling packages will re-populate this cache."
                        ),
                        cleanup_command="pip cache purge",
                    ))
                break  # Only report the first existing cache directory.

        # uv fast cache
        # uv is a modern, Rust-based pip/virtualenv replacement.
        uv_cache = (
            local_cache / "uv" / "cache"     # Windows
            if is_windows()
            else (
                local_cache / "uv"           # macOS: ~/Library/Caches/uv
                if is_macos()
                else home / ".cache" / "uv"  # Linux
            )
        )
        if uv_cache.exists():
            sz = get_dir_size(uv_cache)
            if sz > 20 * 1024 * 1024:
                findings.append(Finding(
                    id="uv_cache",
                    title="uv Package Manager Fast-Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(uv_cache),
                    size_bytes=sz,
                    description=(
                        "Pre-built wheels and package metadata cached by uv. "
                        "Cleared with `uv cache clean`."
                    ),
                    cleanup_command="uv cache clean",
                ))

        # Poetry cache
        # Stores downloaded wheels and virtualenv copies for projects using Poetry.
        poetry_cache = (
            local_cache / "pypoetry" / "Cache"  # Windows
            if is_windows()
            else (
                local_cache / "pypoetry"          # macOS
                if is_macos()
                else home / ".cache" / "pypoetry" # Linux
            )
        )
        if poetry_cache.exists():
            sz = get_dir_size(poetry_cache)
            if sz > 20 * 1024 * 1024:
                findings.append(Finding(
                    id="poetry_cache",
                    title="Poetry Virtualenv & Wheel Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(poetry_cache),
                    size_bytes=sz,
                    description=(
                        "Poetry artifact and wheel download cache. "
                        "Each Poetry project's virtualenv is typically stored here too."
                    ),
                    cleanup_command="poetry cache clear --all .",
                ))

        # ------------------------------------------------------------------
        # 2. Node.js & JavaScript ecosystem caches
        # ------------------------------------------------------------------

        # npm content-addressable download cache
        # ``~/.npm`` stores tarballs indexed by package+version hash.
        npm_cache = home / ".npm"
        if npm_cache.exists():
            sz = get_dir_size(npm_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="npm_cache",
                    title="Node npm Download Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(npm_cache),
                    size_bytes=sz,
                    description=(
                        "Local content-addressable tarball cache from npm installs. "
                        "npm re-downloads packages on next install if the cache is cleared."
                    ),
                    cleanup_command="npm cache clean --force",
                ))

        # npx ephemeral runner packages
        # ``npx <pkg>`` downloads and extracts the package here each time it is
        # run without a globally installed version.  These are ZERO_RISK — they
        # will just be re-downloaded on the next `npx` invocation.
        npx_cache = home / ".npm" / "_npx"
        if npx_cache.exists():
            sz = get_dir_size(npx_cache)
            if sz > 20 * 1024 * 1024:
                findings.append(Finding(
                    id="npx_cache",
                    title="npx Ephemeral Runner Packages",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.ZERO_RISK,
                    path=str(npx_cache),
                    size_bytes=sz,
                    description=(
                        "Packages downloaded for one-off CLI commands via npx. "
                        "Re-downloaded automatically on next `npx` use."
                    ),
                    cleanup_command=f'rm -rf "{npx_cache}"/*',
                ))

        # Yarn package cache (supports v1 / Berry v2/v3)
        yarn_cache = (
            local_cache / "Yarn" / "Cache"    # Windows
            if is_windows()
            else (
                local_cache / "Yarn"           # macOS: ~/Library/Caches/Yarn
                if is_macos()
                else home / ".cache" / "yarn"  # Linux
            )
        )
        if yarn_cache.exists():
            sz = get_dir_size(yarn_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="yarn_cache",
                    title="Yarn Package Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(yarn_cache),
                    size_bytes=sz,
                    description=(
                        "Cached package tarballs across Yarn v1/v2/v3 installs. "
                        "Rebuilt on next `yarn install`."
                    ),
                    cleanup_command="yarn cache clean",
                ))

        # pnpm global content-addressable store
        # Unlike npm/yarn, pnpm hard-links packages from this store into projects,
        # so the store may be large even if individual projects look small.
        # ``pnpm store prune`` removes only unreferenced packages — much safer
        # than deleting the whole store.
        pnpm_store = home / ".local" / "share" / "pnpm" / "store"
        if pnpm_store.exists():
            sz = get_dir_size(pnpm_store)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="pnpm_store",
                    title="pnpm Global Content-Addressable Store",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(pnpm_store),
                    size_bytes=sz,
                    description=(
                        "Shared pnpm package store (hard-linked into project node_modules). "
                        "`pnpm store prune` removes only packages not referenced by any project."
                    ),
                    cleanup_command="pnpm store prune",
                ))

        # node-gyp native C++ header cache
        # When npm installs a native Node addon, node-gyp downloads Node headers
        # for the target Node version here.  Old header versions accumulate.
        node_gyp = home / ".node-gyp"
        if node_gyp.exists():
            sz = get_dir_size(node_gyp)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="node_gyp_cache",
                    title="node-gyp Native Header Caches",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(node_gyp),
                    size_bytes=sz,
                    description=(
                        "C++ headers for compiling native Node.js addons. "
                        "Old Node version headers can safely be removed."
                    ),
                    cleanup_command=f'rm -rf "{node_gyp}"/*',
                ))

        # ------------------------------------------------------------------
        # 3. Rust: Cargo crates archive & Rustup toolchains
        # ------------------------------------------------------------------

        # Cargo registry cache
        # ``~/.cargo/registry/cache`` holds the original ``.crate`` archives
        # downloaded from crates.io.  These are unpacked into ``registry/src``
        # for compilation.  The archives are safe to delete — Cargo re-downloads
        # them on the next `cargo build` invocation.
        cargo_cache = home / ".cargo" / "registry" / "cache"
        if cargo_cache.exists():
            sz = get_dir_size(cargo_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="cargo_registry_cache",
                    title="Rust Cargo Downloaded Crates Archive",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(cargo_cache),
                    size_bytes=sz,
                    description=(
                        "Cached .crate archives from crates.io. "
                        "Cargo re-downloads them automatically on `cargo build`."
                    ),
                    cleanup_command=(
                        "cargo cache -a  "
                        "# or: rm -rf ~/.cargo/registry/cache/*"
                    ),
                ))

        # Rustup toolchains — REQUIRES_REVIEW
        # Each installed toolchain (stable, nightly, beta, or a specific version)
        # is a complete Rust compiler + standard library (~800 MB–1.5 GB each).
        # If you have more than one installed, you might be able to remove old ones,
        # but the user must decide which toolchains their projects actually need.
        rustup_toolchains = home / ".rustup" / "toolchains"
        if rustup_toolchains.exists():
            try:
                toolchains = os.listdir(rustup_toolchains)
                if len(toolchains) > 1:  # Only flag if multiple are installed.
                    sz = get_dir_size(rustup_toolchains)
                    findings.append(Finding(
                        id="rustup_toolchains",
                        title=f"Rustup Multiple Toolchains ({len(toolchains)} installed)",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(rustup_toolchains),
                        size_bytes=sz,
                        description=(
                            f"Installed Rust toolchains: {', '.join(toolchains)}. "
                            "Run `rustup toolchain list` and remove unused toolchains."
                        ),
                        cleanup_command="rustup toolchain uninstall <toolchain-name>",
                    ))
            except Exception:
                pass  # Permission error listing toolchains — skip.

        # ------------------------------------------------------------------
        # 4. JVM / Java: Gradle & Maven caches
        # ------------------------------------------------------------------

        # Gradle multi-version dependency cache
        # ``~/.gradle/caches`` stores jar files and transform outputs for every
        # Gradle version ever used.  Old Gradle versions accumulate subdirectories.
        gradle_caches = home / ".gradle" / "caches"
        if gradle_caches.exists():
            sz = get_dir_size(gradle_caches)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="gradle_caches",
                    title="Gradle Multi-Version Dependency Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(gradle_caches),
                    size_bytes=sz,
                    description=(
                        "Jar files, transforms, and metadata cached across past Gradle builds. "
                        "Re-populated on next `gradle build`."
                    ),
                    cleanup_command=f'rm -rf "{gradle_caches}"/*',
                ))

        # Maven local repository
        # ``~/.m2/repository`` mirrors every JAR, POM, and metadata file
        # downloaded by Maven from Maven Central or other repositories.
        m2_repo = home / ".m2" / "repository"
        if m2_repo.exists():
            sz = get_dir_size(m2_repo)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="maven_repository",
                    title="Maven Local Dependency Repository (.m2)",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(m2_repo),
                    size_bytes=sz,
                    description=(
                        "Locally cached Maven dependency JARs. "
                        "Maven re-downloads missing artifacts from Maven Central."
                    ),
                    cleanup_command=f'rm -rf "{m2_repo}"/*',
                ))

        # ------------------------------------------------------------------
        # 5. Go language caches
        # ------------------------------------------------------------------

        # Go build output cache
        # The Go toolchain caches compiled packages here so unchanged code is
        # not recompiled.  Running `go clean -cache` empties it safely.
        go_cache = (
            local_cache / "go-build"            # macOS: ~/Library/Caches/go-build
            if (is_macos() or is_windows())
            else home / ".cache" / "go-build"   # Linux
        )
        if go_cache.exists():
            sz = get_dir_size(go_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="go_build_cache",
                    title="Go Build Output Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(go_cache),
                    size_bytes=sz,
                    description=(
                        "Go compiler build cache. "
                        "Auto-reconstructed on next `go build`."
                    ),
                    cleanup_command="go clean -cache",
                ))

        # Go module download cache
        # Downloaded module source archives (.zip) live under
        # ``~/go/pkg/mod/cache``.  The actual extracted sources are in
        # ``~/go/pkg/mod``.  Cleaning the cache only removes the archives.
        go_mod_cache = home / "go" / "pkg" / "mod" / "cache"
        if go_mod_cache.exists():
            sz = get_dir_size(go_mod_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="go_mod_cache",
                    title="Go Module Download Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(go_mod_cache),
                    size_bytes=sz,
                    description=(
                        "Downloaded Go module source archives. "
                        "Re-downloaded on next `go get` or `go mod tidy`."
                    ),
                    cleanup_command="go clean -modcache",
                ))

        # ------------------------------------------------------------------
        # 6. Homebrew package download cache (macOS & Linux)
        #
        #    ``brew cleanup`` removes bottles older than a configurable threshold.
        #    ``brew cleanup -s --prune=all`` is the most thorough variant.
        # ------------------------------------------------------------------
        brew_cache = (
            local_cache / "Homebrew"       # macOS: ~/Library/Caches/Homebrew
            if is_macos()
            else home / ".cache" / "Homebrew"  # Linux (Homebrew on Linux)
        )
        if brew_cache.exists():
            sz = get_dir_size(brew_cache)
            if sz > 30 * 1024 * 1024:
                findings.append(Finding(
                    id="homebrew_cache",
                    title="Homebrew Package Download Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(brew_cache),
                    size_bytes=sz,
                    description=(
                        "Downloaded bottles and git clones from `brew install`. "
                        "Re-downloaded on next install."
                    ),
                    cleanup_command="brew cleanup -s --prune=all",
                ))

        # ------------------------------------------------------------------
        # 7. Linux system package manager caches
        # ------------------------------------------------------------------

        # APT package archive cache (Debian / Ubuntu)
        # Downloaded .deb files accumulate here after `apt-get install`.
        apt_archives = Path("/var/cache/apt/archives")
        if apt_archives.exists():
            sz = get_dir_size(apt_archives)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="apt_cache",
                    title="APT Package Archives (/var/cache/apt)",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(apt_archives),
                    size_bytes=sz,
                    description=(
                        "Downloaded .deb package files from apt-get / apt install. "
                        "Re-downloaded on next `apt install`."
                    ),
                    cleanup_command="sudo apt-get clean",
                ))

        # Pacman package cache (Arch Linux)
        # Pacman keeps downloaded package tarballs even after installation.
        # ``paccache -r`` keeps the 3 most recent versions; ``pacman -Sc`` keeps
        # only installed package versions.
        pacman_pkg = Path("/var/cache/pacman/pkg")
        if pacman_pkg.exists():
            sz = get_dir_size(pacman_pkg)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="pacman_cache",
                    title="Pacman Package Cache (/var/cache/pacman/pkg)",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(pacman_pkg),
                    size_bytes=sz,
                    description=(
                        "Cached Arch Linux package tarballs. "
                        "`paccache -r` keeps last 3 versions per package."
                    ),
                    cleanup_command="paccache -r  # or: sudo pacman -Sc",
                ))

        return findings
