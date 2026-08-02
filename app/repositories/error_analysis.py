from __future__ import annotations

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorAnalysisStatus
from app.models.error_analysis import ErrorAnalysis


class ErrorAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending_analysis(
        self, *, error_group_id: int, created_by: int
    ) -> ErrorAnalysis:
        analysis = ErrorAnalysis(
            error_group_id=error_group_id,
            status=ErrorAnalysisStatus.PENDING,
            created_by=created_by,
            raw_response_metadata={},
        )
        self._session.add(analysis)
        await self._session.flush()
        await self._session.refresh(analysis)
        return analysis

    async def get_latest_for_group(self, *, error_group_id: int) -> ErrorAnalysis | None:
        stmt: Select[tuple[ErrorAnalysis]] = (
            select(ErrorAnalysis)
            .where(ErrorAnalysis.error_group_id == error_group_id)
            .order_by(desc(ErrorAnalysis.created_at), desc(ErrorAnalysis.id))
        )
        result = await self._session.scalars(stmt.limit(1))
        return result.first()

    async def list_for_group(self, *, error_group_id: int, limit: int = 50) -> list[ErrorAnalysis]:
        stmt: Select[tuple[ErrorAnalysis]] = (
            select(ErrorAnalysis)
            .where(ErrorAnalysis.error_group_id == error_group_id)
            .order_by(desc(ErrorAnalysis.created_at), desc(ErrorAnalysis.id))
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return list(result)
