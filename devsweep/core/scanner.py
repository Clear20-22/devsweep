"""Base scanner interface for devsweep modules."""

from abc import ABC, abstractmethod
from typing import List
from devsweep.core.models import Finding


class BaseScanner(ABC):
    """Abstract base class for a devsweep scanner module."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the module."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this scanner inspects."""
        pass

    @abstractmethod
    def scan(self) -> List[Finding]:
        """Execute non-destructive inspection and return list of findings."""
        pass
