"""Package managers and language toolchain cache scanner."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir, get_local_cache_dir, is_macos, is_windows


class PackageManagerScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "package_managers"

    @property
    def description(self) -> str:
        return "Audits dev toolchain caches (pip, uv, npm, yarn, pnpm, cargo, gradle, maven, brew)"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()
        local_cache = get_local_cache_dir()

        # -------------------------------------------------------------
        # 1. Python Toolchains (pip, uv, poetry)
        # -------------------------------------------------------------
        pip_caches = ([local_cache / "pip" / "Cache", home / "AppData" / "Roaming" / "pip" / "Cache"]
                      if is_windows() else [local_cache / "pip", home / ".cache" / "pip"])
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
                        description="Cached downloaded wheels and source tarballs from past pip installations.",
                        cleanup_command="pip cache purge"
                    ))
                break

        uv_cache = local_cache / "uv" / "cache" if is_windows() else (local_cache / "uv" if is_macos() else home / ".cache" / "uv")
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
                    description="Pre-built wheels and package metadata cached by uv.",
                    cleanup_command="uv cache clean"
                ))

        poetry_cache = local_cache / "pypoetry" / "Cache" if is_windows() else (local_cache / "pypoetry" if is_macos() else home / ".cache" / "pypoetry")
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
                    description="Poetry artifact and wheel download cache.",
                    cleanup_command="poetry cache clear --all ."
                ))

        # -------------------------------------------------------------
        # 2. Node.js & JavaScript (npm, npx, yarn, pnpm, node-gyp, bun)
        # -------------------------------------------------------------
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
                    description="Local content-addressable tarball cache from npm installs.",
                    cleanup_command="npm cache clean --force"
                ))

        # npx one-off binary downloads
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
                    description="Packages downloaded for one-off CLI commands via npx.",
                    cleanup_command=f'rm -rf "{npx_cache}"/*'
                ))

        yarn_cache = local_cache / "Yarn" / "Cache" if is_windows() else (local_cache / "Yarn" if is_macos() else home / ".cache" / "yarn")
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
                    description="Cached package tarballs across Yarn v1/v2/v3 installs.",
                    cleanup_command="yarn cache clean"
                ))

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
                    description="Shared pnpm package store. Can be pruned to remove unreferenced packages.",
                    cleanup_command="pnpm store prune"
                ))

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
                    description="C++ headers for compiling native C/C++ Node add-ons across old Node versions.",
                    cleanup_command=f'rm -rf "{node_gyp}"/*'
                ))

        # -------------------------------------------------------------
        # 3. Rust (Cargo & Rustup)
        # -------------------------------------------------------------
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
                    description="Cached .crate archives from crates.io.",
                    cleanup_command="cargo cache -a  # or rm -rf ~/.cargo/registry/cache/*"
                ))

        rustup_toolchains = home / ".rustup" / "toolchains"
        if rustup_toolchains.exists():
            try:
                toolchains = os.listdir(rustup_toolchains)
                if len(toolchains) > 1:
                    sz = get_dir_size(rustup_toolchains)
                    findings.append(Finding(
                        id="rustup_toolchains",
                        title=f"Rustup Multiple Toolchains ({len(toolchains)} installed)",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(rustup_toolchains),
                        size_bytes=sz,
                        description=f"Installed Rust toolchains: {', '.join(toolchains)}. Remove unused toolchains to free space.",
                        cleanup_command="rustup toolchain uninstall <toolchain-name>"
                    ))
            except Exception:
                pass

        # -------------------------------------------------------------
        # 4. JVM / Java (Gradle & Maven)
        # -------------------------------------------------------------
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
                    description="Jar files, transforms, and metadata cached across past Gradle builds.",
                    cleanup_command=f'rm -rf "{gradle_caches}"/*'
                ))

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
                    description="Locally installed and downloaded Maven dependency JARs.",
                    cleanup_command=f'rm -rf "{m2_repo}"/*'
                ))

        # -------------------------------------------------------------
        # 5. Go Language (Go Build & Mod Cache)
        # -------------------------------------------------------------
        go_cache = local_cache / "go-build" if (is_macos() or is_windows()) else home / ".cache" / "go-build"
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
                    description="Go compiler build cache. Auto-reconstructed upon go build.",
                    cleanup_command="go clean -cache"
                ))

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
                    description="Downloaded go module source archives.",
                    cleanup_command="go clean -modcache"
                ))

        # -------------------------------------------------------------
        # 6. Homebrew (macOS & Linux)
        # -------------------------------------------------------------
        brew_cache = local_cache / "Homebrew" if is_macos() else home / ".cache" / "Homebrew"
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
                    description="Downloaded bottles and git clones from brew install.",
                    cleanup_command="brew cleanup -s --prune=all"
                ))

        # -------------------------------------------------------------
        # 7. Linux System Package Caches (APT / Pacman)
        # -------------------------------------------------------------
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
                    description="Downloaded .deb package files from apt-get / apt install.",
                    cleanup_command="sudo apt-get clean"
                ))

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
                    description="Cached Arch Linux package tarballs.",
                    cleanup_command="paccache -r  # or sudo pacman -Sc"
                ))

        return findings
