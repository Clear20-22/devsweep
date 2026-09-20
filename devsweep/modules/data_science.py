"""
devsweep.modules.data_science
==============================

Scanner for data science tooling: Conda/Mamba environments & package cache,
JupyterLab extension cache, and Ruby/Gem & PHP/Composer package stores.

What is inspected
-----------------
**Conda / Mamba**
  * ``~/miniconda3/pkgs`` and ``~/anaconda3/pkgs`` — downloaded package tarballs.
    Conda keeps these even after installing them into an environment.  Running
    ``conda clean --all`` removes tarballs and unused cached packages.
  * ``~/.conda/pkgs`` — the user-level conda package cache (alternative location
    when Conda is installed in a non-standard prefix).

**JupyterLab**
  * ``~/.local/share/jupyter`` — JupyterLab extension build artefacts, kernel
    specs, and server extension metadata.
  * ``~/.jupyter`` — Jupyter configuration and runtime logs.

**Ruby / Gem**
  * ``~/.gem`` — all installed Ruby gems and downloaded ``.gem`` archives.
    Only gems not installed to a project-level ``Gemfile.lock`` location are
    here; removing the whole cache means re-running ``gem install``.
  * ``~/.bundle/cache`` — Bundler cached gem files for ``bundle install --local``.

**PHP / Composer**
  * ``~/.composer/cache`` — Composer's global package download cache.
    Running ``composer clear-cache`` removes it; it is rebuilt on the next
    ``composer install``.

**Snap package cache** (Linux only)
  * ``/var/lib/snapd/cache`` — downloaded Snap packages waiting to be applied
    as updates.

**Flatpak** (Linux only)
  * ``~/.local/share/flatpak`` — Flatpak application runtimes and app bundles.
    Marked REQUIRES_REVIEW because removing Flatpak data uninstalls applications.

Safety tiers
-------------
* SAFE_CACHE  — Conda pkg tarballs, Jupyter artefacts, Composer cache, Ruby gem
                archives, Snap cache.  All rebuild automatically.
* REQUIRES_REVIEW — Conda environments, Flatpak app data.  Removing these would
                    break installed apps or delete active project environments.
"""

import os
from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir, is_linux, is_macos


class DataScienceScanner(BaseScanner):
    """Scanner for Conda, Mamba, JupyterLab, Ruby/Gem, PHP/Composer, Snap, and Flatpak."""

    @property
    def name(self) -> str:
        return "data_science"

    @property
    def description(self) -> str:
        return (
            "Scans Conda/Mamba, JupyterLab, Ruby/Gem, Composer, Snap, and Flatpak caches"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()

        # ------------------------------------------------------------------
        # 1. Conda / Mamba package tarballs
        #
        #    Conda stores downloaded package tarballs in a ``pkgs/`` directory
        #    inside the Conda prefix.  These accumulate over time because Conda
        #    keeps them as a local fallback for ``conda install --use-cache``.
        #    ``conda clean --all`` is the safe, official way to remove them.
        #
        #    We check multiple common prefix locations in priority order.
        # ------------------------------------------------------------------
        conda_pkg_dirs = [
            home / "miniconda3" / "pkgs",     # standard Miniconda install
            home / "anaconda3" / "pkgs",       # standard Anaconda install
            home / "miniforge3" / "pkgs",      # Miniforge (community build)
            home / "mambaforge" / "pkgs",      # Mambaforge (Mamba default)
            home / ".conda" / "pkgs",          # user-level Conda package cache
            Path("/opt/conda/pkgs"),            # Docker / system-wide Conda
        ]
        for pkgs_dir in conda_pkg_dirs:
            if pkgs_dir.exists():
                sz = get_dir_size(pkgs_dir)
                if sz > 100 * 1024 * 1024:
                    findings.append(Finding(
                        id="conda_pkg_cache",
                        title="Conda/Mamba Downloaded Package Tarballs",
                        category=Category.AI_ML,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(pkgs_dir),
                        size_bytes=sz,
                        description=(
                            "Cached Conda package tarballs from past `conda install` runs. "
                            "Use `conda clean --all` to remove safely."
                        ),
                        cleanup_command="conda clean --all -y",
                    ))
                break  # Only report the first matching prefix.

        # ------------------------------------------------------------------
        # 2. Conda environments (REQUIRES_REVIEW)
        #    ~/miniconda3/envs  or  ~/anaconda3/envs
        #
        #    Each named environment is a complete Python installation.
        #    We only report when more than one environment exists and the total
        #    is > 1 GB — a strong signal that some environments are stale.
        # ------------------------------------------------------------------
        conda_env_dirs = [
            home / "miniconda3" / "envs",
            home / "anaconda3" / "envs",
            home / "miniforge3" / "envs",
            home / "mambaforge" / "envs",
        ]
        for envs_dir in conda_env_dirs:
            if envs_dir.exists():
                try:
                    envs = [d for d in os.listdir(envs_dir) if (envs_dir / d).is_dir()]
                    if len(envs) > 1:  # Multiple envs = some may be stale.
                        sz = get_dir_size(envs_dir)
                        if sz > 1024 * 1024 * 1024:  # > 1 GB
                            findings.append(Finding(
                                id="conda_environments",
                                title=f"Conda Environments ({len(envs)} installed)",
                                category=Category.AI_ML,
                                safety=SafetyLevel.REQUIRES_REVIEW,
                                path=str(envs_dir),
                                size_bytes=sz,
                                description=(
                                    f"Named Conda environments: {', '.join(envs)}. "
                                    "Remove unused ones with `conda env remove -n <name>`."
                                ),
                                cleanup_command="conda env remove -n <env-name>",
                            ))
                except Exception:
                    pass
                break

        # ------------------------------------------------------------------
        # 3. JupyterLab extension & runtime artefacts
        #    ~/.local/share/jupyter
        #
        #    JupyterLab stores built extension webpack bundles, kernel specs,
        #    and server extension data here.  The ``lab`` subdirectory is the
        #    largest: it contains the entire pre-built JupyterLab application.
        #    Cleared with ``jupyter lab clean``; rebuilt on next ``jupyter lab``.
        # ------------------------------------------------------------------
        jupyter_share = home / ".local" / "share" / "jupyter"
        if jupyter_share.exists():
            sz = get_dir_size(jupyter_share)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="jupyter_share",
                    title="JupyterLab Extension Build & Runtime Cache",
                    category=Category.AI_ML,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(jupyter_share),
                    size_bytes=sz,
                    description=(
                        "JupyterLab webpack extension bundles, kernel specs, "
                        "and server extension metadata. Rebuilt on next `jupyter lab`."
                    ),
                    cleanup_command="jupyter lab clean --all",
                ))

        # ------------------------------------------------------------------
        # 4. Ruby / Gem global gem cache
        #    ~/.gem
        #
        #    ``gem install <pkg>`` downloads and installs gems here when no
        #    Bundler project scope is active.  The ``cache`` subdirectory holds
        #    raw ``.gem`` archive files that remain after installation.
        # ------------------------------------------------------------------
        gem_dir = home / ".gem"
        if gem_dir.exists():
            sz = get_dir_size(gem_dir)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="ruby_gem_cache",
                    title="Ruby Gem Global Package Cache (~/.gem)",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(gem_dir),
                    size_bytes=sz,
                    description=(
                        "Global Ruby gems and downloaded .gem archives. "
                        "Re-installed via `gem install <package>`."
                    ),
                    cleanup_command="gem cleanup",
                ))

        # ------------------------------------------------------------------
        # 5. Bundler gem download cache
        #    ~/.bundle/cache
        #
        #    When you run ``bundle install --standalone`` or Bundler fetches
        #    gem sources, it writes ``.gem`` files to this user-level cache.
        #    ``bundle clean --force`` removes gems not referenced by a Gemfile.
        # ------------------------------------------------------------------
        bundler_cache = home / ".bundle" / "cache"
        if bundler_cache.exists():
            sz = get_dir_size(bundler_cache)
            if sz > 50 * 1024 * 1024:
                findings.append(Finding(
                    id="bundler_cache",
                    title="Ruby Bundler Global Gem Download Cache",
                    category=Category.PACKAGE_MANAGERS,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(bundler_cache),
                    size_bytes=sz,
                    description=(
                        "Bundler cached .gem archives for offline / local installs."
                    ),
                    cleanup_command=f'rm -rf "{bundler_cache}"/*',
                ))

        # ------------------------------------------------------------------
        # 6. PHP Composer global package download cache
        #    ~/.composer/cache  (macOS / Linux)
        #    %APPDATA%\Composer\cache  (Windows — handled by platform utils)
        #
        #    Composer caches downloaded package zip archives to speed up future
        #    installs.  ``composer clear-cache`` is the official CLI command.
        # ------------------------------------------------------------------
        composer_caches = [
            home / ".composer" / "cache",                  # Linux/macOS
            home / "AppData" / "Roaming" / "Composer" / "cache",  # Windows
        ]
        for composer_cache in composer_caches:
            if composer_cache.exists():
                sz = get_dir_size(composer_cache)
                if sz > 50 * 1024 * 1024:
                    findings.append(Finding(
                        id="composer_cache",
                        title="PHP Composer Package Download Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(composer_cache),
                        size_bytes=sz,
                        description=(
                            "Cached Composer package archives from `composer install` runs. "
                            "Re-populated on next `composer install`."
                        ),
                        cleanup_command="composer clear-cache",
                    ))
                break

        # ------------------------------------------------------------------
        # 7. Snap package download cache (Linux only)
        #    /var/lib/snapd/cache
        #
        #    Snapd downloads new Snap revision tarballs here before applying
        #    updates.  Previous revisions that have already been applied are
        #    safe to remove; ``snap saved`` shows which revisions are retained.
        # ------------------------------------------------------------------
        if is_linux():
            snap_cache = Path("/var/lib/snapd/cache")
            if snap_cache.exists():
                sz = get_dir_size(snap_cache)
                if sz > 100 * 1024 * 1024:
                    findings.append(Finding(
                        id="snapd_cache",
                        title="Snap Package Download Cache",
                        category=Category.PACKAGE_MANAGERS,
                        safety=SafetyLevel.SAFE_CACHE,
                        path=str(snap_cache),
                        size_bytes=sz,
                        description=(
                            "Downloaded Snap package archives waiting for update application. "
                            "Already-applied revision tarballs are safe to remove."
                        ),
                        # ``snap set system cache.max-snap-cache=0`` disables future caching.
                        cleanup_command="sudo rm -rf /var/lib/snapd/cache/*",
                    ))

        # ------------------------------------------------------------------
        # 8. Flatpak application runtime data (Linux only)
        #    ~/.local/share/flatpak
        #
        #    Flatpak stores installed app bundles and runtimes here.  Unlike
        #    a package cache, these directories ARE the installed applications.
        #    Use REQUIRES_REVIEW — removing this directory uninstalls apps.
        #
        #    ``flatpak uninstall --unused`` removes only unused runtimes.
        # ------------------------------------------------------------------
        if is_linux():
            flatpak_dir = home / ".local" / "share" / "flatpak"
            if flatpak_dir.exists():
                sz = get_dir_size(flatpak_dir)
                if sz > 500 * 1024 * 1024:
                    findings.append(Finding(
                        id="flatpak_app_data",
                        title="Flatpak Application Runtimes & App Bundles",
                        category=Category.SYSTEM_BROWSERS,
                        safety=SafetyLevel.REQUIRES_REVIEW,
                        path=str(flatpak_dir),
                        size_bytes=sz,
                        description=(
                            "Installed Flatpak applications and shared runtimes. "
                            "`flatpak uninstall --unused` safely removes unused runtimes only."
                        ),
                        cleanup_command="flatpak uninstall --unused",
                    ))

        return findings
