"""Project directories, virtual environment, and repository bloat scanner."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir


class ProjectScanner(BaseScanner):
    def __init__(self, search_roots: Optional[List[Path]] = None, max_scan_depth: int = 4):
        self.max_scan_depth = max_scan_depth
        home = get_home_dir()
        if search_roots:
            self.search_roots = [p for p in search_roots if p.exists()]
        else:
            # Common developer workspaces across OSes
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
        return "Scans developer workspaces for large virtualenvs, node_modules, build artifacts, and loose git objects"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []

        if not self.search_roots:
            return findings

        for root in self.search_roots:
            self._scan_directory(root, findings)

        return findings

    def _scan_directory(self, root: Path, findings: List[Finding]):
        """Walk project directory tree safely up to max_scan_depth."""
        root_depth = len(root.parts)

        for current_root, dirs, files in os.walk(root):
            curr_path = Path(current_root)
            depth = len(curr_path.parts) - root_depth
            if depth > self.max_scan_depth:
                dirs.clear()
                continue

            # 1. Virtual Environments
            for d in list(dirs):
                if d in (".venv", "venv", "env") and (curr_path / d / "pyvenv.cfg").exists():
                    venv_path = curr_path / d
                    sz = get_dir_size(venv_path)
                    if sz > 200 * 1024 * 1024:  # > 200MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"venv_{parent_project}_{d}",
                            title=f"Python Virtualenv in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.REQUIRES_REVIEW,
                            path=str(venv_path),
                            size_bytes=sz,
                            description=(
                                f"Virtual environment inside {parent_project}. Can be re-created via "
                                "`uv venv` or `python -m venv` if dependencies are specified in requirements.txt or pyproject.toml."
                            ),
                            cleanup_command=f'rm -rf "{venv_path}"'
                        ))
                    dirs.remove(d)  # Don't descend into venv

                # 2. Node Modules
                elif d == "node_modules" and (curr_path / "package.json").exists():
                    nm_path = curr_path / d
                    sz = get_dir_size(nm_path)
                    if sz > 300 * 1024 * 1024:  # > 300MB
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"node_modules_{parent_project}",
                            title=f"node_modules in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.REQUIRES_REVIEW,
                            path=str(nm_path),
                            size_bytes=sz,
                            description=f"Installed Node dependencies for {parent_project}. Re-installable with `npm install` / `pnpm install`.",
                            cleanup_command=f'rm -rf "{nm_path}"'
                        ))
                    dirs.remove(d)  # Don't descend into node_modules

                # 3. Next.js / React build caches
                elif d == ".next" and (curr_path / "package.json").exists():
                    next_path = curr_path / d
                    sz = get_dir_size(next_path)
                    if sz > 150 * 1024 * 1024:
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"next_cache_{parent_project}",
                            title=f"Next.js Build Cache in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.SAFE_CACHE,
                            path=str(next_path),
                            size_bytes=sz,
                            description=f"Compiled Webpack / SWC cache in {parent_project}. Rebuilt automatically on `npm run dev` / `build`.",
                            cleanup_command=f'rm -rf "{next_path}"'
                        ))
                    dirs.remove(d)

                # 4. Rust Target directory
                elif d == "target" and (curr_path / "Cargo.toml").exists():
                    target_path = curr_path / d
                    sz = get_dir_size(target_path)
                    if sz > 200 * 1024 * 1024:
                        parent_project = curr_path.name
                        findings.append(Finding(
                            id=f"rust_target_{parent_project}",
                            title=f"Cargo Target Build Directory in '{parent_project}'",
                            category=Category.PROJECTS,
                            safety=SafetyLevel.SAFE_CACHE,
                            path=str(target_path),
                            size_bytes=sz,
                            description=f"Compiled Rust binaries and intermediate crates for {parent_project}.",
                            cleanup_command=f"cd \"{curr_path}\" && cargo clean"
                        ))
                    dirs.remove(d)

                # 5. Git repository loose objects check
                elif d == ".git" and (curr_path / ".git").is_dir():
                    git_objects = curr_path / ".git" / "objects"
                    if git_objects.exists():
                        sz = get_dir_size(git_objects)
                        if sz > 200 * 1024 * 1024:  # > 200MB
                            parent_project = curr_path.name
                            findings.append(Finding(
                                id=f"git_objects_{parent_project}",
                                title=f"Large Git Objects Database in '{parent_project}'",
                                category=Category.PROJECTS,
                                safety=SafetyLevel.SAFE_CACHE,
                                path=str(curr_path / ".git"),
                                size_bytes=sz,
                                description=(
                                    f"Git object repository in {parent_project} contains uncompressed/loose objects. "
                                    "Repacking with `git gc --prune=now` will compress and deduplicate history."
                                ),
                                cleanup_command=f"cd \"{curr_path}\" && git gc --prune=now --aggressive"
                            ))
                    dirs.remove(d)
