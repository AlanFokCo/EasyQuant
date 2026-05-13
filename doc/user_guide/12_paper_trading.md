!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §11](11_risk_attribution.md) · [下一章 §13](13_optimization.md)

---

## 12. 模拟盘交易

模拟盘使用实时行情数据持续运行策略，适合在实盘前验证。

```python
from eqlib import run_paper_trade

def initialize(context):
    g.security = '601390'
    set_benchmark('000300.XSHG')
    run_daily(market_open, time='every_bar')

def market_open(context):
    # ... 策略逻辑
    pass

# 启动模拟盘，每 60 秒刷新一次
result = run_paper_trade(
    initialize,
    starting_cash=100000,
    benchmark='000300.XSHG',
    interval=60,          # 轮询间隔（秒）
)
```

模拟盘会持续输出当前总资产和盈亏：

```
[14:30:00] total_value=102,345.67  PnL=+2,345.67 (+2.35%)
[14:31:00] total_value=102,456.78  PnL=+2,456.78 (+2.46%)
```

按 `Ctrl+C` 停止。
