# 19 — Support/Resistance Portfolio Strategy

A multi-stock portfolio strategy that identifies **support and resistance (S/R) levels**
from swing-point clustering, then buys near support and sells near resistance with
confirmation from RSI, MACD, ATR, Donchian channels, and volume ratio.

## Strategy Logic

| Condition | Buy | Sell |
|-----------|-----|------|
| S/R proximity | Price within 2% of support | Price within 2% of resistance |
| RSI | RSI < 30 (oversold) | RSI > 70 (overbought) |
| MACD | Golden cross (DIF crosses above DEA) | Death cross (DIF crosses below DEA) |
| Donchian | Price at or below lower band | Price at or above upper band |
| ATR trailing stop | — | Price < highest_since_buy − 2.5 × ATR |
| Volume ratio | Confirms participation | — |

A **buy** signal fires when the price is near support **and** (RSI is oversold **or**
MACD golden cross).  A **sell** signal fires when the price is near resistance **and**
(RSI is overbought **or** MACD death cross), or when the ATR trailing stop is breached,
or when the Donchian upper band is reached.

Positions are equally weighted at a maximum of 25% per stock (4 concurrent holdings).

## Stock Pool

| Code | Trade Code | Name | Sector |
|------|------------|------|--------|
| 601390 | 601390.XSHG | China Railway (中国中铁) | Infrastructure |
| 002594 | 002594.XSHE | BYD (比亚迪) | EV / New Energy |
| 601088 | 601088.XSHG | China Shenhua (中国神华) | Coal / Energy |
| 601857 | 601857.XSHG | PetroChina (中国石油) | Oil & Gas |
| 600536 | 600536.XSHG | China Software (中国软件) | Technology |
| 601111 | 601111.XSHG | Air China (中国国航) | Aviation |
| 000630 | 000630.XSHE | Tongling Nonferrous (铜陵有色) | Metals |
| 601398 | 601398.XSHG | ICBC (工商银行) | Banking |

## Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `SR_LOOKBACK` | 80 | Bars to scan for swing-point S/R clusters |
| `SR_TOLERANCE` | 0.02 (2%) | Price proximity to count as "near" an S/R level |
| `RSI_PERIOD` | 14 | RSI calculation window |
| `RSI_OVERSOLD` | 30 | RSI threshold for oversold (buy confirmation) |
| `RSI_OVERBOUGHT` | 70 | RSI threshold for overbought (sell confirmation) |
| `ATR_PERIOD` | 14 | ATR calculation window |
| `ATR_STOP_MULTIPLIER` | 2.5 | Trailing stop distance: highest − N × ATR |
| `DONCHIAN_PERIOD` | 20 | Donchian channel lookback |
| `VOLUME_RATIO_PERIOD` | 20 | Average volume window for ratio calculation |
| `MAX_SINGLE_PCT` | 0.25 (25%) | Maximum portfolio weight per stock |

## Files

| File | Description |
|------|-------------|
| `sr_strategy.py` | Strategy logic (initialize, indicators, buy/sell decisions) |
| `run_backtest.py` | Backtest runner with CLI arguments |
| `README.md` | This file |

## How to Run

```bash
# Default: 200,000 CNY starting capital
python examples/19_sr_portfolio/run_backtest.py

# Custom starting capital
python examples/19_sr_portfolio/run_backtest.py --cash 500000
```

Reports (PNG, HTML, Markdown, JSON) are saved to the `reports/` directory
at the repository root.
