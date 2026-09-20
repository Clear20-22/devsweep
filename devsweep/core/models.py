"""
devsweep.core.models
====================

Shared data-model layer for the entire devsweep pipeline.

Everything the scanner modules produce and the reporters consume is expressed
through the three types defined here:

* ``SafetyLevel``  — how confidently a finding can be removed
* ``Category``     — which tooling domain a finding belongs to
* ``Finding``      — a single reclaimable storage item found on disk
* ``ScanReport``   — the complete result of one scan run

Design note
-----------
Using plain Python ``dataclass`` objects (instead of e.g. Pydantic) keeps the
dependency footprint at zero: devsweep runs with stock Python 3.8+.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Safety classification — determines how a finding is presented and whether
# it is included in automatically generated cleanup scripts.
# ---------------------------------------------------------------------------

class SafetyLevel(str, Enum):
    """Three-tier risk classification for every reclaimable item.

    Inheriting from ``str`` means enum values serialise to their string names
    transparently when passed to ``json.dumps`` via ``dataclasses.asdict``.
    """

    ZERO_RISK = "ZERO_RISK"
    """Completely safe to remove:
    dead orphan databases, leftover installer DMGs, update-dump directories.
    The related app no longer references these paths at all.
    Tip: still verify the path exists and the app is closed before running
    the command — the *tool* is certain, but the *user* should stay in control.
    """

    SAFE_CACHE = "SAFE_CACHE"
    """Safe to clear — will rebuild automatically on demand:
    developer toolchain download caches, compiler artefacts, and browser HTTP
    caches.  Removing them causes a one-time slowdown the next time you build
    or browse, then everything is regenerated.
    """

    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    """Needs a human decision before removal:
    active project virtual environments, Docker VM images, duplicate app
    bundles, and Android emulator system images.  Deleting without checking
    could break a running project or remove something that cannot easily be
    recovered.
    """


# ---------------------------------------------------------------------------
# High-level grouping for the UI tables and report sections.
# ---------------------------------------------------------------------------

class Category(str, Enum):
    """Scanner category — maps each finding to its tooling domain.

    The string value is used verbatim in the terminal table, JSON export, and
    Markdown report headings, so keep them human-readable.
    """

    PACKAGE_MANAGERS = "Package Managers & Toolchains"
    IDES_EDITORS = "IDEs & Editors"
    VIRTUALIZATION = "Containers, VMs & Emulators"
    AI_ML = "AI & Machine Learning"
    PROJECTS = "Project Artifacts & Repositories"
    SYSTEM_BROWSERS = "System Caches & Browsers"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """One reclaimable storage item discovered during a scan.

    Scanner modules return a list of ``Finding`` objects.  Reporters read
    those lists to render tables, write reports, and build cleanup scripts.

    Attributes
    ----------
    id : str
        A stable, snake_case machine identifier (e.g. ``"npm_cache"``).
        Used as a dict key if callers need to deduplicate across runs.
    title : str
        Short human-readable label shown in the terminal table header
        (e.g. ``"Node npm Download Cache"``).
    category : Category
        Top-level tooling domain this finding belongs to.
    safety : SafetyLevel
        How confidently this item can be removed (see ``SafetyLevel`` docs).
    path : str
        Absolute filesystem path to the reclaimable directory or file.
        Reporters may replace the home prefix with ``~`` when ``--redact``
        is active — see ``utils.redact_report``.
    size_bytes : int
        Physical allocated disk space in bytes.  For sparse virtual-disk
        files (Docker.raw, ext4.vhdx) this is the *allocated* block count
        rather than the logical file size — see ``utils.get_file_allocated_size``.
    description : str
        One-sentence explanation of what the item is and why it is safe
        (or not) to delete.  Shown in the terminal table ``Details`` column.
    cleanup_command : str
        A ready-to-run shell command (or a human instruction starting with
        ``#``) that removes the item.  Commands starting with ``#`` are shown
        as notes in reports but omitted from generated cleanup scripts.
    item_count : int, optional
        For aggregate findings (e.g. N orphaned workspace folders), the count
        of sub-items.  Displayed alongside the title when present.
    metadata : dict, optional
        Arbitrary key→value pairs for scanner-specific extra context (e.g.
        Docker image names, IDE version strings).
    """

    id: str
    title: str
    category: Category
    safety: SafetyLevel
    path: str
    size_bytes: int
    description: str
    cleanup_command: str
    item_count: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Computed size helpers — reporters use these instead of raw bytes so
    # they never have to duplicate the formatting logic.
    # ------------------------------------------------------------------

    @property
    def size_mb(self) -> float:
        """Return ``size_bytes`` converted to megabytes (float)."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """Return ``size_bytes`` converted to gigabytes (float)."""
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def formatted_size(self) -> str:
        """Return a human-readable size string (e.g. ``"3.48 GB"`` or ``"512.0 MB"``).

        Automatically selects the most readable unit:
        GB ≥ 1 GiB · MB ≥ 1 MiB · KB ≥ 1 KiB · otherwise raw bytes.
        """
        if self.size_bytes >= 1024 * 1024 * 1024:
            return f"{self.size_gb:.2f} GB"
        elif self.size_bytes >= 1024 * 1024:
            return f"{self.size_mb:.1f} MB"
        elif self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


@dataclass
class ScanReport:
    """The complete output of one devsweep scan run.

    Constructed by ``cli.main`` after all scanner modules have finished and
    passed into every reporter (terminal, JSON, Markdown, and script-gen).

    Attributes
    ----------
    system_os : str
        Human-readable OS platform string from ``platform.platform()``.
    hostname : str
        Machine hostname from ``platform.node()``.
        Replaced with ``"<redacted>"`` when ``--redact`` is active.
    total_disk_bytes : int
        Total capacity of the filesystem mount that contains the home dir.
    free_disk_bytes : int
        Free space currently available on that same mount.
    scan_duration_sec : float
        Wall-clock time (in seconds) from scan start to completion.
    findings : list of Finding
        All reclaimable items discovered, in discovery order.
        Reporters typically sort this by ``size_bytes`` descending.
    """

    system_os: str
    hostname: str
    total_disk_bytes: int
    free_disk_bytes: int
    scan_duration_sec: float
    findings: List[Finding] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Aggregate helpers — reporters use these for the summary breakdown row.
    # ------------------------------------------------------------------

    @property
    def total_reclaimable_bytes(self) -> int:
        """Sum of ``size_bytes`` across **all** findings."""
        return sum(f.size_bytes for f in self.findings)

    @property
    def zero_risk_bytes(self) -> int:
        """Sum of ``size_bytes`` for ``ZERO_RISK`` findings only."""
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.ZERO_RISK)

    @property
    def safe_cache_bytes(self) -> int:
        """Sum of ``size_bytes`` for ``SAFE_CACHE`` findings only."""
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.SAFE_CACHE)

    @property
    def review_required_bytes(self) -> int:
        """Sum of ``size_bytes`` for ``REQUIRES_REVIEW`` findings only."""
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.REQUIRES_REVIEW)
