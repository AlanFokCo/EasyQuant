# Example 20: All-Weather Alpha -- Multi-Layer Combined Strategy

A production-grade, multi-layer quantitative strategy that integrates factor
selection, sector rotation, technical signals, and risk management for the
China A-share market.

## Strategy Architecture

```
Layer 1: Multi-Factor Weekly Selection
  Momentum (20d return, 35%) + Volume (5d/20d ratio, 30%)
  + Reversal (-5d return, 15%) + Volatility (-20d std, 20%)
  Z-score normalised across pool
        |
Layer 2: Sector Rotation Scoring
  10-day sector momentum (via representative stock)
  10% weight bonus/malus on composite score
        |
Layer 3: Technical Entry/Exit Signals
  Entry: RSI oversold OR Bollinger lower
         AND (MACD golden OR near support)
         AND volume confirms (>1.2x avg)
  Exit:  ATR trailing stop | RSI+Bollinger overbought
         | MACD death cross | Donchian breakout | Hard -8% stop
        |
Layer 4: Risk Management
  Equal-weight top-5, max 20% per stock
  North-capital regime scaling: bull=100%, neutral=75%, bear=50%
  Hard stop-loss at -8% from average cost
```

## Stock Pool (12 stocks, 8 sectors)

| Code      | Name                  | Sector         |
|-----------|-----------------------|----------------|
| 601390    | China Railway         | Infrastructure |
| 600036    | China Merchants Bank  | Banking        |
| 601088    | China Shenhua         | Coal           |
| 601857    | PetroChina            | Oil & Gas      |
| 002594    | BYD                   | New Energy     |
| 000768    | AVIC Jonhon           | Technology     |
| 600536    | China National Soft   | Technology     |
| 601111    | Air China             | Infrastructure |
| 601179    | China XD Electric     | Energy         |
| 601398    | ICBC                  | Banking        |
| 601318    | Ping An               | Insurance      |
| 600887    | Yili                  | Consumer       |

## Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| TOP_N | 5 | Max concurrent positions |
| MOMENTUM_PERIOD | 20 | Momentum lookback (trading days) |
| REVERSAL_PERIOD | 5 | Short-term reversal lookback |
| RSI_OVERSOLD | 35 | RSI entry threshold |
| RSI_OVERBOUGHT | 65 | RSI exit threshold |
| BOLL_PERIOD | 20 | Bollinger Band period |
| BOLL_STD | 2.0 | Bollinger Band std multiplier |
| MACD (fast/slow/signal) | 12/26/9 | MACD parameters |
| ATR_MULTIPLIER | 2.5 | ATR trailing-stop multiplier |
| DONCHIAN_PERIOD | 20 | Donchian Channel period |
| SR_LOOKBACK | 60 | Support/resistance lookback |
| HARD_STOP_PCT | 8% | Hard stop-loss threshold |
| VOL_CONFIRM_RATIO | 1.2x | Volume confirmation threshold |
| MAX_SINGLE_PCT | 20% | Max allocation per stock |

## How to Run

### Backtest

```bash
# Default: 500,000 CNY, 3-year lookback
python examples/20_all_weather_alpha/run_backtest.py

# Custom capital and date range
python examples/20_all_weather_alpha/run_backtest.py \
    --cash 1000000 --start 2021-01-01 --end 2024-12-31
```

### Paper Trading

```bash
# Default: 500,000 CNY, 60s refresh
python examples/20_all_weather_alpha/run_paper_trade.py

# Custom settings
python examples/20_all_weather_alpha/run_paper_trade.py \
    --cash 200000 --interval 120
```

## Files

| File | Description |
|------|-------------|
| `combined_strategy.py` | Full multi-layer strategy module |
| `run_backtest.py` | Backtest runner with argparse CLI |
| `run_paper_trade.py` | Paper trading runner |
| `README.md` | This file |
