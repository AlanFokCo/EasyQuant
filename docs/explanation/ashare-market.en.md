# A-Share Market Essentials

A brief introduction to the A-share market fundamentals you need to know when using EasyQuant. For the full guide, see [A-Share Market Prerequisites](../tutorials/prerequisites/ashare-knowledge.md).

---

## Stock Tickers

| Type | Format | Example |
|------|--------|---------|
| Individual stock | 6-digit number | `'601390'` (China Railway) |
| Index | 6-digit number + exchange suffix | `'000300.XSHG'` (CSI 300) |
| Shanghai exchange | `.XSHG` | `'600519.XSHG'` (Kweichow Moutai) |
| Shenzhen exchange | `.XSHE` | `'000858.XSHE'` (Wuliangye) |

!!! tip "Shorthand in eqlib"

    In `order*` and `attribute_history`, you can use just the 6-digit ticker (e.g., `'601390'`) — the framework auto-detects the exchange. Benchmark indices should include the suffix (e.g., `'000300.XSHG'`).

## Trading Rules

| Rule | Description |
|------|-------------|
| **T+1** | Shares bought today can only be sold on the next trading day |
| **Limit up/down** | Main board ±10%, ChiNext / STAR Market ±20% |
| **Trading hours** | 9:30–11:30, 13:00–15:00 |
| **Minimum lot** | 100 shares (1 lot) |

## Major Indices

| Index | Ticker | Description |
|-------|--------|-------------|
| CSI 300 | `000300.XSHG` | Large-cap blue chips, most commonly used benchmark |
| SSE 50 | `000016.XSHG` | Mega-cap |
| CSI 500 | `000905.XSHG` | Mid-cap |
| ChiNext Index | `399006.XSHE` | Growth stocks |

## Trading Cost Structure

| Cost | Buy | Sell | Notes |
|------|-----|------|-------|
| Stamp duty | 0% | 0.05% | Sell-side only (halved since Aug 2023) |
| Commission | 0.025% | 0.025% | Minimum ¥5 per trade (inclusive of regulatory fees) |

Configure in eqlib:

```python
set_order_cost(OrderCost(
    open_tax=0,
    close_tax=0.0005,
    open_commission=0.00025,
    close_commission=0.00025,
    min_commission=5,
))
```
