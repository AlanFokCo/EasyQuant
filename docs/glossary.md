# 词汇表 / Glossary

本词汇表解释了 EasyQuant 文档和 A 股量化回测中常见的专业术语。

---

## A

**Alpha (超额收益)**
策略相对于基准（如沪深300）的超额年化回报，经市场风险调整后剩余的「纯收益」部分。正 alpha 意味着策略在相同风险下表现优于基准。

**annualized return (年化收益率)**
将持有期总回报换算为「如果持有整整一年」的等效回报率。公式：`(1 + total_return) ** (365 / days) - 1`。

---

## B

**backtest (回测)**
在历史数据上模拟策略执行，以评估其潜在表现。EasyQuant 使用事件驱动引擎：每个交易日依次调用 `before_trading_start` → `run_daily` / `handle_data` → `after_trading_end`。

**benchmark (基准)**
用于衡量策略表现的参照指数，默认为沪深300（`000300.XSHG`）。Sharpe、alpha、beta 等指标都相对于基准计算。

**beta (贝塔)**
策略收益对基准收益的敏感度。beta = 1 表示与基准同涨同跌；beta > 1 放大波动；beta < 1 减弱波动。

**Brinson attribution (Brinson 归因)**
将超额收益分解为配置效应（allocation effect）、选股效应（selection effect）和交互效应（interaction effect）三部分，用于量化各层级决策的贡献。

---

## C

**Calmar ratio (卡玛比率)**
年化收益率 / 最大回撤绝对值。反映每承担单位回撤风险能获得多少年化收益。

**context (上下文)**
EasyQuant 在回测/实盘中传递给每个回调函数的对象，包含当前日期（`context.current_dt`）、投资组合状态（`context.portfolio`）、股票池（`context.universe`）等信息。

---

## D

**drawdown (回撤)**
从历史高点到当前点位的跌幅，通常以百分比表示。`max_drawdown`（最大回撤）是整个回测期间最大的峰谷跌幅，是衡量策略下行风险的核心指标。

---

## E

**event-driven (事件驱动)**
EasyQuant 的核心架构：不对全体历史数据做矢量化批量计算，而是按时间顺序逐条触发事件（每日开盘、收盘、数据到达），策略通过回调函数响应事件。这与 Zipline / JoinQuant 的设计一致。

---

## G

**g (全局对象)**
在 EasyQuant 策略中用 `g.xxx = ...` 存储策略级别全局变量的对象，生命周期与整次回测相同。类似 JoinQuant 的 `g`。

---

## I

**Information Ratio (信息比率 / IR)**
超额收益（策略 − 基准）的均值 / 超额收益的标准差 × √252。衡量每承担单位主动风险能获得多少超额收益。

---

## L

**look-ahead bias (未来函数 / 前视偏差)**
在回测中无意间使用了在当时不可知的未来数据，导致策略表现虚高。常见原因：直接调用实时行情接口、使用当日收盘价下单（应为次日开盘）、财务数据未按披露日期过滤。

**lot size (交易单位 / 手数)**
A 股最小买入单位为 1 手 = 100 股。EasyQuant 的 `order()` 系列函数自动将目标股数取整到 100 的倍数（T+1 规则下不允许当日买卖同一只股票）。

---

## M

**mark-to-market (盯市)**
按当前市价评估持仓价值，而非历史成本。`portfolio.total_value` 是实时盯市后的总资产，含现金和持仓市值。

**max drawdown (最大回撤)**
见 drawdown。

---

## P

**pending order (待成交委托)**
用 `order()` / `order_value()` 等函数下单后，订单不会立即成交，而是放入 `_pending_orders` 队列，在**下一个交易日开盘时**按开盘价撮合（T+1 规则）。

**portfolio (投资组合)**
通过 `context.portfolio` 访问，包含 `available_cash`（可用现金）、`total_value`（总资产）、`positions`（持仓字典，key 为股票代码）等字段。

---

## Q

**qfq / 前复权 (forward adjusted price)**
将历史股价按分红、送股、拆股等公司行为向前调整，使历史价格与当前价格连续可比。EasyQuant 默认使用前复权数据（`adjust='qfq'`）。

---

## R

**recorded_values (记录值)**
通过 `record(key=value)` 写入的每日自定义指标，存储在 `result['recorded_values']` 中，以日期为键，字典为值。用于在报告中绘制自定义曲线。

**risk-free rate (无风险利率)**
计算 Sharpe、Sortino 等指标时使用的基准回报率，默认取中国国债年化利率 3%（`RISK_FREE_RATE = 0.03`）。

---

## S

**Sharpe ratio (夏普比率)**
(年化收益率 − 年化无风险利率) / 年化波动率。衡量每承担单位总风险能获得多少超额收益。高夏普（> 1）通常被认为较好。

**Sortino ratio (索提诺比率)**
(年化收益率 − MAR) / 下行标准差。与 Sharpe 的区别在于只考虑下行波动（收益低于最低可接受回报 MAR = 0 的部分），对正波动不惩罚。

**ST (特别处理)**
沪深交易所对经营异常股票的特殊标记（*ST / ST）。ST 股涨跌幅限制为 ±5%，EasyQuant 的 `filter_st_stocks()` 函数可将 ST 股从股票池中排除。

---

## T

**T+1**
A 股交易规则：当日买入的股票最早可在下一交易日卖出。EasyQuant 通过 `_t1_locked_amounts` 强制执行此规则，防止回测中产生当日买卖的虚假信号。

**trading calendar (交易日历)**
A 股交易日历，排除节假日、周末。EasyQuant 优先使用新浪财经 `ak.tool_trade_date_hist_sina()` 获取精确交易日，并缓存在 `PreloadedData._dates` 中。

---

## U

**universe (股票池)**
策略运行的股票集合，通过 `context.universe` 访问，由 `set_universe()` 或在 `initialize()` 中赋值设置。

---

## W

**walk-forward analysis (滚动验证 / 走出样本)**
将历史期间分为交替的「样本内」（in-sample, IS）和「样本外」（out-of-sample, OOS）窗口：在 IS 窗口优化参数，在 OOS 窗口验证，然后拼接 OOS 曲线。用于检测过拟合。EasyQuant 通过 `eqlib.wfa.walk_forward()` 提供支持。
