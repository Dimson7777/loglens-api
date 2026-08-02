from __future__ import annotations

from typing import Protocol

from app.schemas.analysis import AIAnalysisResult


class AIProvider(Protocol):
    async def analyze_error_group(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIAnalysisResult:
        """Return validated analysis output for one error group."""
