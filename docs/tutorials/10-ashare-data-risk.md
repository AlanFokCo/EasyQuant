# Tutorial 10: A 股特色数据与组合风控

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 掌握 A 股特色数据 API 和组合风控监测器的使用 |
    | **预计用时** | 约 30 分钟 |
    | **前置** | [Tutorial 03](03-optimization.md)（策略优化） |

> A 股市场有其独特的微观结构——北向资金、融资融券、涨跌停板、限售股解禁——这些信号在海外市场并不存在或形态迥异。本篇将逐一讲解如何利用 `eqlib` 提供的四个 A 股特色 API 获取这些信号，并用 `PortfolioRiskMonitor` 构建组合级风控体系。

**文档索引：** [指南总览](../how-to/index.md) | **相关示例：** [Example 25](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/25_ashare_market_sentiment.py)

---

## 目录

1. [为什么需要 A 股特色数据](#1-为什么需要-a-股特色数据)
2. [北向资金流向](#2-北向资金流向)
3. [融资融券数据](#3-融资融券数据)
4. [涨跌停统计](#4-涨跌停统计)
5. [限售股解禁](#5-限售股解禁)
6. [组合风控：PortfolioRiskMonitor](#6-组合风控portfolioriskmonitor)
7. [每日风控检查与熔断](#7-每日风控检查与熔断)
8. [综合案例：带风控的北向资金策略](#8-综合案例带风控的北向资金策略)
9. [小结与下一步](#9-小结与下一步)

---

## 1. 为什么需要 A 股特色数据

传统量化框架（如 Zipline、Backtrader）主要面向美股，提供的是价量、基本面等"通用"数据。A 股市场的参与者结构、交易制度不同，衍生出几类**独有信号**：

| 信号 | 含义 | 为什么重要 |
|------|------|-----------|
| **北向资金** | 沪股通 + 深股通的外资净流入/流出 | 被市场视为"聪明钱"，其动向常被用来判断中短期趋势 |
| **融资融券** | 全市场杠杆资金的融资余额和融券余额 | 反映散户与机构的杠杆情绪，余额飙升常预示过热 |
| **涨跌停统计** | 每日涨停/跌停股票数量 | 衡量市场宽度（breadth），大面积跌停是系统性风险信号 |
| **限售股解禁** | 即将解禁的限售股列表和市值 | 潜在卖压的预警，大市值解禁前股价常承压 |

将以上信号融入策略，可以让回测更贴近 A 股真实环境，减少"信号盲区"。

---

## 2. 北向资金流向

### 2.1 API 概览

```python
from eqlib import get_north_money_flow
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_date` | str / datetime | 开始日期（默认近 30 天） |
| `end_date` | str / datetime | 结束日期（默认今天，中国时区） |

**返回 DataFrame**：

| 列名 | 说明 | 单位 |
|------|------|------|
| `date` | 交易日期 | YYYY-MM-DD |
| `net_buy` | 净买入额（沪股通 + 深股通合计） | 亿元 |
| `total_buy` | 总买入额 | 亿元 |
| `total_sell` | 总卖出额 | 亿元 |

> **提示**：数据源为沪股通 + 深股通合计，缓存有效期 1 小时。使用中国时区 (UTC+8) 确定"今天"，避免跨时区服务器获取错误日期。

### 2.2 基础用法：计算滚动净买入

```python
from eqlib import get_north_money_flow
from datetime import datetime, timedelta

# 获取近 3 个月数据
end_date = datetime.now().date()
start_date = end_date - timedelta(days=90)

north = get_north_money_flow(start_date=start_date, end_date=end_date)

if not north.empty:
    # 5 日和 20 日滚动净买入
    north["rolling_5d"] = north["net_buy"].rolling(5).sum()
    north["rolling_20d"] = north["net_buy"].rolling(20).sum()

    print(north[["date", "net_buy", "rolling_5d", "rolling_20d"]].tail(10))
```

### 2.3 策略应用：北向资金趋势信号

```python
from eqlib import get_north_money_flow
from datetime import datetime, timedelta

def north_capital_signal():
    """根据北向资金判断市场情绪。"""
    north = get_north_money_flow(
        start_date=datetime.now().date() - timedelta(days=60)
    )
    if north.empty:
        return "neutral"

    north["rolling_5d"] = north["net_buy"].rolling(5).sum()
    north["rolling_20d"] = north["net_buy"].rolling(20).sum()

    latest_5d = north["rolling_5d"].iloc[-1]
    latest_20d = north["rolling_20d"].iloc[-1]

    if latest_5d > 50 and latest_20d > 100:
        return "bullish"          # 强势流入，看多
    elif latest_5d < -50 and latest_20d < -100:
        return "bearish"          # 强势流出，看空
    elif latest_5d > 0:
        return "neutral_bullish"  # 温和流入
    elif latest_5d < 0:
        return "neutral_bearish"  # 温和流出
    else:
        return "neutral"

# 使用
signal = north_capital_signal()
print(f"北向资金情绪: {signal}")
```

---

## 3. 融资融券数据

### 3.1 API 概览

```python
from eqlib import get_margin_data
```

**返回 DataFrame**：

| 列名 | 说明 | 单位 |
|------|------|------|
| `date` | 交易日期 | YYYY-MM-DD |
| `margin_balance` | 融资余额（沪市 + 深市合计） | 亿元 |
| `margin_buy` | 融资买入额 | 亿元 |
| `margin_repay` | 融资偿还额 | 亿元 |
| `short_balance` | 融券余额 | 亿元 |

> **注意**：`margin_repay` 的第一行为 `NaN`（无前日余额可计算），使用时需 `dropna()` 或 `fillna(0)` 处理。计算公式为：`margin_repay = 前日融资余额 + 当日融资买入 - 当日融资余额`。

### 3.2 计算融资余额变化率

融资余额的**边际变化**比绝对值更有意义——快速上升往往预示杠杆过热。

```python
from eqlib import get_margin_data
from datetime import datetime, timedelta

end_date = datetime.now().date()
start_date = end_date - timedelta(days=60)

margin = get_margin_data(start_date=start_date, end_date=end_date)

if not margin.empty:
    # 日环比变化率
    margin["balance_change_pct"] = margin["margin_balance"].pct_change()

    # 5 日平均变化率
    margin["balance_change_5d"] = margin["balance_change_pct"].rolling(5).mean()

    # 杠杆过热预警：5 日平均变化率超过 0.5%
    latest_change = margin["balance_change_5d"].dropna().iloc[-1]
    if latest_change > 0.005:
        print(f"⚠️ 杠杆过热预警：融资余额 5 日平均变化率 {latest_change:.4%}")
    elif latest_change < -0.005:
        print(f"📉 去杠杆信号：融资余额 5 日平均变化率 {latest_change:.4%}")
    else:
        print(f"✅ 杠杆情绪平稳：{latest_change:.4%}")
```

### 3.3 融资买入占比

融资买入额占融资余额的比例，可以衡量**新增杠杆的激进程度**：

```python
if not margin.empty:
    margin["buy_ratio"] = margin["margin_buy"] / margin["margin_balance"]
    print(f"最新融资买入占比: {margin['buy_ratio'].iloc[-1]:.4%}")
```

---

## 4. 涨跌停统计

### 4.1 API 概览

```python
from eqlib import get_limit_up_down_stats
```

**返回 DataFrame**：

| 列名 | 说明 |
|------|------|
| `date` | 交易日期 |
| `limit_up_count` | 涨停股票数量 |
| `limit_down_count` | 跌停股票数量 |

> **重要限制**：该 API **仅支持最近 30 个交易日**的数据。超出范围会打印警告，返回结果可能不完整。缓存有效期 30 分钟（交易时段内数据会变化）。

### 4.2 系统性风险预警

大面积跌停（如超过 100 只）是市场恐慌的明确信号：

```python
from eqlib import get_limit_up_down_stats
from datetime import datetime, timedelta

end_date = datetime.now().date()
start_date = end_date - timedelta(days=15)

stats = get_limit_up_down_stats(start_date=start_date, end_date=end_date)

if not stats.empty:
    print("近期涨跌停统计：")
    print(stats[["date", "limit_up_count", "limit_down_count"]].tail(5))

    # 系统性风险预警
    latest_down = stats["limit_down_count"].iloc[-1]
    if latest_down > 100:
        print(f"🚨 系统性风险预警：{latest_down} 只股票跌停")
    elif latest_down > 50:
        print(f"⚠️ 市场情绪偏弱：{latest_down} 只股票跌停")

    # 市场宽度指标：涨停/跌停比
    stats["up_down_ratio"] = (
        stats["limit_up_count"] / stats["limit_down_count"].replace(0, 1)
    )
    avg_ratio = stats["up_down_ratio"].mean()
    print(f"平均涨停/跌停比: {avg_ratio:.2f}")
```

### 4.3 在策略中使用涨跌停过滤

```python
def market_breadth_ok():
    """检查市场宽度是否正常（跌停数量不超过阈值）。"""
    stats = get_limit_up_down_stats()  # 默认近 30 天
    if stats.empty:
        return True  # 数据不可用时，默认放行

    recent_3d = stats.tail(3)
    avg_down = recent_3d["limit_down_count"].mean()

    return avg_down < 30  # 近 3 日平均跌停 < 30 只时，认为市场正常
```

---

## 5. 限售股解禁

### 5.1 API 概览

```python
from eqlib import get_restriction_release
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `days` | int | 未来天数范围，默认 30 天。如果为 `None` 或 < 1，使用默认值 |

**返回 DataFrame**：

| 列名 | 说明 | 单位 |
|------|------|------|
| `code` | 股票代码 | 6 位数字 |
| `name` | 股票名称 | — |
| `release_date` | 解禁日期 | YYYY-MM-DD |
| `release_amount` | 解禁数量 | 万股 |
| `release_value` | 解禁市值 | 亿元 |
| `release_pct` | 占解禁前流通市值比例 | — |

> **提示**：缓存有效期 6 小时（解禁数据日内不变化）。

### 5.2 查看即将解禁的股票

```python
from eqlib import get_restriction_release

# 获取未来 30 天解禁列表
releases = get_restriction_release(days=30)

if not releases.empty:
    # 按解禁市值降序
    top_releases = releases.sort_values("release_value", ascending=False)
    print("未来 30 天解禁市值 Top 10：")
    print(top_releases[["code", "name", "release_date", "release_value"]].head(10))

    # 统计：大市值解禁数量（>10 亿元）
    big_releases = releases[releases["release_value"] > 10]
    print(f"\n解禁市值超 10 亿元的股票数量: {len(big_releases)}")
```

### 5.3 选股时排除即将解禁的股票

大额解禁往往带来卖压，可以在选股阶段排除：

```python
def filter_restricted_stocks(candidate_codes, days=15, value_threshold=5):
    """从候选列表中排除未来有大额解禁的股票。

    Args:
        candidate_codes: 候选股票代码列表（6 位数字）
        days: 未来天数范围
        value_threshold: 解禁市值阈值（亿元）

    Returns:
        过滤后的代码列表
    """
    releases = get_restriction_release(days=days)
    if releases.empty:
        return candidate_codes

    # 解禁市值 > 阈值 或 占流通比 > 5% 的股票
    risky = releases[
        (releases["release_value"] > value_threshold)
        | (releases["release_pct"] > 0.05)
    ]
    risky_codes = set(risky["code"].tolist())

    filtered = [c for c in candidate_codes if c not in risky_codes]
    excluded = len(candidate_codes) - len(filtered)
    if excluded > 0:
        print(f"排除 {excluded} 只有大额解禁风险的股票")

    return filtered
```

---

## 6. 组合风控：PortfolioRiskMonitor

当你运行多个策略时，单策略层面的风控不够——你需要**组合级**视角，审视策略之间的相关性、整体 VaR、持仓集中度等。

### 6.1 创建监控器

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

# 使用默认阈值
monitor = PortfolioRiskMonitor()

# 或自定义阈值
custom_thresholds = RiskThresholds(
    max_drawdown_yellow=0.12,    # 黄色预警回撤
    max_drawdown_red=0.18,       # 红色预警回撤
    max_drawdown_kill=0.25,      # 熔断回撤
    correlation_yellow=0.55,     # 黄色预警相关性
    correlation_red=0.70,        # 红色预警相关性
    correlation_kill=0.85,       # 熔断相关性
    single_stock_max=0.08,       # 单股票最大占比
    single_sector_max=0.25,      # 单板块最大占比
    small_cap_max=0.15,          # 微盘股最大占比（市值 < 50 亿）
    var_confidence=0.95,         # VaR 置信水平
)
monitor = PortfolioRiskMonitor(thresholds=custom_thresholds)
```

### 6.2 添加策略回测结果

```python
from eqlib import run_backtest

# 策略 A：均线策略
result_a = run_backtest(
    initialize_ma,
    start_date="2024-01-01",
    end_date="2024-12-31",
    starting_cash=100000,
)

# 策略 B：动量策略
result_b = run_backtest(
    initialize_momentum,
    start_date="2024-01-01",
    end_date="2024-12-31",
    starting_cash=100000,
)

monitor.add_strategy("均线策略", result_a)
monitor.add_strategy("动量策略", result_b)
```

> **注意**：`add_strategy` 接收的是 `run_backtest()` 返回的 result dict，其中必须包含 `recorded_values` 数据。如果数据为空或缺失，会抛出 `ValueError`。

### 6.3 计算组合 VaR

VaR（Value at Risk）衡量在给定置信水平下，组合可能遭受的最大日损失：

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
print(f"95% 置信水平下，组合日 VaR: {var_amount:,.0f} 元 ({var_pct:.2%})")
```

| VaR 百分比 | 风险水平 | 建议 |
|-----------|---------|------|
| < 1% | 低风险 | 正常运行 |
| 1% - 2% | 中等风险 | 关注 |
| > 2% | 较高风险 | 考虑降低仓位 |

> **说明**：VaR 使用历史模拟法计算，要求每个策略至少有 30 天的日收益率数据。数据不足的策略会被自动排除，并在日志中提示。当所有策略数据不足时，返回 `(nan, nan)`。

### 6.4 策略相关性矩阵

高相关性意味着策略"同涨同跌"，分散化效果差：

```python
corr = monitor.correlation_matrix()
if not corr.empty:
    print("策略相关性矩阵：")
    print(corr)

    # 检查是否存在过高相关性
    max_corr = 0.0
    for i in range(len(corr)):
        for j in range(i + 1, len(corr)):
            if abs(corr.iloc[i, j]) > max_corr:
                max_corr = abs(corr.iloc[i, j])

    if max_corr > 0.75:
        print(f"⚠️ 策略间最高相关性 {max_corr:.2f}，分散化效果不足")
```

| 相关性 | 含义 | 建议 |
|-------|------|------|
| < 0.3 | 低相关 | 理想，策略分散效果好 |
| 0.3 - 0.6 | 中度相关 | 可接受 |
| > 0.6 | 高相关 | 注意风险分散不足（黄色预警） |
| > 0.85 | 极高相关 | 熔断预警 |

> **提示**：策略数 < 2 时，`correlation_matrix()` 返回空 DataFrame。

### 6.5 集中度风险

```python
concentration = monitor.concentration_risk()
print(f"持仓股票数: {concentration['num_holdings']}")
print(f"单股票最大占比: {concentration['max_single_stock']:.2%}")
print(f"前三大持仓占比: {concentration['top3_concentration']:.2%}")
```

| 返回值字段 | 说明 |
|-----------|------|
| `max_single_stock` | 单只股票在组合中的最大占比 |
| `max_single_sector` | 单个板块在组合中的最大占比 |
| `small_cap_pct` | 微盘股（市值 < 50 亿）占比 |
| `num_holdings` | 持仓股票总数 |
| `top3_concentration` | 前三大持仓合计占比 |

---

## 7. 每日风控检查与熔断

### 7.1 运行每日检查

`daily_check()` 是风控的主入口，它会综合 VaR、相关性、集中度、市场 regime 等维度，生成一份 `RiskReport`：

```python
from eqlib import PortfolioRiskMonitor, check_kill_switch

monitor = PortfolioRiskMonitor()
monitor.add_strategy("均线策略", result_a)
monitor.add_strategy("动量策略", result_b)

report = monitor.daily_check()

print(f"预警级别: {report.alert_level.value}")
print(f"组合 VaR: {report.portfolio_var:,.0f} 元")
print(f"市场 regime: {report.regime}")

if report.triggers:
    print("触发的预警：")
    for t in report.triggers:
        print(f"  - {t}")

if report.recommendations:
    print("建议操作：")
    for r in report.recommendations:
        print(f"  - {r}")
```

### 7.2 三级预警体系

| 级别 | 枚举值 | 含义 | 动作 |
|------|--------|------|------|
| `YELLOW` | `"yellow"` | 监控关注 | 不触发自动动作，加强观察 |
| `RED` | `"red"` | 需要人工介入 | 发送通知，建议调仓 |
| `KILL_SWITCH` | `"kill"` | 自动熔断 | 暂停策略，等待人工确认 |

触发条件（默认阈值）：

| 维度 | YELLOW | RED | KILL_SWITCH |
|------|--------|-----|-------------|
| 策略相关性 | ≥ 0.60 | ≥ 0.75 | ≥ 0.85 |
| 单股票占比 | > 10% | > 20% | — |
| 单板块占比 | > 30% | — | — |
| 微盘股占比 | > 20% | — | — |
| 市场 regime | 震荡市 | — | 熊市 |

### 7.3 熔断检查

`check_kill_switch()` 根据报告中的触发条件，返回需要立即执行的操作列表：

```python
actions = check_kill_switch(report)

if actions:
    print("⚠️ 需要立即执行的操作：")
    for action in actions:
        print(f"  {action}")
else:
    print("✅ 无需熔断操作")
```

`KILL_SWITCH` 级别的熔断操作示例：

- 「暂停所有策略，等待人工确认」
- 「降低高相关性策略仓位 50%」
- 「减仓超标股票」

`RED` 级别的建议操作：

- 「建议降低高相关性策略仓位」
- 「建议人工检查策略状态」

### 7.4 在实盘中集成风控

使用 `before_trading_start` 回调在每日开盘前执行风控检查：

```python
from eqlib import (
    before_trading_start, PortfolioRiskMonitor,
    check_kill_switch, AlertLevel, log,
)

monitor = PortfolioRiskMonitor()

def risk_check_callback(context, data):
    """每日开盘前风控检查。"""
    report = monitor.daily_check()

    if report.alert_level == AlertLevel.KILL_SWITCH:
        log.warning(f"🚨 熔断预警！触发条件: {report.triggers}")
        actions = check_kill_switch(report)
        for action in actions:
            log.warning(action)
        # 在实际交易中，此处应调用清仓接口或发送紧急通知

    elif report.alert_level == AlertLevel.RED:
        log.warning(f"🔴 红色预警: {report.triggers}")
        for rec in report.recommendations:
            log.info(f"  建议: {rec}")

    elif report.triggers:
        log.info(f"🟡 关注: {report.triggers}")

# 在 initialize 中注册回调
def initialize(context):
    before_trading_start(risk_check_callback)
    # ... 其他初始化
```

> **说明**：`before_trading_start` 注册的回调在每个交易日的 09:30 之前执行，签名为 `(context, data)`。与 `run_daily(func, time='09:30')` 不同，它在市场开盘前就运行，适合做盘前检查。

---

## 8. 综合案例：带风控的北向资金策略

以下是一个完整的策略示例，将北向资金信号与风控检查结合：

```python
"""带风控的北向资金策略。

策略逻辑：
- 北向资金 5 日净流入 > 50 亿 且 20 日净流入 > 100 亿 → 看多
- 北向资金 5 日净流出 > 50 亿 → 减仓
- 每日开盘前检查市场宽度（跌停数量）
"""

from eqlib import (
    run_backtest, analyze_returns, order_target, order_value,
    get_north_money_flow, get_limit_up_down_stats,
    before_trading_start, g, log, set_benchmark, attribute_history,
)
from datetime import datetime, timedelta


def initialize(context):
    """策略初始化。"""
    g.security = "601390"      # 中国中铁
    g.position_pct = 0.8       # 最大仓位比例
    g.can_trade = True         # 风控熔断标记

    set_benchmark("000300.XSHG")

    # 注册每日开盘前风控检查
    before_trading_start(before_market_check)


def before_market_check(context, data):
    """每日开盘前：检查北向资金 + 市场宽度。"""
    current_date = context.current_dt.date()

    # ── 1. 北向资金信号 ──────────────────────────────
    north = get_north_money_flow(
        start_date=current_date - timedelta(days=60),
        end_date=current_date,
    )

    if not north.empty:
        north["rolling_5d"] = north["net_buy"].rolling(5).sum()
        north["rolling_20d"] = north["net_buy"].rolling(20).sum()

        latest_5d = north["rolling_5d"].iloc[-1]
        latest_20d = north["rolling_20d"].iloc[-1]

        # 强势流出 → 降低仓位
        if latest_5d < -50 and latest_20d < -100:
            g.position_pct = 0.3
            log.info(
                f"北向资金流出信号: 5日={latest_5d:.1f}亿, "
                f"20日={latest_20d:.1f}亿, 降仓至30%"
            )
        # 强势流入 → 恢复正常仓位
        elif latest_5d > 50 and latest_20d > 100:
            g.position_pct = 0.8
            log.info(
                f"北向资金流入信号: 5日={latest_5d:.1f}亿, "
                f"20日={latest_20d:.1f}亿, 仓位80%"
            )

    # ── 2. 市场宽度检查 ──────────────────────────────
    stats = get_limit_up_down_stats(
        start_date=current_date - timedelta(days=5),
        end_date=current_date,
    )

    if not stats.empty:
        recent_down = stats.tail(3)["limit_down_count"].mean()
        if recent_down > 100:
            g.can_trade = False
            log.warning(
                f"🚨 市场恐慌：近 3 日平均 {recent_down:.0f} 只跌停，暂停交易"
            )
        elif recent_down > 50:
            g.position_pct = min(g.position_pct, 0.3)
            log.warning(
                f"⚠️ 市场偏弱：近 3 日平均 {recent_down:.0f} 只跌停，限制仓位"
            )
        else:
            g.can_trade = True


def handle_data(context, data):
    """每日交易逻辑。"""
    if not g.can_trade:
        return

    # 均线信号
    prices = attribute_history(g.security, 20, "1d", ["close"])
    if len(prices) < 20:
        return

    ma5 = prices["close"].iloc[-5:].mean()
    ma20 = prices["close"].mean()

    total_value = context.portfolio.total_value
    target_value = total_value * g.position_pct

    if ma5 > ma20:
        # 短期均线在上 → 买入至目标仓位
        order_target(g.security, value=target_value)
    elif ma5 < ma20 * 0.98:
        # 短期均线明显在下 → 清仓
        order_target(g.security, value=0)


# ── 运行回测 ──────────────────────────────────────────
if __name__ == "__main__":
    result = run_backtest(
        initialize,
        start_date="2024-01-01",
        end_date="2024-12-31",
        starting_cash=100000,
    )

    metrics = analyze_returns(result, risk_free_rate=0.03)
    print(f"年化收益: {metrics['annual_return']:.2%}")
    print(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
    print(f"最大回撤: {metrics['max_drawdown']:.2%}")
```

### 案例要点

1. **`before_trading_start` 注册**：在 `initialize` 中调用，确保每天开盘前执行风控检查；回调签名为 `(context, data)`
2. **信号分层**：北向资金提供"大方向"信号（加仓/减仓），均线提供"入场/离场"时机
3. **风控熔断**：`g.can_trade` 标记在 `before_market_check` 中设置，`handle_data` 中检查
4. **仓位动态调整**：`g.position_pct` 根据市场状态在 30%~80% 之间浮动

---

## 9. 小结与下一步

### 本篇要点回顾

| API / 工具 | 用途 | 关键注意事项 |
|-----------|------|-------------|
| `get_north_money_flow` | 北向资金净流入/流出 | 单位：亿元；1 小时缓存 |
| `get_margin_data` | 融资融券余额与买卖 | `margin_repay` 首行为 NaN |
| `get_limit_up_down_stats` | 涨跌停股票数量统计 | 仅支持最近 30 个交易日 |
| `get_restriction_release` | 限售股解禁列表 | 单位：万股/亿元；6 小时缓存 |
| `PortfolioRiskMonitor` | 组合级风控监测 | VaR 需 ≥30 天数据 |
| `check_kill_switch` | 熔断操作检查 | 三级预警：YELLOW / RED / KILL_SWITCH |

### 相关示例

- **[Example 25](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/25_ashare_market_sentiment.py)**：A 股市场情绪指标——完整演示四个数据 API 的用法
- **[Example 08](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/08_lifecycle_callbacks.py)**：生命周期回调——`before_trading_start` 与 `after_trading_end` 的详细用法

### 下一步

- [Tutorial 05: 模拟盘到实盘](04-live-trading.md)：将带风控的策略部署到模拟交易
- [Tutorial 09: 策略参数优化与审计](09-param-optimization.md)：用参数化方法优化本篇的策略参数
- 尝试将 `PortfolioRiskMonitor` 添加到你的多策略组合中，检查策略间相关性是否过高
