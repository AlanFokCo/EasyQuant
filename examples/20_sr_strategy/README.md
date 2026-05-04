# Example 20: Support & Resistance Portfolio Strategy

## Strategy Overview

A multi-stock portfolio strategy that identifies support and resistance levels
using historical price patterns, then buys near support and sells near resistance
with confirmation from RSI, MACD, ATR, and Donchian channels.

### Buy Signals
- Price near support level (within 2%) + RSI oversold (< 30) or MACD golden cross
- Price at or below Donchian lower band + RSI not overbought

### Sell Signals
- ATR trailing stop (highest price since buy - 2.5 * ATR)
- Price near resistance + RSI overbought (> 70) or MACD death cross
- Price at or above Donchian upper band

### Position Management
- Max 25% of portfolio per stock (4 stocks max)
- Equal-weight allocation among eligible candidates
- Per-trade commission: 0.03%, sell tax: 0.1%

## Stock Pool

| Code | Name (EN) | Name (CN) | Sector |
|------|-----------|-----------|--------|
| 601390 | China Railway | 中国中铁 | Infrastructure |
| 600916 | China Gold | 中国黄金 | Gold |
| 002594 | BYD | 比亚迪 | EV/New Energy |
| 601088 | China Shenhua | 中国神华 | Coal |
| 601857 | PetroChina | 中国石油 | Oil |
| 600536 | China Soft | 中国软件 | Technology |
| 601398 | ICBC | 工商银行 | Banking |
| 518880 | Gold ETF | 黄金ETF | Gold ETF |

## Backtest Results

| Metric | Value |
|--------|-------|
| Period | 2020-01-01 to 2026-03-30 (~6 years) |
| Starting Cash | 1,000,000 |
| Final Value | 2,371,889.70 |
| **Total Return** | **+137.19%** |
| Buy Orders | 114 |
| Sell Orders | 112 |
| Total Trades | 226 |

## Files in This Directory

| File | Description |
|------|-------------|
| `sr_strategy.py` | Strategy code |
| `run_backtest.py` | Backtest runner script |
| `sr_backtest.png` | Portfolio chart (PNG) |
| `sr_backtest.html` | Interactive HTML report |
| `sr_backtest.md` | Markdown summary report |
| `sr_backtest.json` | Full backtest data (JSON) |

## How to Run

```bash
# From the project root directory:
python examples/20_sr_strategy/run_backtest.py
```

Requires local data files in `data/` directory. If you don't have them:
```bash
# Download data first (example 19)
python examples/19_local_data_backtest.py --download-all
```

## Technical Indicators Used

- **Support/Resistance**: Price level clustering from 80-day lookback
- **RSI (14)**: Relative Strength Index for overbought/oversold detection
- **MACD (12,26,9)**: Trend direction and momentum
- **ATR (14)**: Average True Range for volatility-based stop loss
- **Donchian Channel (20)**: Price breakout/breakdown detection

## Key Design Principles

1. **Mean reversion with trend confirmation**: Buy dips at support, but confirm with MACD/RSI
2. **Dynamic stop loss**: ATR-based trailing stop adapts to volatility
3. **Diversification**: 8 stocks across different sectors reduces single-stock risk
4. **Position limits**: Max 25% per stock prevents over-concentration
