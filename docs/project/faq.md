# 常见问题（FAQ）

> 排错与常见疑问。操作类指南请查看 [操作指南](../how-to/index.md)。

### 按主题跳转

| 你遇到的问题 | 跳到 |
|--------------|------|
| Python 版本、`pip install`、`import eqlib` | [安装与环境](#安装与环境) |
| 首次回测慢、无数据、分钟线 / Tick | [数据与网络](#数据与网络) |
| 无交易、T+1、下单数量、基准 | [回测与策略](#回测与策略) |
| PNG 空、HTML 空白、JSON 里数字对不上 | [报告与分析](#报告与分析) |
| 模拟盘、导出 PTrade / QMT | [模拟盘与导出](#模拟盘与导出) |
| 改源码、跑单元测试 | [开发与测试](#开发与测试) |

---

## 安装与环境

### Q: `pip install .` 报错「requires a different Python: 3.9.x not in '>=3.10'」

**原因：**`eqlib` 要求 **Python ≥ 3.10**（见 `pyproject.toml` 中 `requires-python`）。

**处理：**安装并使用 3.10 / 3.11 / 3.12，例如：

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Q: 只装了 `akshare` 等依赖，`import eqlib` 仍失败

**原因：**`eqlib` 是本项目包，需从 PyPI 或仓库安装。

**处理：**

```bash
# 方式一：PyPI 安装（推荐，无需克隆仓库）
pip install easyquant-eqlib

# 方式二：从源码安装（在仓库根目录）
cd /path/to/EasyQuant
pip install .
```

安装后任意工作目录均可 `import eqlib`。运行 `examples/` 下脚本前同样建议先完成上述安装（示例不再自动改写 `sys.path` 以导入 `eqlib`）。

### Q: 需要安装哪些依赖？

**最小集（已由 `pip install .` 或 `pip install easyquant-eqlib` 安装）：**`akshare`、`chinese_calendar`、`pandas`、`numpy`、`matplotlib`、`scipy`、`scikit-learn`、`requests`。

**可选：**`pip install pyarrow` 以提升部分磁盘缓存性能（见 `pyproject.toml` 的 `[project.optional-dependencies]`）。

---

## 数据与网络

### Q: 首次回测很慢或卡住

**常见原因：**`akshare` 在线拉取历史行情，受网络与数据源影响。

**建议：**

- 使用 `run_strategy(..., use_local=True)` 或 `run_backtest(..., use_local=True)`：首次下载并写入 `data/`，之后优先读本地 CSV。
- 对多标的回测务必传入 **`securities=[...]`**，只预加载会交易的股票，显著减少请求量。
- 参见 [API 参考](../reference/index.md) 中 `set_cache_dir` / `set_local_data_dir`。

### Q: `get_price` / `attribute_history` 返回空

**检查：**

1. 代码是否为 **6 位 A 股代码**（如 `601390`），指数基准形如 `000300.XSHG`。
2. 日期区间是否在股票上市之后、是否为交易日。
3. 网络是否正常；可换时段重试或改用本地数据 `use_local=True`。

### Q: 分钟线、Tick 报错或数据不全

分钟/Tick 依赖 `akshare` 对应接口与标的流动性，不同股票可用历史长度不同。详见 [API 参考 — 分钟线 / Tick](../reference/api-data.md)。

### Q: 北向资金 API 返回空数据怎么办？

**可能原因：**

1. **交易日限制**：北向资金数据仅在交易日更新，周末和节假日无数据。
2. **网络问题**：数据源（东方财富）接口不稳定，可稍后重试。
3. **日期范围**：`get_north_money_flow(count=N)` 返回最近 N 个交易日数据，若 N 过大可能超出数据源限制。

**处理：**

```python
from eqlib import get_north_money_flow

df = get_north_money_flow(count=30)
if df.empty:
    log.warn("北向资金数据暂不可用，使用备用逻辑")
    # 可使用缓存或历史均值作为替代
```

建议在 `initialize` 中预加载并缓存北向资金数据，避免每次 `handle_data` 都请求。

### Q: get_limit_up_down_stats 为什么只返回最近 30 天？

**原因：** 该接口调用 `ak.stock_zt_pool_em`，数据源（东方财富）仅提供近 30 个交易日的涨跌停统计数据，无法获取更早历史。

**替代方案：**

- 对于回测场景，可使用 `attribute_history` 获取个股涨跌幅，自行统计涨跌停数量。
- 若需更长历史，可考虑使用第三方付费数据源。

```python
from eqlib import get_limit_up_down_stats

df = get_limit_up_down_stats()
# 仅包含最近约 30 个交易日
```

### Q: 融资融券数据的 margin_repay 第一行为什么是 NaN？

**原因：** `margin_repay`（融资偿还额）是相邻两日融资余额的差值计算得出的。第一行没有前一日数据，因此计算结果为 NaN。这是正常的数据处理结果。

**处理：**

```python
from eqlib import get_margin_trading

df = get_margin_trading('601390', count=30)
# 去除首行 NaN
df = df.dropna(subset=['margin_repay'])

# 或使用前值填充
df['margin_repay'] = df['margin_repay'].fillna(0)
```

### Q: 为什么我在 run_backtest 外设置的 g.xxx 丢失了？

**原因：** `run_backtest`（以及 `run_strategy`）在每次调用时都会**清空 `g` 对象**。这是设计行为——每个回测会话应该有自己的独立状态，避免多次运行之间的数据污染。

**处理：** 在 `initialize()` 内部设置 `g` 的属性，而不是在 `run_backtest` 外部：

```python
# ❌ 错误
g.security = '601398'
result = run_backtest(initialize, ...)

# ✅ 正确
def initialize(context):
    g.security = '601398'
    run_daily(market_open, time='every_bar')

result = run_backtest(initialize, ...)
```

如果需要模块级别的配置，使用普通 Python 变量而非 `g`：

```python
# 模块级常量（不会被清空）
MY_SECURITY = '601398'

def initialize(context):
    g.security = MY_SECURITY
```

---

## 回测与策略

### Q: 回测结束生成了 HTML，但 PNG 很空或没有净值曲线

**常见原因：**`record()` 未在策略中记录 **`total_value`**，或 `recorded_values` 中缺少按日的组合价值，导致 `generate_chart` / HTML 中部分序列无法绘制。

**处理：**在每日逻辑末尾调用框架提供的记录（若使用 `run_daily` 等，引擎通常会记录组合；自定义时请确保与官方示例一致）。可参考 `examples/03_run_backtest.py` 与 [运行回测](../how-to/run-backtest.md)。

### Q: 买入后当天想卖出，提示可卖为 0

**原因：**A 股 **T+1**，当日买入股数计入 `closeable_amount`，次日才可卖。引擎会按规则限制卖出数量。

### Q: `order` / `order_value` 股数不是心里想的数

**原因：**买入数量会 **向下取整到 100 股的整数倍**；资金不足时会按最大可买执行。

### Q: 基准设为 `000300.XSHG` 有什么作用？

用于计算 **alpha、beta、信息比率、超额收益** 等，并在 HTML/PNG 中与策略收益对比。详见 [报告格式规范](../reference/reports-format.md)。

---

## 报告与分析

### Q: HTML 里「日胜率」和「交易胜率」不一样？

**原因：**`analyze_returns` 同时提供 **`win_rate_daily`**（按交易日盈亏比例）与 **`win_rate_trade`**（完整买卖配对后的胜率）。含义不同，勿混用。完整列表见 [报告格式规范](../reference/reports-format.md)。

<a id="faq-html-blank"></a>

### Q: HTML 报告里图表区域空白？

**原因：**交互式 HTML 通过 **CDN**（如 jsDelivr / unpkg）加载 **Lightweight Charts** 脚本。公司内网、代理或离线环境可能拦截外联脚本，导致 **K 线、累计收益、回撤等图区空白**；页眉、摘要和指标卡片多为页面内嵌数据，通常仍可见。

**处理：**换可访问外网的网络；或将 `cdn.jsdelivr.net`、`unpkg.com` 加入白名单后刷新；在有网环境打开后自行截图存档。

<a id="faq-json-num-trades"></a>

### Q: JSON 里 `summary.num_trades` 和「交易次数（配对）」为什么不一样？

**原因：**`summary.num_trades` 常表示 **成交单边条数**（每一笔 `BUY` / `SELL` 各计一条，例如 8 买 + 8 卖 = **16**）。报告/HTML 中的 **「交易次数」若指配对回合**，则为完整买—卖闭环数量（上例为 **8**）。阅读 JSON 时请同时看 `risk_metrics` 与 `trades` 列表。

<a id="faq-benchmark-null"></a>

### Q: `benchmark_return` 为 `null`，Alpha / Beta 接近 0 是否正常？

**可能原因：**拉取或对齐 **基准指数日收益** 失败（网络、指数代码转换、日期交集为空等）时，超额收益与 CAPM 相关展示可能为 **0 或占位**。**策略净值、PNG 静态图、成交表仍以策略数据为准**。可检查网络后重跑，或确认 `set_benchmark` 与回测区间中有有效指数行情。

### Q: 如何只跑回测、不要自动生成四份报告？

使用 **`run_backtest`**，自行按需调用 `generate_html_report`、`analyze_returns` 等。见 [API 参考](../reference/api-analysis.md)。

---

## 模拟盘与导出

### Q: `run_paper_trade` 与回测区别？

模拟盘按设定间隔拉 **实时或最新行情**，循环执行策略，**不结束**直到手动中断（Ctrl+C）。详见 [模拟盘](../how-to/paper-trade.md)。

### Q: 如何导出到 PTrade / QMT？

见 [导出 PTrade/QMT](../how-to/export-ptrade.md) 与示例 `examples/12_paper_trade.py`。

---

## Web 策略工作室

### Q: 登录后自动退出是什么原因？

**原因：** JWT Token 过期或失效时，前端会自动清除认证状态并返回登录页面。

**处理：**
- 检查后端是否正常运行
- 生产环境需配置稳定的 JWT 密钥（环境变量 `EQ_JWT_SECRET`），否则重启后密钥变化导致所有 Token 失效
- 若后端重启，需重新登录

### Q: 回测一直显示 positions=0，没有交易？

**原因：** 策略代码中可能未正确设置 `context.universe = [...]`。Web 工作室的数据预加载依赖这个配置来确定需要加载哪些股票的历史数据。

**处理：** 在 `initialize(context)` 中明确设置股票池：

```python
def initialize(context):
    context.universe = ['601390', '600519']
```

更多 Web 工作室问题请查看 [Web 策略工作室](../how-to/web-studio.md)。

---

## 开发与测试

### Q: 修改了 `eqlib` 源码如何验证？

```bash
python -m pytest tests/
```

（优化策略时一般 **不** 修改 `eqlib/`，只改策略与示例。）
