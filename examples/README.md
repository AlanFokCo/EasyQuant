# EasyQuant Examples

24 examples organized in a progressive learning path: Foundation (01-07),
Intermediate (08-14), Practical (15-20), and ML (21-24).

## Prerequisites

```bash
pip install -e .
```

All examples use relative dates and shared configuration from `_defaults.py`.

## Foundation (01-07): Learn the Basics

| # | File | What You'll Learn |
|---|------|-------------------|
| 01 | `01_fetch_data.py` | Data APIs: `get_price`, `fetch_stock_data`, `scan_market`, CSV workflow |
| 02 | `02_write_strategy.py` | Strategy pattern: `initialize`, `run_daily`, `g` object, MA crossover |
| 03 | `03_run_backtest.py` | Lower-level `run_backtest`, trade log inspection, `analyze_returns` |
| 04 | `04_stock_screener.py` | `scan_market`, `check_golden_cross`, `get_restriction_release`, `query()` API |
| 05 | `05_reports.py` | All 4 report formats (PNG/HTML/MD/JSON), complete metric key reference |
| 06 | `06_local_data.py` | Local data cache: `save_stock_local`, `has_local_data`, `use_local=True` |
| 07 | `07_lifecycle.py` | Lifecycle hooks: `before_trading_start`, `after_trading_end`, ST detection |

```bash
python examples/01_fetch_data.py
python examples/02_write_strategy.py
# ... etc
```

## Intermediate (08-14): Analysis & A-Share Features

| # | File | What You'll Learn |
|---|------|-------------------|
| 08 | `08_utils_library.py` | `utils.*` library: indicators, statistics, money management |
| 09 | `09_attribution.py` | `analyze_returns`, `brinson_attribution`, `simple_factor_analysis` |
| 10 | `10_index_concept.py` | `get_index_stocks`, `get_concept_list`, `get_industry_list` |
| 11 | `11_portfolio_backtest.py` | `StrategyConfig`, `run_portfolio_backtest`, `PortfolioRiskMonitor` |
| 12 | `12_paper_trade.py` | `run_paper_trade`, webhook notifications, pre-market monitoring |
| 13 | `13_ashare_sentiment.py` | North-capital flow, margin data, limit stats, composite sentiment |
| 14 | `14_portfolio_risk.py` | `PortfolioRiskMonitor`: VaR, correlation, concentration, kill switch |

## Practical (15-20): Complete Strategy Projects

| # | File | Strategy | Key Techniques |
|---|------|----------|----------------|
| 15 | `15_bollinger_strategy.py` | Bollinger mean reversion | `utils.boll()`, ATR trailing stop |
| 16 | `16_macd_volume.py` | MACD trend following | `utils.macd()`, volume confirmation |
| 17 | `17_multi_factor.py` | Multi-factor selection | Z-score scoring, north-capital gate |
| 18 | `18_grid_trading.py` | Grid trading | Grid levels, range-bound detection |
| 19 | `19_sr_portfolio/` | S/R portfolio | Support/resistance, multi-stock |
| 20 | `20_all_weather_alpha/` | All-weather alpha | Multi-layer: factors + rotation + risk |

```bash
python examples/15_bollinger_strategy.py
python examples/19_sr_portfolio/run_backtest.py
python examples/20_all_weather_alpha/run_backtest.py
```

## Machine Learning (21-24): ML-Driven Selection

| # | File | What You'll Learn |
|---|------|-------------------|
| 21 | `21_ml_selector.py` | `MLSelector` drop-in for rule-based selection; `past_return_5d` target |
| 22 | `22_feature_pipeline.py` | `FeaturePipeline` standalone; RSI/MACD/ATR feature engineering |
| 23 | `23_model_comparison.py` | RandomForest vs LogisticRegression on identical features |
| 24 | `24_custom_features.py` | Custom feature functions (price/MA ratio, volume surge) injected into pipeline |

```bash
python examples/21_ml_selector.py
python examples/22_feature_pipeline.py
python examples/23_model_comparison.py
python examples/24_custom_features.py
```

## Shared Infrastructure

- `examples/_defaults.py` — Trading costs (2024 rates), stock codes, relative dates
- `tests/test_examples_smoke.py` — Smoke tests: syntax, imports, code standards

## Bonus: Web Studio Ready Strategies

Additional strategies optimized for **Web Strategy Studio** (browser-based editing and backtesting):

| File | Strategy | Key Techniques |
|------|----------|----------------|
| `eqlib/examples/multi_factor_momentum.py` | Multi-factor momentum rotation | 10-stock universe, daily rebalancing, equal-weight position sizing |

These strategies use `from eqlib import *` directly and are designed to be copy-pasted into the Web Studio editor.

## Trading Cost Standards

All examples use consistent 2024 rates:

| Cost | Rate | Notes |
|------|------|-------|
| Stamp duty | 0.05% | Sell only, halved since Aug 2023 |
| Commission | 0.025% | Buy + sell, includes regulatory fees |
| Minimum | 5 CNY | Per trade |
