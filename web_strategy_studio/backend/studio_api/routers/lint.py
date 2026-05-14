from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api.db import get_session
from studio_api.lint_service import lint_source
from studio_api.models import Strategy, StrategyVersion
from studio_api.schemas import LintBody, LintResponse

router = APIRouter(prefix="/api/v1", tags=["lint"])


@router.post("/lint", response_model=LintResponse)
async def lint_inline(body: LintBody):
    r = lint_source(body.source_code, body.profile)
    return LintResponse(**r)


@router.post("/strategies/{strategy_id}/lint", response_model=LintResponse)
async def lint_strategy(
    strategy_id: str,
    body: LintBody,
    session: AsyncSession = Depends(get_session),
):
    code = body.source_code
    if not code.strip():
        res = await session.execute(
            select(Strategy)
            .options(selectinload(Strategy.versions))
            .where(Strategy.id == strategy_id)
        )
        strat = res.scalar_one_or_none()
        if strat is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "NOT_FOUND", "message": "Strategy not found", "details": None}},
            )
        latest = max(strat.versions, key=lambda v: v.version)
        code = latest.source_code
    r = lint_source(code, body.profile)
    return LintResponse(**r)
