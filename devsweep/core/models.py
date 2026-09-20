"""Data models and enums for devsweep auditor."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SafetyLevel(str, Enum):
    ZERO_RISK = "ZERO_RISK"            # 100% safe: dead orphans, leftover installers, download dumps
    SAFE_CACHE = "SAFE_CACHE"          # Safe to clear: dev/build caches, auto-repopulated on demand
    REQUIRES_REVIEW = "REQUIRES_REVIEW" # Needs user decision: inactive venvs, Docker VMs, duplicate apps


class Category(str, Enum):
    PACKAGE_MANAGERS = "Package Managers & Toolchains"
    IDES_EDITORS = "IDEs & Editors"
    VIRTUALIZATION = "Containers, VMs & Emulators"
    AI_ML = "AI & Machine Learning"
    PROJECTS = "Project Artifacts & Repositories"
    SYSTEM_BROWSERS = "System Caches & Browsers"


@dataclass
class Finding:
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

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def formatted_size(self) -> str:
        if self.size_bytes >= 1024 * 1024 * 1024:
            return f"{self.size_gb:.2f} GB"
        elif self.size_bytes >= 1024 * 1024:
            return f"{self.size_mb:.1f} MB"
        elif self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"


@dataclass
class ScanReport:
    system_os: str
    hostname: str
    total_disk_bytes: int
    free_disk_bytes: int
    scan_duration_sec: float
    findings: List[Finding] = field(default_factory=list)

    @property
    def total_reclaimable_bytes(self) -> int:
        return sum(f.size_bytes for f in self.findings)

    @property
    def zero_risk_bytes(self) -> int:
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.ZERO_RISK)

    @property
    def safe_cache_bytes(self) -> int:
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.SAFE_CACHE)

    @property
    def review_required_bytes(self) -> int:
        return sum(f.size_bytes for f in self.findings if f.safety == SafetyLevel.REQUIRES_REVIEW)
