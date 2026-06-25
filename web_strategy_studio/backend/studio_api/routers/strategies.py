"""Strategy CRUD (§4.2) — with versioning correctness (B4/B15)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api import auth as auth_mod
from studio_api.config import settings
from studio_api.db import get_session
from studio_api.models import Strategy, StrategyVersion, User
from studio_api.schemas import (
    CreateStrategyBody,
    DiffResponse,
    PatchStrategyBody,
    SnapshotBody,
    StrategyCreated,
    StrategyDetail,
    StrategyTemplateResponse,
    StrategyVersionItem,
    TemplateDetail,
    TemplateSummary,
    api_error,
)
from studio_api.services.template_service import TemplateService
from studio_api.services.version_service import VersionService

router = APIRouter(prefix="/api/v1", tags=["strategies"])

STRATEGY_TEMPLATE = '''"""EasyQuant 均线交叉策略 — 在 Web Studio 中编辑并运行回测."""
from eqlib import *


def initialize(context):
    """Strategy initialization."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.00025,
        close_commission=0.00025,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Backtest strategy init: %s" % g.security)


def market_open(context):
    """每日交易逻辑：均线金叉买入，死叉卖出."""
    security = g.security
    close_data = attribute_history(security, 25, "1d", ["close"])

    if close_data.empty or len(close_data) < g.slow_period:
        return

    fast_ma = close_data["close"].tail(g.fast_period).mean()
    slow_ma = close_data["close"].tail(g.slow_period).mean()
    current_price = close_data["close"].iloc[-1]

    prev_fast = close_data["close"].tail(g.fast_period + 1).head(g.fast_period).mean()
    prev_slow = close_data["close"].tail(g.slow_period + 1).head(g.slow_period).mean()

    cash = context.portfolio.available_cash

    # 金叉买入
    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \\
           or context.portfolio.positions[security].amount == 0:
            order_value(security, cash)
            log.info("Golden cross BUY: %s @ %.3f" % (security, current_price))

    # 死叉卖出
    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \\
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Death cross SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma)
'''


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _hash(source_code: str) -> str:
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def _get_current_version(strat: Strategy) -> StrategyVersion:
    """Return the StrategyVersion row that matches strat.current_version (B15)."""
    for v in strat.versions:
        if v.version == strat.current_version:
            return v
    # Fallback: max version (shouldn't happen in a consistent DB)
    return max(strat.versions, key=lambda v: v.version)


@router.post("/strategies", response_model=StrategyCreated, status_code=201)
async def create_strategy(
    body: CreateStrategyBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    sid = _new_id("strat")
    now = datetime.now(timezone.utc)
    dp = body.default_params.model_dump() if body.default_params else None
    strat = Strategy(
        id=sid,
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
        current_version=1,
        default_params=dp,
        created_at=now,
        updated_at=now,
    )
    sv = StrategyVersion(
        id=_new_id("sv"),
        strategy_id=sid,
        version=1,
        source_code=body.source_code,
        content_hash=_hash(body.source_code),
    )
    session.add(strat)
    session.add(sv)
    await session.commit()
    return StrategyCreated(id=sid, name=body.name, version=1, created_at=now)


@router.get("/strategies/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(
    strategy_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    # B15: look up by current_version PK, not max(versions)
    sv = _get_current_version(strat)
    return StrategyDetail(
        id=strat.id,
        name=strat.name,
        description=strat.description,
        source_code=sv.source_code,
        version=strat.current_version,
        updated_at=strat.updated_at,
        default_params=strat.default_params,
    )


@router.patch("/strategies/{strategy_id}", response_model=StrategyCreated)
async def patch_strategy(
    strategy_id: str,
    body: PatchStrategyBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    # HIGH-19: optimistic lock — reject if caller's expected_version doesn't match
    if body.expected_version is not None and body.expected_version != strat.current_version:
        raise HTTPException(
            status_code=409,
            detail=api_error(
                "VERSION_CONFLICT",
                f"expected v{body.expected_version}, server is at v{strat.current_version}",
            ),
        )
    now = datetime.now(timezone.utc)
    if body.name is not None:
        strat.name = body.name
    if body.description is not None:
        strat.description = body.description
    if body.source_code is not None:
        new_hash = _hash(body.source_code)
        current_sv = _get_current_version(strat)
        # B4: only create a new version row when content actually changed.
        if current_sv.content_hash == new_hash or current_sv.source_code == body.source_code:
            # Identical content: no new version, just touch updated_at.
            strat.updated_at = now
        else:
            # Check if the current version was created recently (draft window).
            coalesce = False
            if current_sv.created_at:
                age_sec = (
                    now.replace(tzinfo=timezone.utc)
                    - current_sv.created_at.replace(tzinfo=timezone.utc)
                ).total_seconds()
                coalesce = (age_sec < settings.version_coalesce_sec) and (current_sv.label is None)
            if coalesce:
                # HIGH-19: when expected_version is provided, skip the coalesce
                # path and always create a proper new version.  This ensures two
                # concurrent writes that both arrive with expected_version=N will
                # each bump the version: the first succeeds (N→N+1), the second
                # hits the top-level check above (expected N, server is N+1) → 409.
                if body.expected_version is not None:
                    new_ver = strat.current_version + 1
                    strat.current_version = new_ver
                    strat.updated_at = now
                    session.add(
                        StrategyVersion(
                            id=_new_id("sv"),
                            strategy_id=strategy_id,
                            version=new_ver,
                            source_code=body.source_code,
                            content_hash=new_hash,
                        )
                    )
                else:
                    # Reuse the current version row (update in place).
                    current_sv.source_code = body.source_code
                    current_sv.content_hash = new_hash
                    strat.updated_at = now
            else:
                # Create a proper new version.
                new_ver = strat.current_version + 1
                strat.current_version = new_ver
                strat.updated_at = now
                session.add(
                    StrategyVersion(
                        id=_new_id("sv"),
                        strategy_id=strategy_id,
                        version=new_ver,
                        source_code=body.source_code,
                        content_hash=new_hash,
                    )
                )
    else:
        strat.updated_at = now
    await session.commit()
    await session.refresh(strat)
    return StrategyCreated(
        id=strat.id,
        name=strat.name,
        version=strat.current_version,
        created_at=strat.updated_at or now,
    )


@router.post("/strategies/{strategy_id}/snapshot", response_model=StrategyCreated, status_code=201)
async def create_snapshot(
    strategy_id: str,
    body: SnapshotBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    """Force-create a new named version (Cmd+S).

    Unlike PATCH, this always creates a new version row with the current
    source code, optionally tagging it with a human-readable label.
    """
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    current_sv = _get_current_version(strat)
    now = datetime.now(timezone.utc)
    new_ver = strat.current_version + 1
    strat.current_version = new_ver
    strat.updated_at = now
    session.add(
        StrategyVersion(
            id=_new_id("sv"),
            strategy_id=strategy_id,
            version=new_ver,
            source_code=current_sv.source_code,
            content_hash=current_sv.content_hash or _hash(current_sv.source_code),
            label=body.label,
        )
    )
    await session.commit()
    await session.refresh(strat)
    return StrategyCreated(
        id=strat.id,
        name=strat.name,
        version=strat.current_version,
        created_at=now,
    )


@router.get("/strategies/{strategy_id}/versions", response_model=List[StrategyVersionItem])
async def list_strategy_versions(
    strategy_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    """List all versions of a strategy in ascending order."""
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    return [
        StrategyVersionItem(
            version=v.version,
            label=v.label,
            content_hash=v.content_hash,
            created_at=v.created_at,
        )
        for v in sorted(strat.versions, key=lambda v: v.version)
    ]


@router.get("/strategies/{strategy_id}/versions/{version}", response_model=StrategyDetail)
async def get_strategy_version(
    strategy_id: str,
    version: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    """Fetch a specific version's source code."""
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    sv = next((v for v in strat.versions if v.version == version), None)
    if sv is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Version not found"))
    return StrategyDetail(
        id=strat.id,
        name=strat.name,
        description=strat.description,
        source_code=sv.source_code,
        version=sv.version,
        updated_at=sv.created_at,
        default_params=strat.default_params,
    )


@router.post("/strategies/{strategy_id}/versions/{version}/restore", response_model=StrategyCreated)
async def restore_strategy_version(
    strategy_id: str,
    version: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    """Restore a previous version by branching it as the new current version."""
    res = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.versions))
        .where(Strategy.id == strategy_id, Strategy.owner_id == current_user.id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))
    sv = next((v for v in strat.versions if v.version == version), None)
    if sv is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Version not found"))
    now = datetime.now(timezone.utc)
    new_ver = strat.current_version + 1
    strat.current_version = new_ver
    strat.updated_at = now
    session.add(
        StrategyVersion(
            id=_new_id("sv"),
            strategy_id=strategy_id,
            version=new_ver,
            source_code=sv.source_code,
            content_hash=sv.content_hash or _hash(sv.source_code),
            label=f"restore from v{version}",
        )
    )
    await session.commit()
    await session.refresh(strat)
    return StrategyCreated(
        id=strat.id,
        name=strat.name,
        version=strat.current_version,
        created_at=now,
    )


@router.get("/strategies/{strategy_id}/template", response_model=StrategyTemplateResponse)
async def strategy_template(
    strategy_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
):
    _ = strategy_id  # reserved for per-user templates
    return StrategyTemplateResponse(
        source_code=STRATEGY_TEMPLATE,
        hints=[
            "必须定义 initialize(context)",
            "使用 run_daily(market_open, time='every_bar') 注册每日逻辑",
            "顶层不要写 if __name__ == '__main__'，由运行器加载",
        ],
    )


# ---------------------------------------------------------------------------
# Version diff (§3.1 — Module A enhancement)
# ---------------------------------------------------------------------------

_version_service = VersionService()


@router.get(
    "/strategies/{strategy_id}/versions/{from_version}/diff/{to_version}",
    response_model=DiffResponse,
)
async def diff_versions(
    strategy_id: str,
    from_version: int,
    to_version: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(auth_mod.get_current_user),
):
    """Generate a unified diff between two versions of a strategy."""
    # Verify ownership
    res = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.owner_id == current_user.id,
        )
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Strategy not found"))

    result = await _version_service.get_diff(
        session, strategy_id, from_version, to_version
    )
    if result is None:
        raise HTTPException(status_code=404, detail=api_error("NOT_FOUND", "Version not found"))
    return DiffResponse(**result)


# ---------------------------------------------------------------------------
# Template endpoints (§3.1 — Module A enhancement)
# ---------------------------------------------------------------------------

_template_service = TemplateService()


@router.get("/templates", response_model=List[TemplateSummary])
async def list_templates(
    current_user: User = Depends(auth_mod.get_current_user),
):
    """List all available strategy templates (summary only)."""
    return [TemplateSummary(**t) for t in _template_service.get_templates()]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: str,
    current_user: User = Depends(auth_mod.get_current_user),
):
    """Get a specific template with full code."""
    template = _template_service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=api_error("NOT_FOUND", f"Template '{template_id}' not found"),
        )
    return TemplateDetail(**template)
