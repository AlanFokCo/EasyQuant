!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §10](10_reports.md) · [下一章 §12](12_paper_trading.md)

---

## 11. 风险与归因分析

### 11.1 `analyze_returns`：综合风险指标

```python
from eqlib import analyze_returns

metrics = analyze_returns(result, risk_free_rate=0.03)
```

返回指标：

| 指标 | 说明 | 好值 |
|------|------|------|
| `total_return` | 总收益率 | 正数越大越好 |
| `annual_return` | 年化收益率 | 正数越大越好 |
| `annual_volatility` | 年化波动率 | 低一些更好 |
| `sharpe_ratio` | 夏普比率 | > 1 为好，> 2 为优秀 |
| `sortino_ratio` | 索提诺比率 | 只考虑下行风险，> 1 为好 |
| `max_drawdown` | 最大回撤 | 接近 0 越好 |
| `calmar_ratio` | 卡玛比率 (年化收益/最大回撤) | > 1 为好 |
| `alpha` | 超额收益（年化） | 正数为跑赢基准 |
| `beta` | 市场敏感度 | 1 表示与大盘同步，> 1 波动更大 |
| `information_ratio` | 信息比率 | > 0.5 为好 |
| `win_rate_daily` | 日胜率（盈利交易日占比） | > 0.5 为好 |
| `win_rate_trade` | 配对交易胜率（完整买卖回合） | 与 `win_rate_daily` 含义不同，勿混用 |

完整字段列表与解读见 [**reports_and_metrics.md — 第 4 节**](../reports_and_metrics.md#4-analyze_returns-指标字典)。

### 11.2 `brinson_attribution`：归因分析

将收益分解为 **配置效应**、**选股效应** 和 **交互效应**。

```python
from eqlib import brinson_attribution

attr = brinson_attribution(result)
print("配置效应: %.4f" % attr['allocation_effect'])
print("选股效应: %.4f" % attr['selection_effect'])
```

### 11.3 `fama_french_analysis`：因子分析

```python
from eqlib import fama_french_analysis

ff = fama_french_analysis(result)
print("市场 Beta: %.3f" % ff['market_beta'])
print("年化 Alpha: %.4f" % ff['alpha_annual'])
```
