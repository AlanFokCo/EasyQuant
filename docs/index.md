---
hide:
  - navigation.path
---

# EasyQuant

面向中国 A 股的事件驱动回测框架。

<div class="hero-cards">
<a class="hero-card" href="doc/user_guide/#0-新手四步">
<h3>快速入门</h3>
<p>从安装到运行第一个回测，15 分钟即可上手。</p>
<span class="card-link">开始 →</span>
</a>
<a class="hero-card" href="doc/user_guide/">
<h3>用户手册</h3>
<p>编写策略、运行回测、解读报告的完整指南。</p>
<span class="card-link">阅读 →</span>
</a>
<a class="hero-card" href="tutorials/">
<h3>分步教程</h3>
<p>从零到实盘的系列教程，含真实策略案例。</p>
<span class="card-link">学习 →</span>
</a>
<a class="hero-card" href="doc/api_reference/">
<h3>API 参考</h3>
<p><code>eqlib</code> 全部公开 API 的参数与示例。</p>
<span class="card-link">查阅 →</span>
</a>
</div>

## 核心能力

- **事件驱动回测** — `initialize` → `run_daily` → `handle_data`，与 JoinQuant / Zipline 一致的编程模型
- **A 股数据** — 日线 OHLCV、分钟 K 线、实时行情、财务摘要、资金流向，通过 AKShare 免费获取
- **仓位管理** — 按股数 / 金额 / 目标值买卖，自动取整到 100 股，自动计算手续费
- **风险分析** — 夏普 / 索提诺 / 最大回撤 / alpha & beta / Brinson 归因 / Fama-French 因子
- **模拟盘** — 使用实时行情持续运行策略，实盘前验证
- **PTrade/QMT 适配** — 策略一键导出为券商平台格式

## 快速验证

```bash
pip install easyquant-eqlib
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

在 `reports/` 目录打开最新生成的 `.html` 报告。

---

!!! info

    本文档仅供学习研究，不构成投资建议。
