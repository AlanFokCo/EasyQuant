# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Dual index charts (CSI300 + SSE) in HTML backtest reports
- Support/Resistance strategy (`examples/20_sr_strategy/`)
- Stock selection strategy (`examples/22_stock_selection_strategy.py`)
- Local data backtest (`examples/19_local_data_backtest.py`) with CSV cache
- Portfolio backtesting with equal-weight rebalancing (`examples/12_portfolio_backtest.py`)
- Brinson attribution and Fama-French factor analysis
- HTML report with interactive charts via Lightweight Charts
- MkDocs documentation site with CI/CD via GitHub Pages
- AI-driven self-optimization loop (Claude Code orchestrated, `CLAUDE.md`)

### Changed

- Index data source fallback from EastMoney to Sina for reliability
- Improved report structure: K-line, cumulative returns, drawdown, daily PnL

### Fixed

- CI build failures from broken `docs/CLAUDE.md` symlink
- HTML report empty index data when network proxy blocks EastMoney API

## [0.1.0] — 2025-05

Initial release.

### Added

- Event-driven backtest engine (`eqlib/engine.py`)
- Fluent query API (`eqlib/stock_query.py`)
- Data layer with akshare integration and local CSV caching
- Strategy templates: MACD+Volume, Bollinger, Grid Trading, Multi-Factor
- Matplotlib chart generation and Markdown report export
- PTrade/QMT adapter for live deployment
- Comprehensive test suite
