"""
devsweep.modules.projects
==========================

Scanner for project-local developer bloat: virtual environments, installed
Node dependencies, JavaScript framework build caches, Rust target directories,
and oversized git object stores.

What is inspected
-----------------
The scanner walks one or more *search roots* (developer workspace directories)
looking for well-known sub-directory patterns that indicate reclaimable storage:

* **Python virtualenvs** (``.venv``, ``venv``, ``env``) — detected by the
  presence of a ``pyvenv.cfg`` file.  Reported when > 200 MB.
* **node_modules** — detected alongside a ``package.json``.  Reported when
  > 300 MB.
* **.next** (Next.js / Webpack build cache) — detected alongside a
  ``package.json``.  Reported when > 150 MB.
* **target/** (Rust build output) — detected alongside a ``Cargo.toml``.
  Reported when > 200 MB.
* **.git/objects** (loose git object database) — flagged when the ``.git``
  objects directory exceeds 200 MB.  Running ``git gc`` compresses and
  deduplicates the history.

Default search roots
--------------------
When no custom roots are provided, the scanner checks the following directories
(whichever exist on the current machine):

* ``~/Documents/GitHub``
* ``~/Documents/Projects``
* ``~/Projects``
* ``~/dev``
* ``~/workspace``
* ``~/source``
* ``~/repos``

Custom roots can be passed via ``--scan-projects`` on the CLI, or by
constructing ``ProjectScanner(search_roots=[...])`` directly.

Depth limit
-----------
The walk is capped at ``max_scan_depth`` (default 4) levels below each search
root to avoid spending minutes inside deeply nested ``node_modules`` trees.
Detected directories (``node_modules``, ``.venv``, etc.) are never descended
into — they are measured in bulk and then skipped.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir


class ProjectScanner(BaseScanner):
    """Scanner for per-project developer build artefacts and virtualenvs.

    Parameters
    ----------
    search_roots : list of Path, optional
        Directories to walk.  If omitted, the scanner uses a list of common
        developer workspace locations under the user's home directory.
    max_scan_depth : int
        How many directory levels below each search root to traverse.
        Default is 4, which covers ``<root>/<org>/<project>/<subdir>/``.
    """

    def __init__(
        self,
        search_roots: Optional[List[Path]] = None,
        max_scan_depth: int = 4,
    ):
        self.max_scan_depth = max_scan_depth
        home = get_home_dir()

        if search_roots:
            # Only keep roots that actually exist on this machine.
            self.search_roots = [p for p in search_roots if p.exists()]
        else:
            # Common developer workspace locations across operating systems.
            # Feel free to add more locations relevant to your community!
            candidates = [
                home / "Documents" / "GitHub",
                home / "Documents" / "Projects",
                home / "Projects",
                home / "dev",
                home / "workspace",
                home / "source",
                home / "repos",
            ]
            self.search_roots = [p for p in candidates if p.exists()]

    @property
    def name(self) -> str:
        return "projects"

    @property
    def description(self) -> str:
        return (
            "Scans developer workspaces for large virtualenvs, node_modules, "
            "build artefacts, and loose git objects"
        )

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []

        if not self.search_roots:
            # No workspace directories found — nothing to scan.
            return findings

        for root in self.search_roots:
            self._scan_directory(root, findings)

        return findings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_directory(self, root: Path, findings: List[Finding]):
        """Walk ``root`` up to ``self.max_scan_depth`` and collect findings.

        Uses ``os.walk`` rather than ``Path.rglob`` so we can:
        1. Cap the recursion depth precisely.
        2. Remove directories from the ``dirs`` list to prevent ``os.walk``
           from descending into them (e.g. we measure ``.venv`` then skip it).
        """
        root_depth = len(root.parts)  # Reference depth for relative depth calc.

        for current_root, dirs, files in os.walk(root):
            curr_path = Path(current_root)
            depth = len(curr_path.parts) - root_depth

            # Stop descending if we've hit the depth limit.
            if depth > self.max_scan_depth:
                dirs.clear()
                continue

            # Iterate over a copy of dirs so we can safely remove items.
            for d in list(dirs):

                # ----------------------------------------------------------
                # 1. Python virtual environments
                #    Marker file: pyvenv.cfg (present in all virtualenv implementations)
                # ----------------------------------------------------------
                if d in (".venv", "venv", "env") and (curr_path / d / "pyvenv.cfg").exists():
                    venv_path = curr_path / d
                    sz = get_dir_size(venv_path)
                    if sz > 200 * 1024 * 1024:  # > 200 MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"venv_{parent_project}_{d}",
                            title=f"Python Virtualenv in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.REQUIRES_REVIEW,
                            path=str(venv_path),
                            size_bytes=sz,
                            description=(
                                f"Virtual environment inside {parent_project}. "
                                "Can be re-created via `uv venv` or `python -m venv` "
                                "if dependencies are specified in requirements.txt or pyproject.toml."
                            ),
                            cleanup_command=f'rm -rf "{venv_path}"',
                        ))
                    # Do NOT descend into the virtualenv — it contains thousands
                    # of small files and we've already measured it in bulk.
                    dirs.remove(d)

                # ----------------------------------------------------------
                # 2. Node.js node_modules
                #    Marker file: package.json in the parent directory
                # ----------------------------------------------------------
                elif d == "node_modules" and (curr_path / "package.json").exists():
                    nm_path = curr_path / d
                    sz = get_dir_size(nm_path)
                    if sz > 300 * 1024 * 1024:  # > 300 MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"node_modules_{parent_project}",
                            title=f"node_modules in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.REQUIRES_REVIEW,
                            path=str(nm_path),
                            size_bytes=sz,
                            description=(
                                f"Installed Node dependencies for {parent_project}. "
                                "Re-installable with `npm install` / `pnpm install`."
                            ),
                            cleanup_command=f'rm -rf "{nm_path}"',
                        ))
                    # Skip descending into node_modules — it contains tens of
                    # thousands of files and would dramatically slow the scan.
                    dirs.remove(d)

                # ----------------------------------------------------------
                # 3. Next.js / Webpack build cache
                #    ``.next`` holds compiled JavaScript bundles, ISR pages,
                #    and the Webpack/SWC module cache.  Rebuilt on `npm run build`.
                # ----------------------------------------------------------
                elif d == ".next" and (curr_path / "package.json").exists():
                    next_path = curr_path / d
                    sz = get_dir_size(next_path)
                    if sz > 150 * 1024 * 1024:  # > 150 MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"next_cache_{parent_project}",
                            title=f"Next.js Build Cache in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.SAFE_CACHE,
                            path=str(next_path),
                            size_bytes=sz,
                            description=(
                                f"Compiled Webpack / SWC cache in {parent_project}. "
                                "Rebuilt automatically on `npm run dev` / `build`."
                            ),
                            cleanup_command=f'rm -rf "{next_path}"',
                        ))
                    dirs.remove(d)

                # ----------------------------------------------------------
                # 4. Rust target directory
                #    Contains compiled binaries and all intermediate compilation
                #    artefacts.  Rust does not clean these up automatically.
                #    Use ``cargo clean`` rather than ``rm -rf`` to preserve
                #    fingerprint files that help Cargo skip unchanged crates.
                # ----------------------------------------------------------
                elif d == "target" and (curr_path / "Cargo.toml").exists():
                    target_path = curr_path / d
                    sz = get_dir_size(target_path)
                    if sz > 200 * 1024 * 1024:  # > 200 MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"rust_target_{parent_project}",
                            title=f"Cargo Target Build Directory in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.SAFE_CACHE,
                            path=str(target_path),
                            size_bytes=sz,
                            description=(
                                f"Compiled Rust binaries and intermediate crates for {parent_project}."
                            ),
                            # Use `cargo clean` so Cargo can re-use cached dependency crates.
                            cleanup_command=f'cd "{curr_path}" && cargo clean',
                        ))
                    dirs.remove(d)

                # ----------------------------------------------------------
                # 5. Loose git object database
                #    ``.git/objects`` grows large when a repo has a long history
                #    with binary files, or when loose objects have not been
                #    packed.  ``git gc --prune=now --aggressive`` repacks the
                #    history and removes unreachable objects, typically
                #    reclaiming 30–70% of the objects directory.
                # ----------------------------------------------------------
                elif d == ".git" and (curr_path / ".git").is_dir():
                    git_objects = curr_path / ".git" / "objects"
                    if git_objects.exists():
                        sz = get_dir_size(git_objects)
                        if sz > 200 * 1024 * 1024:  # > 200 MB
                            parent_project = curr_path.name
                            findings.append(Finding(
                                id=f"git_objects_{parent_project}",
                                title=f"Large Git Objects Database in '{parent_project}'",
                                category=Category.PROJECTS,
                                safety=SafetyLevel.SAFE_CACHE,
                                path=str(curr_path / ".git"),
                                size_bytes=sz,
                                description=(
                                    f"Git object repository in {parent_project} contains "
                                    "uncompressed/loose objects. "
                                    "Repacking with `git gc --prune=now` will compress and "
                                    "deduplicate history without losing any commits."
                                ),
                                cleanup_command=(
                                    f'cd "{curr_path}" && git gc --prune=now --aggressive'
                                ),
                            ))
                    # Don't walk inside .git — it's an internal git structure.
                    dirs.remove(d)
