"""Strategy CRUD (§4.2)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studio_api.db import get_session
from studio_api.models import Strategy, StrategyVersion
from studio_api.schemas import (
    CreateStrategyBody,
    PatchStrategyBody,
    StrategyCreated,
    StrategyDetail,
    StrategyTemplateResponse,
)

router = APIRouter(prefix="/api/v1", tags=["strategies"])

STRATEGY_TEMPLATE = '''"""EasyQuant strategy — edit in Web Strategy Studio."""
from eqlib import *


def initialize(context):
    """Strategy initialization."""
    g.security = "601390"
    g.fast_period = 5
    g.slow_period = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    context.universe = [g.security]
    run_daily(market_open, time="every_bar")

    log.info("Backtest strategy init: %s" % g.security)


def market_open(context):
    """Daily trading logic."""
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

    if prev_fast <= prev_slow and fast_ma > slow_ma:
        if security not in context.portfolio.positions \
           or context.portfolio.positions[security].amount == 0:
            order_value(security, cash)
            log.info("Golden cross BUY: %s @ %.3f" % (security, current_price))

    elif prev_fast >= prev_slow and fast_ma < slow_ma:
        if security in context.portfolio.positions \
           and context.portfolio.positions[security].amount > 0:
            order_target(security, 0)
            log.info("Death cross SELL: %s @ %.3f" % (security, current_price))

    record(price=current_price, fast_ma=fast_ma, slow_ma=slow_ma)
'''


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


@router.post("/strategies", response_model=StrategyCreated, status_code=201)
async def create_strategy(body: CreateStrategyBody, session: AsyncSession = Depends(get_session)):
    sid = _new_id("strat")
    now = datetime.now(timezone.utc)
    dp = body.default_params.model_dump() if body.default_params else None
    strat = Strategy(
        id=sid,
        name=body.name,
        description=body.description,
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
    )
    session.add(strat)
    session.add(sv)
    await session.commit()
    return StrategyCreated(id=sid, name=body.name, version=1, created_at=now)


@router.get("/strategies/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(strategy_id: str, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(Strategy).options(selectinload(Strategy.versions)).where(Strategy.id == strategy_id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Strategy not found", "details": None}},
        )
    latest = max(strat.versions, key=lambda v: v.version)
    return StrategyDetail(
        id=strat.id,
        name=strat.name,
        description=strat.description,
        source_code=latest.source_code,
        version=strat.current_version,
        updated_at=strat.updated_at,
        default_params=strat.default_params,
    )


@router.patch("/strategies/{strategy_id}", response_model=StrategyCreated)
async def patch_strategy(
    strategy_id: str,
    body: PatchStrategyBody,
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(
        select(Strategy).options(selectinload(Strategy.versions)).where(Strategy.id == strategy_id)
    )
    strat = res.scalar_one_or_none()
    if strat is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Strategy not found", "details": None}},
        )
    now = datetime.now(timezone.utc)
    if body.name is not None:
        strat.name = body.name
    if body.description is not None:
        strat.description = body.description
    new_ver = strat.current_version + 1
    if body.source_code is not None:
        strat.current_version = new_ver
        strat.updated_at = now
        session.add(
            StrategyVersion(
                id=_new_id("sv"),
                strategy_id=strategy_id,
                version=new_ver,
                source_code=body.source_code,
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


@router.get("/strategies/{strategy_id}/template", response_model=StrategyTemplateResponse)
async def strategy_template(strategy_id: str):
    _ = strategy_id  # reserved for per-user templates
    return StrategyTemplateResponse(
        source_code=STRATEGY_TEMPLATE,
        hints=[
            "必须定义 initialize(context)",
            "使用 run_daily(market_open, time='every_bar') 注册每日逻辑",
            "顶层不要写 if __name__ == '__main__'，由运行器加载",
        ],
    )
