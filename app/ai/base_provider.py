"""MRUDA — Abstract AI Provider."""

from abc import ABC, abstractmethod
from typing import Optional


class AIProvider(ABC):
    """Abstract base for AI narrative generation.

    All providers consume InsightOutput JSON and produce a human-readable summary.
    The system works without AI — this is purely optional.
    """

    @abstractmethod
    async def generate_summary(
        self, insight_json: dict, question: Optional[str] = None
    ) -> str:
        """Generate a narrative summary from structured insight data.

        Args:
            insight_json: The InsightOutput as a dict.
            question: Optional specific question from the user.
                      If provided, answer this question using the data.
                      If None, produce a general executive summary.

        Returns:
            A human-readable narrative string.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and ready."""
        ...
