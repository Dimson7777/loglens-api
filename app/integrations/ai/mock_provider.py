from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import AnalysisPriority
from app.schemas.analysis import AIAnalysisResult


class MockAIProvider:
    async def analyze_error_group(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIAnalysisResult:
        del system_prompt
        confidence = 0.66
        component = "unknown"
        if "database" in user_prompt.lower():
            component = "database"
            confidence = 0.82

        return AIAnalysisResult(
            summary="Likely repeated operational failure pattern in sampled logs.",
            likely_root_cause="Unhandled exception path repeatedly triggered under load.",
            suggested_fix="Add defensive validation and broaden exception handling with retries.",
            confidence=confidence,
            affected_component=component,
            recommended_priority=AnalysisPriority.MEDIUM,
            reasoning_summary=(
                "The sampled logs include repeated exception signatures and correlated timestamps."
            ),
            generated_at=datetime.now(UTC),
            provider="mock",
            model="mock-gpt",
            latency_ms=5,
        )
