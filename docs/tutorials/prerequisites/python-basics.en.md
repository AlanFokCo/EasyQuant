# Prerequisites: Python Basics & Environment Setup

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Suitable for** | Readers with little or no Python experience, or those who have not yet used pandas / numpy |
    | **Estimated time** | 60–90 minutes (skim or skip sections you already know) |
    | **Already proficient?** | Go straight to [Tutorial 00](../00-getting-started.md) |

> This article is for readers with **very little Python experience**. If you are already comfortable with pandas and numpy, feel free to skip this article and start from [Tutorial 00](../00-getting-started.md).

---

## Table of Contents

1. [Why Python for Quantitative Trading](#1-why-python-for-quantitative-trading)
2. [Environment Management: Python Version & Virtual Environments](#2-environment-management-python-version--virtual-environments)
3. [Python Core Syntax Cheat Sheet](#3-python-core-syntax-cheat-sheet)
4. [pandas Core Usage](#4-pandas-core-usage)
5. [numpy Basics](#5-numpy-basics)
6. [Where These Concepts Appear in eqlib Strategies](#6-where-these-concepts-appear-in-eqlib-strategies)
7. [Next Steps](#7-next-steps)

---

## 1. Why Python for Quantitative Trading { #1-why-python-for-quantitative-trading }

Python is the de facto standard language in quantitative trading:

- **Concise syntax**: The same logic requires 3–5× less code than Java/C++
- **Complete financial ecosystem**: `pandas` (data), `numpy` (math), `matplotlib` (charts), `scipy` (statistics)
- **Free data sources**: `akshare`, `tushare`, etc. provide full historical A-share data
- **AI coding assistants**: Common LLM tools can help write code and debug (but always verify logic and data yourself).

An `eqlib` strategy file is just a regular `.py` file — you only need the core skills covered in this article to get started.

---

## 2. Environment Management: Python Version & Virtual Environments { #2-environment-management-python-version--virtual-environments }

### 2.1 Version Requirements

`eqlib` requires **Python >= 3.10** (see `requires-python` in `pyproject.toml`).
We recommend **3.11** or **3.12**.

```bash
# Check your current Python version
python --version
# or
python3 --version
```

### 2.2 Virtual Environments (Strongly Recommended)

Virtual environments keep each project's dependencies isolated, preventing the classic problem of "installing package A breaks project B."

```bash
# Create a virtual environment in the repository root
cd EasyQuant
python3 -m venv .venv

# Activate (macOS / Linux)
source .venv/bin/activate

# Activate (Windows CMD)
.venv\Scripts\activate.bat

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Verify: after activation, the prompt is prefixed with (.venv)
# Install eqlib and all its dependencies
pip install easyquant-eqlib  # PyPI (recommended)
# Or from the repository root: pip install .
```

Once activated, all `python` and `pip` commands run inside the virtual environment and do not affect the system Python.

### 2.3 Exiting the Virtual Environment

```bash
deactivate
```

### 2.4 Dependency List

| Package | Purpose | Required? |
|---------|---------|-----------|
| `akshare` | A-share data source | Required |
| `pandas` | Tabular data processing | Required |
| `numpy` | Numerical computation | Required |
| `matplotlib` | Chart generation | Required |
| `scipy` | Statistical analysis | Required |
| `pyarrow` | Faster disk caching | Optional |
| `pytest` | Running unit tests | Development |

Running `pip install easyquant-eqlib` (or `pip install .`) automatically installs the first five.

---

## 3. Python Core Syntax Cheat Sheet { #3-python-core-syntax-cheat-sheet }

Below are the Python constructs most frequently used in eqlib strategies.

### 3.1 Variables & Data Types

```python
# Numbers
price = 5.23          # float
count = 100           # int
ratio = 0.3           # float (30%)

# Strings
code = '601390'       # stock code as string

# Booleans
has_position = True
is_bull_market = False

# None (null value)
signal = None
```

### 3.2 Conditional Statements

```python
price = 5.23
ma20 = 5.10

# Single condition
if price > ma20:
    print('Price above moving average')

# Multiple conditions
if price > ma20 * 1.02:
    print('Buy signal')
elif price < ma20 * 0.98:
    print('Sell signal')
else:
    print('Hold / observe')

# and / or
if price > ma20 and volume > avg_volume:
    print('Price-volume confirmation, strong signal')
```

### 3.3 Function Definitions

```python
def calculate_ma(prices, period):
    """Calculate simple moving average"""
    return prices.tail(period).mean()

# Call
ma5 = calculate_ma(close_prices, 5)
ma20 = calculate_ma(close_prices, 20)
```

> In eqlib, `initialize`, `market_open`, etc. are functions you define; the engine calls them automatically at the appropriate lifecycle points.

### 3.4 Loops

```python
securities = ['601390', '600519', '000858']

# for loop
for code in securities:
    print(code)

# for loop with index
for i, code in enumerate(securities):
    print(i, code)

# Conditional control flow
for code in securities:
    if some_condition:
        break   # terminate loop
    if another_condition:
        continue  # skip to next iteration
```

### 3.5 Lists

```python
# Create
my_stocks = ['601390', '600519', '000858']

# Append
my_stocks.append('000001')

# Remove
my_stocks.remove('600519')

# Membership check
if '601390' in my_stocks:
    print('In stock pool')

# List comprehension (concise syntax)
strong_stocks = [s for s in all_stocks if returns[s] > 0.05]
```

### 3.6 Dictionaries

```python
# Example: positions dictionary
positions = {
    '601390': {'amount': 1000, 'cost': 4.85},
    '600519': {'amount': 100,  'cost': 1680.0},
}

# Read
amount = positions['601390']['amount']

# Safe read (returns default if key does not exist)
pos = positions.get('000858', None)

# Membership check
if '601390' in positions:
    print('Holding this stock')

# Iterate
for code, pos_info in positions.items():
    print(code, pos_info['amount'])
```

### 3.7 Type Conversion & Common Built-in Functions

```python
# Type conversion
x = int('100')        # string -> int
y = float('3.14')     # string -> float
s = str(100)          # int -> string

# Math
abs(-5)               # absolute value -> 5
max(3, 5, 2)          # maximum -> 5
min(3, 5, 2)          # minimum -> 2
round(3.1415, 2)      # rounding -> 3.14

# Length
len([1, 2, 3])        # -> 3
len('601390')         # -> 6
```

---

## 4. pandas Core Usage { #4-pandas-core-usage }

`pandas` is the most important data processing library in eqlib. `attribute_history` returns a `DataFrame`.

### 4.1 DataFrame Basics

```python
import pandas as pd

# Common DataFrame structure in eqlib:
# attribute_history('601390', 5, '1d', ['open', 'high', 'low', 'close', 'volume'])
# Returns something like:
#            open   high    low  close      volume
# 2024-01-02  4.85   4.92   4.80   4.88  1234567890
# 2024-01-03  4.89   4.95   4.85   4.92  987654321
# ...

df = attribute_history('601390', 20, '1d', ['close', 'volume'])

# Select a single column (returns Series)
close = df['close']        # close price Series
volume = df['volume']      # volume Series

# Select multiple columns (returns DataFrame)
price_vol = df[['close', 'volume']]

# Check if empty
if df.empty:
    return

# Check row count
if len(df) < 20:
    return  # insufficient data
```

### 4.2 Common Series Operations

```python
close = df['close']    # pandas Series

# Latest price (last row)
latest_price = close.iloc[-1]

# First row
oldest_price = close.iloc[0]

# Last N rows
last_5 = close.tail(5)
last_5_mean = last_5.mean()     # 5-day average price

# First N rows
first_5 = close.head(5)

# Statistics
close.mean()      # mean
close.std()       # standard deviation
close.max()       # maximum
close.min()       # minimum
close.sum()       # sum

# Check whether each value meets a condition
above_ma = close > close.mean()    # returns a True/False Series
```

### 4.3 Rolling Calculations

```python
# 20-day rolling moving average
ma20 = close.rolling(window=20).mean()

# 20-day rolling standard deviation
std20 = close.rolling(window=20).std()

# Get the latest rolling value
latest_ma20 = ma20.iloc[-1]
```

### 4.4 Date Index

```python
# DataFrame index is usually dates
# Slice by date range
recent = df.loc['2024-06-01':'2024-06-30']

# Get the latest date
latest_date = df.index[-1]
```

### 4.5 Common NaN Handling

```python
import pandas as pd

# Check for NaN values
has_nan = df.isnull().any().any()

# Drop rows containing NaN
df_clean = df.dropna()

# Fill NaN with 0
df_filled = df.fillna(0)

# Check whether a specific value is NaN
import math
if math.isnan(some_value):
    return
```

---

## 5. numpy Basics { #5-numpy-basics }

`numpy` primarily provides efficient numerical computation and is often used indirectly through pandas in eqlib.

```python
import numpy as np

prices = [4.85, 4.92, 4.88, 4.95, 5.01]  # Python list
arr = np.array(prices)                      # convert to numpy array

# Element-wise math operations
arr * 1.02          # multiply all elements by 1.02
arr - arr.mean()    # subtract mean (first step in normalization)

# Statistics
np.mean(arr)        # mean
np.std(arr)         # standard deviation
np.max(arr)         # maximum
np.min(arr)         # minimum

# Conditional filtering
high_prices = arr[arr > 4.9]    # filter elements greater than 4.9

# NaN-safe versions (pandas NaN and numpy nan are compatible)
np.isnan(some_value)     # check for NaN
np.nanmean(arr)          # mean ignoring NaN values
```

---

## 6. Where These Concepts Appear in eqlib Strategies { #6-where-these-concepts-appear-in-eqlib-strategies }

| Code Snippet | Python/pandas Concept Used |
|--------------|---------------------------|
| `g.security = '601390'` | Variable assignment |
| `hist = attribute_history(...)` | Function call returning a DataFrame |
| `hist['close'].mean()` | DataFrame column selection + Series method |
| `hist['close'].tail(5).mean()` | Series tail slice + mean |
| `hist['close'].iloc[-1]` | Integer-location indexing |
| `if price > ma_fast > ma_slow:` | Chained comparison |
| `context.portfolio.positions.get(sec)` | Dictionary `.get()` |
| `for sec in g.securities:` | List for-loop |
| `if df.empty or len(df) < 20: return` | Conditional check + early return |

---

## 7. Next Steps { #7-next-steps }

- **Continue prerequisites**: [Technical Analysis Fundamentals](technical-concepts.md), [A-Share Market Fundamentals](ashare-knowledge.md)
- **Start the main tutorials**: [Tutorial 00: Environment & Quantitative Foundations](../00-getting-started.md)

> **Recommended resources**: For systematic Python learning, the official Python Tutorial (docs.python.org/3/tutorial) is a great starting point. The pandas official documentation (pandas.pydata.org/docs) is the most authoritative reference manual.
