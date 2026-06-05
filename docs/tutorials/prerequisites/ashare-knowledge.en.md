# Prerequisites: A-Share Market Fundamentals

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Suitable for** | Readers unfamiliar with A-share code conventions, T+1 settlement, limit up/down, fees/taxes, and major indices |
    | **Estimated time** | ~45 minutes |
    | **Value** | Helps you correctly understand backtest assumptions and execution constraints in `eqlib` |

> This article is for readers who have **not traded A-shares or need to learn the rules of the Chinese stock market**. Understanding these rules will help you write more realistic strategies and correctly interpret the metrics in backtest reports.

---

## Table of Contents

1. [What Are A-Shares](#1-what-are-a-shares)
2. [Stock Code Format & Exchanges](#2-stock-code-format--exchanges)
3. [Trading Hours](#3-trading-hours)
4. [T+1 Settlement](#4-t1-settlement)
5. [Limit Up/Down System](#5-limit-updown-system)
6. [ST Stocks & Delisting Risk](#6-st-stocks--delisting-risk)
7. [Trading Costs: Fees & Taxes](#7-trading-costs-fees--taxes)
8. [Major Market Indices](#8-major-market-indices)
9. [Fundamental Data: PE / PB / ROE etc.](#9-fundamental-data-pe--pb--roe-etc)
10. [Capital Flow](#10-capital-flow)
11. [North-bound Capital](#11-north-bound-capital)
12. [Margin Trading](#12-margin-trading)
13. [Limit Up/Down Statistics](#13-limit-updown-statistics)
14. [Restricted Share Unlock](#14-restricted-share-unlock)
15. [How These Rules Are Reflected in eqlib](#15-how-these-rules-are-reflected-in-eqlib)
16. [Next Steps](#16-next-steps)

---

## 1. What Are A-Shares

**A-shares** are stocks listed on the Shanghai Stock Exchange (SSE) and the Shenzhen Stock Exchange (SZSE) in **mainland China**, denominated in Renminbi (RMB/CNY).

| Type | Description |
|------|-------------|
| A-shares | Listed in mainland China, RMB-denominated — the focus of this article |
| H-shares | Shares of the same companies listed in Hong Kong, HKD-denominated |
| B-shares | Legacy shares denominated in foreign currency, thinly traded |
| US ADRs | Depositary receipts of Chinese companies listed in the United States |

> **EasyQuant only supports A-shares** — it does not support Hong Kong stocks, US stocks, futures, options, or cryptocurrencies.

---

## 2. Stock Code Format & Exchanges

### 2.1 Code Conventions

A-share codes are **6-digit numbers**; the prefix determines the exchange and board:

| Prefix | Exchange | Board | Examples |
|--------|----------|-------|---------|
| `600xxx` `601xxx` `603xxx` `605xxx` | Shanghai (SSE) | SSE Main Board | `601390` (ICBC) `600519` (Kweichow Moutai) |
| `000xxx` `001xxx` | Shenzhen (SZSE) | SZSE Main Board | `000858` (Wuliangye) |
| `002xxx` `003xxx` | Shenzhen | SME Board (merged into Main Board) | `002415` (Hikvision) |
| `300xxx` `301xxx` | Shenzhen | ChiNext (GEM) | `300750` (CATL) |
| `688xxx` `689xxx` | Shanghai | STAR Market | `688981` (SMIC) |
| `8xxxxx` | NEEQ | Beijing Stock Exchange | — |

### 2.2 Index Code Format (with Exchange Suffix)

In eqlib, **index codes require an exchange suffix**:

| Index | Code | Notes |
|-------|------|-------|
| CSI 300 | `000300.XSHG` | Most commonly used benchmark |
| SSE Composite | `000001.XSHG` | Reflects the overall Shanghai market |
| SZSE Component | `399001.XSHE` | Reflects the overall Shenzhen market |
| CSI 500 | `000905.XSHG` | Mid-cap stocks |
| ChiNext Index | `399006.XSHE` | Overall ChiNext market |
| STAR 50 | `000688.XSHG` | Top STAR Market stocks |
| SSE 50 | `000016.XSHG` | Shanghai blue chips |

> **Rules (project convention):**
> - `000xxx.XSHG` = Shanghai index (e.g., CSI 300)
> - `399xxx.XSHE` = Shenzhen index (e.g., SZSE Component, ChiNext Index)
> - `000xxx.XSHE` or bare `000xxx` = Shenzhen stock (e.g., Wuliangye `000858`)

```python
# Set benchmark
set_benchmark('000300.XSHG')   # CSI 300

# Get index constituent stocks
from eqlib import get_index_stocks
hs300_stocks = get_index_stocks('000300.XSHG')
```

---

## 3. Trading Hours

A-share trading is divided into two sessions (Beijing Time, UTC+8):

| Session | Time | Description |
|---------|------|-------------|
| Call auction | 9:15–9:25 | Pre-market orders to determine the opening price |
| Morning session | 9:30–11:30 | Continuous trading |
| Lunch break | 11:30–13:00 | No trading |
| Afternoon session | 13:00–15:00 | Continuous trading |

**Impact on eqlib:**
- Daily backtests use the **9:30 open price** as the fill price (on the next trading day)
- Minute-level bars run from `09:30` to `15:00`, excluding the lunch break
- Public holidays (Chinese New Year, National Day, etc.) have no trading days

---

## 4. T+1 Settlement

**T+1** is one of the most important A-share rules:

> **Stocks bought today cannot be sold until the next trading day.**

By comparison, the US market settled on T+3 until 2024 when it moved to T+1 (with restrictions on day trading); Hong Kong settles on T+2.

### Impact on Strategies

```python
# In backtests: eqlib handles T+1 constraints automatically
# Buy today -> closeable_amount = 0 today -> closeable_amount = shares bought tomorrow

def market_open(context):
    position = context.portfolio.positions.get('601390')
    if position:
        # closeable_amount = shares available for immediate sale (after T+1 restriction)
        can_sell = position.closeable_amount
        # Shares just bought are not included in can_sell
```

**Strategy implications**: You cannot do same-day "sell high, buy low" (intraday T+0 trading), and you must hold until the next day before selling. Day-trading / scalping strategies are not feasible.

---

## 5. Limit Up/Down System

A-share daily price movements are capped:

| Board | Limit |
|-------|-------|
| SSE/SZSE Main Board (incl. SME Board) | ±10% |
| ChiNext (GEM) | ±20% |
| STAR Market | ±20% |
| ST / *ST stocks | ±5% |
| Beijing Stock Exchange | ±30% |

### Impact on Strategies

```python
# A stock that hit the limit-up price cannot be bought (no sellers)
# A stock that hit the limit-down price cannot be sold (no buyers)
# eqlib backtests ignore liquidity constraints; live trading must account for them

# Best practice: filter out stocks that have hit limit-up today
hist = attribute_history(security, 2, '1d', ['close'])
prev_close = hist['close'].iloc[-2]
today_close = hist['close'].iloc[-1]
limit_up = today_close >= prev_close * 1.099  # near limit-up

if limit_up:
    continue  # skip, do not buy limit-up stocks
```

---

## 6. ST Stocks & Delisting Risk

### What ST Means

| Label | Meaning |
|-------|---------|
| `ST` | Special Treatment: the company has reported losses for two consecutive years or has negative net assets |
| `*ST` | Delisting Risk Warning: three consecutive years of losses, faces delisting |
| `S*ST` | Currently undergoing regulatory restructuring |

ST stocks have the following characteristics:
- Limit up/down band compressed from ±10% to **±5%**
- Poor liquidity, prone to sharp declines
- Opaque information, extremely high risk

### Filtering ST Stocks in Strategies

```python
from eqlib import filter_st_stocks

candidates = ['601390', '600519', '000858', '000001']

# Filter out ST / *ST stocks
safe_stocks = filter_st_stocks(candidates)
```

---

## 7. Trading Costs: Fees & Taxes

### 7.1 Standard Fee Schedule (2024)

| Cost | Buy | Sell | Description |
|------|-----|------|-------------|
| Commission (Brokerage) | 0.02%–0.03% | 0.02%–0.03% | Paid to the broker, minimum 5 CNY |
| Stamp duty | 0 | **0.05%** | Paid to the tax authority (halved from 0.1% in August 2023) |
| Transfer fee (SSE only) | 0.00002% | 0.00002% | Negligible |

### 7.2 Actual Cost of a Round-Trip Trade

Example: buying and selling 100,000 CNY worth of stock (commission 0.025%, minimum 5 CNY):
- Buy: 100,000 × 0.025% = 25 CNY
- Sell: 100,000 × 0.025% + 100,000 × 0.05% = 25 + 50 = 75 CNY
- **Total round-trip cost: 100 CNY (0.10%)**

Frequent trading seriously erodes returns!

### 7.3 Setting Trading Costs in eqlib

```python
def initialize(context):
    set_order_cost(OrderCost(
        open_tax=0,               # buy stamp duty (currently 0)
        close_tax=0.0005,         # sell stamp duty 0.05% (current as of 2024)
        open_commission=0.00025,   # buy commission 0.025%
        close_commission=0.00025,  # sell commission 0.025%
        min_commission=5,         # minimum commission 5 CNY
    ))
```

> If you do not set trading costs, eqlib defaults to zero fees — this will inflate your backtest results! Always set realistic fees.

---

## 8. Major Market Indices

| Index | Code (eqlib format) | Constituents | Common Use Case |
|-------|---------------------|--------------|-----------------|
| CSI 300 | `000300.XSHG` | 300 large-cap blue chips | **Most commonly used benchmark** |
| CSI 500 | `000905.XSHG` | 500 mid-cap stocks | Mid-cap strategy benchmark |
| SSE Composite | `000001.XSHG` | All SSE-listed stocks | Overall market indicator |
| ChiNext Index | `399006.XSHE` | Top 100 ChiNext stocks | Growth strategy benchmark |
| STAR 50 | `000688.XSHG` | Top 50 STAR Market stocks | Tech strategy benchmark |

### Which Benchmark to Choose?

- **Main-board blue-chip strategies**: CSI 300 (`000300.XSHG`)
- **Mid/small-cap strategies**: CSI 500 (`000905.XSHG`)
- **Growth / innovation strategies**: ChiNext Index (`399006.XSHE`)
- **Whole-market strategies**: SSE Composite (`000001.XSHG`)

---

## 9. Fundamental Data: PE / PB / ROE etc.

Commonly used fundamental factors in quantitative strategies:

| Metric | Full Name | Meaning | Lower is... |
|--------|-----------|---------|-------------|
| **PE** | Price-to-Earnings | P/E ratio = price / earnings per share | More "cheap" (value factor) |
| **PB** | Price-to-Book | P/B ratio = price / book value per share | More "cheap" |
| **PS** | Price-to-Sales | P/S ratio = market cap / annual revenue | — |
| **ROE** | Return on Equity | Net income / equity | Higher is better (quality factor) |
| **ROA** | Return on Assets | Net income / total assets | Higher is better |
| **EPS** | Earnings Per Share | Earnings per share | Higher is better |
| **Gross Margin** | Gross Margin | Gross profit / revenue | Higher is better (competitive moat) |

```python
from eqlib import fetch_factor_data

# Fetch multi-dimensional fundamental data for candidate stocks
candidates = ['601390', '600519', '000858']
df = fetch_factor_data(candidates, fields=['pe', 'pb', 'roe'])
#        pe      pb    roe
# 601390  5.4    0.62   11.2
# 600519  28.1   10.3   35.6
# 000858  19.7    6.1   24.8

# Sort by PE ascending (value stock selection)
df_sorted = df.sort_values('pe', ascending=True)
```

---

## 10. Capital Flow

**Capital flow** reflects whether institutional (large-order) investors are net buyers or net sellers on a given day:

| Metric | Meaning |
|--------|---------|
| **Net main inflow** | Net buy amount of large orders (orders > 500,000 CNY) |
| **Super-large orders** | Single order > 1,000,000 CNY |
| **Large orders** | Single order 500,000–1,000,000 CNY |
| **Medium orders** | Single order 100,000–500,000 CNY |
| **Small orders** | Single order < 100,000 CNY |

Consecutive days of net main inflow → Institutions are accumulating, often a precursor to a price rise.

```python
from eqlib import get_money_flow

money_flow = get_money_flow('601390', days=5)
# Returns a DataFrame with fields including net_main (net main inflow)
```

---

## 11. North-bound Capital

**North-bound capital** refers to funds flowing from Hong Kong into the A-share market via the Shanghai-Hong Kong Stock Connect and Shenzhen-Hong Kong Stock Connect channels, often called "smart money."

### 11.1 What Is North-bound Capital

| Type | Description |
|------|-------------|
| **Shanghai Connect** | Hong Kong investors buy SSE stocks through the Hong Kong exchange |
| **Shenzhen Connect** | Hong Kong investors buy SZSE stocks through the Hong Kong exchange |
| **North-bound capital** | Shanghai Connect + Shenzhen Connect combined (foreign capital flowing into A-shares) |
| **South-bound capital** | Mainland investors buying Hong Kong stocks (the reverse direction) |

Characteristics of North-bound capital:
- Dominated by institutional investors, more rational decision-making
- Longer holding periods, preference for blue-chip stocks
- Often regarded as a market bellwether

### 11.2 Fetching North-bound Capital Data in eqlib

```python
from eqlib import get_north_money_flow

# Get North-bound capital flow for the past 3 months
north = get_north_money_flow(start_date="2024-01-01", end_date="2024-03-31")

# Returned fields:
# - date: trading date
# - net_buy: net buy amount (100M CNY)
# - total_buy: total buy amount (100M CNY)
# - total_sell: total sell amount (100M CNY)

# Calculate 5-day net buy
recent_5d = north["net_buy"].tail(5).sum()
if recent_5d > 50:
    print("Strong North-bound capital inflow, positive market sentiment")
elif recent_5d < -50:
    print("Strong North-bound capital outflow, watch for risk")
```

### 11.3 Strategy Application

Consecutive North-bound capital inflows/outflows can serve as a market timing signal:

```python
# Check North-bound capital trend in your strategy
north = get_north_money_flow()
if not north.empty:
    recent_3d = north["net_buy"].tail(3).sum()
    if recent_3d < -50:  # net outflow exceeding 5B CNY over 3 days
        g.market_sentiment = "bearish"  # position reduction signal
```

---

## 12. Margin Trading

**Margin trading** is a leverage mechanism where investors borrow funds or shares from their broker.

### 12.1 Basic Concepts

| Type | Description |
|------|-------------|
| **Margin buy (financing)** | Borrow money to buy stocks (bullish, adding leverage) |
| **Short sell (securities lending)** | Borrow shares to sell (bearish, shorting) |
| **Margin balance** | Total outstanding margin-buy amount |
| **Short balance** | Total outstanding short-sell amount |

Rising margin balance → Growing bullish sentiment
Falling margin balance → Waning bullish sentiment

### 12.2 Fetching Margin Trading Data in eqlib

```python
from eqlib import get_margin_data

# Get margin trading data for the past 3 months
margin = get_margin_data(start_date="2024-01-01", end_date="2024-03-31")

# Returned fields:
# - date: trading date
# - margin_balance: outstanding margin-buy balance (100M CNY)
# - margin_buy: new margin-buy amount (100M CNY)
# - margin_repay: margin-buy repayment amount (100M CNY)
# - short_balance: outstanding short-sell balance (100M CNY)

# Calculate margin balance change rate
margin["balance_change_pct"] = margin["margin_balance"].diff(5) / margin["margin_balance"].shift(5) * 100
```

### 12.3 Caveats

- `margin_repay` has NaN in the first row (no prior-day balance to compute from)
- Rapidly growing margin balance may signal excessive leverage — be alert to pullback risk

---

## 13. Limit Up/Down Statistics

**Limit up/down statistics** reflect overall market sentiment and systemic risk.

### 13.1 Market Breadth Indicators

| Indicator | Description |
|-----------|-------------|
| **Limit-up count** | Number of stocks hitting the daily upper price limit |
| **Limit-down count** | Number of stocks hitting the daily lower price limit |
| **Limit-up/down ratio** | Limit-up count / limit-down count |

Many limit-up stocks → Positive market sentiment
Many limit-down stocks → Pessimistic market sentiment
Limit-down count > 100 → Potential systemic risk

### 13.2 Fetching Limit Up/Down Statistics in eqlib

```python
from eqlib import get_limit_up_down_stats

# Get limit up/down statistics for the past 30 days
limit_stats = get_limit_up_down_stats()

# Returned fields:
# - date: trading date
# - limit_up_count: number of limit-up stocks
# - limit_down_count: number of limit-down stocks

# Systemic risk alert
latest_down = limit_stats["limit_down_count"].iloc[-1]
if latest_down > 100:
    print("Systemic risk alert: limit-down count exceeds 100")
```

### 13.3 Caveats

- The API only supports the most recent 30 trading days
- Limit up/down data may change during trading hours

---

## 14. Restricted Share Unlock

**Restricted share unlock** refers to previously non-tradeable shares becoming eligible for public trading, which may create selling pressure.

### 14.1 Types of Unlock

| Type | Description |
|------|-------------|
| **IPO founder lock-up shares** | Shares that IPO shareholders committed to holding for a specified period |
| **Private placement lock-up shares** | Shares that private placement participants committed to holding |
| **Equity incentive lock-up shares** | Shares locked up under employee incentive plans |

After unlocking, original holders can freely sell. If the unlock volume is large and holders are eager to reduce their positions, the stock price may come under pressure.

### 14.2 Fetching Unlock Data in eqlib

```python
from eqlib import get_restriction_release

# Get the unlock schedule for the next 30 days
releases = get_restriction_release(days=30)

# Returned fields:
# - code: stock code
# - name: stock name
# - release_date: unlock date
# - release_amount: number of shares unlocked (10,000 shares)
# - release_value: market value of unlocked shares (100M CNY)
# - release_pct: percentage of pre-unlock tradeable market cap

# Sort by unlock market value, focus on large unlocks
large_releases = releases[releases["release_value"] > 50]
print(f"Large unlocks (>5B CNY) in the next 30 days: {len(large_releases)} stocks")
```

### 14.3 Strategy Application

Exclude stocks with imminent large unlocks during stock selection:

```python
# Exclude stocks with unlock market value exceeding 10B CNY in the next 30 days
releases = get_restriction_release(days=30)
large_release_codes = releases[releases["release_value"] > 100]["code"].tolist()

candidates = ["601390", "600519", "000858"]
safe_candidates = [c for c in candidates if c not in large_release_codes]
```

---

## 15. How These Rules Are Reflected in eqlib

| Rule | How eqlib Handles It |
|------|----------------------|
| T+1 settlement | `position.closeable_amount` is 0 on the day of purchase |
| Limit up/down | Backtests do not auto-filter (manual logic required); affects order fills in live trading |
| Stamp duty | Set via `OrderCost(close_tax=0.0005)` |
| ST filtering | `filter_st_stocks(securities)` |
| Index constituents | `get_index_stocks('000300.XSHG')` |
| Benchmark comparison | `set_benchmark('000300.XSHG')` |
| Fundamental data | `fetch_factor_data()`, `get_fundamentals()` |
| North-bound capital | `get_north_money_flow()` |
| Margin trading | `get_margin_data()` |
| Limit up/down statistics | `get_limit_up_down_stats()` |
| Restricted share unlock | `get_restriction_release()` |

---

## 16. Next Steps

- **Complete all prerequisites**: [Python Basics](python-basics.md), [Technical Analysis Fundamentals](technical-concepts.md)
- **Start the main tutorials**: [Tutorial 00: Environment & Quantitative Foundations](../00-getting-started.md)
- **Tutorial 00** includes an overview of common A-share market mistakes: [00-getting-started.md](../00-getting-started.md)
- **Tutorial 07: Sector Rotation Strategy** covers A-share sector rotation in depth: [06-sector-rotation.md](../06-sector-rotation.md)
- **Tutorial 10: A-Share Specific Data & Risk Management** provides a detailed guide to A-share-specific data and risk management: [10-ashare-data-risk.md](../10-ashare-data-risk.md)
