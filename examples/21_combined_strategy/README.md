# Example 21: All-Weather Alpha — Comprehensive Combined Strategy

A production-ready, multi-layer quantitative strategy that integrates all major
techniques covered in the EasyQuant tutorials and examples.

## Strategy Layers

| Layer | Technique | Source |
|-------|-----------|--------|
| 1 | Multi-factor stock selection (momentum + volume + reversal + volatility, Z-Score normalised) | Tutorial 08, Example 16 |
| 2 | Sector-rotation scoring bonus | Tutorial 07, Example 10 |
| 3 | RSI + Bollinger Band mean-reversion entry | Tutorial 06, Example 14 |
| 3 | MACD trend confirmation + volume confirmation | Example 15 |
| 3 | ATR trailing stop | Examples 15, 20 |
| 3 | Donchian Channel exit | Example 20 |
| 3 | Support/Resistance confirmation | Example 20 |
| 4 | Hard stop-loss (−8%) + equal-weight position sizing | Examples 14, 16 |
| 4 | Lifecycle callbacks (before_trading_start / after_trading_end) | Example 08 |

## Files

| File | Description |
|------|-------------|
| `combined_strategy.py` | Full strategy module — import and customise |
| `run_backtest.py` | Ready-to-run backtest (2022–2024, ¥500,000) |
| `run_paper_trade.py` | Ready-to-run paper trading script |

## Quick Start

```bash
# Backtest (takes ~60 s); reports go to ../../reports/ under the repo root
python examples/21_combined_strategy/run_backtest.py

# Paper trade (runs until Ctrl+C)
python examples/21_combined_strategy/run_paper_trade.py
```

Backtest note: `order*` calls are queued and filled at the next trading day open; paper trading uses real-time prices.

## Tutorial

Full step-by-step explanation with formulas and justifications:
**[tutorials/09_combined_strategy.md](../../tutorials/09_combined_strategy.md)**

## Stock Pool (12 stocks, 8 sectors)

| Code | Name | Sector |
|------|------|--------|
| 601398 | ICBC 工商银行 | Banking |
| 600519 | Kweichow Moutai 贵州茅台 | Liquor |
| 002594 | BYD 比亚迪 | New Energy |
| 601857 | PetroChina 中国石油 | Oil & Gas |
| 601088 | China Shenhua 中国神华 | Coal |
| 601390 | China Railway 中国中铁 | Infrastructure |
| 600276 | Hengrui Pharma 恒瑞医药 | Healthcare |
| 000333 | Midea 美的集团 | Appliances |
| 600916 | China Gold 中国黄金 | Gold |
| 000858 | Wuliangye 五粮液 | Liquor |
| 601318 | Ping An 中国平安 | Insurance |
| 600887 | Yili 伊利股份 | Consumer |
