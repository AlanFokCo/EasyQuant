# 前置知识：Python 基础与环境配置

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **适合** | 几乎没有 Python 经验、或尚未用过 pandas / numpy 的读者 |
    | **预计** | 60～90 分钟（可查表跳读） |
    | **若已熟练** | 请直接开始 [Tutorial 00](../00_environment_and_first_run.md) |

> 本文面向**几乎没有 Python 经验**的读者。如果你已经能熟练使用 pandas、numpy，可直接跳过本文，从 [Tutorial 00](../00_environment_and_first_run.md) 开始。

---

## 目录

1. [为什么用 Python 做量化](#1-为什么用-python-做量化)
2. [环境管理：Python 版本与虚拟环境](#2-环境管理python-版本与虚拟环境)
3. [Python 核心语法速查](#3-python-核心语法速查)
4. [pandas 核心用法](#4-pandas-核心用法)
5. [numpy 基础](#5-numpy-基础)
6. [在 eqlib 策略中用到这些知识的位置](#6-在-eqlib-策略中用到这些知识的位置)
7. [下一步](#7-下一步)

---

## 1. 为什么用 Python 做量化

Python 在量化交易领域是事实上的标准语言：

- **语法简洁**：同样的逻辑，Python 代码比 Java/C++ 少 3–5 倍
- **金融生态完整**：`pandas`（数据）、`numpy`（数学）、`matplotlib`（图表）、`scipy`（统计）
- **免费数据源**：`akshare`、`tushare` 等提供 A 股全量历史数据
- **AI 编程助手**：常见大模型工具可辅助写代码与排错（需自行核对逻辑与数据）。

`eqlib` 策略文件就是普通的 `.py` 文件，你只需掌握本文中的核心用法即可上手。

---

## 2. 环境管理：Python 版本与虚拟环境

### 2.1 版本要求

`eqlib` 要求 **Python ≥ 3.10**（见 `pyproject.toml` 中 `requires-python`）。  
推荐使用 **3.11** 或 **3.12**。

```bash
# 检查当前 Python 版本
python --version
# 或
python3 --version
```

### 2.2 虚拟环境（强烈推荐）

虚拟环境让每个项目的依赖互不干扰，避免"安装了 A 包结果把 B 项目搞坏"的问题。

```bash
# 在仓库根目录创建虚拟环境
cd EasyQuant
python3 -m venv .venv

# 激活（macOS / Linux）
source .venv/bin/activate

# 激活（Windows CMD）
.venv\Scripts\activate.bat

# 激活（Windows PowerShell）
.venv\Scripts\Activate.ps1

# 验证：激活后命令提示符前会显示 (.venv)
# 安装 eqlib 及其所有依赖
pip install easyquant-eqlib  # PyPI（推荐）
# 或在仓库根目录执行：pip install .
```

激活后所有 `python` 和 `pip` 命令都在虚拟环境中运行，不影响系统 Python。

### 2.3 退出虚拟环境

```bash
deactivate
```

### 2.4 依赖清单

| 包 | 用途 | 是否必须 |
|----|------|---------|
| `akshare` | A 股数据源 | 必须 |
| `pandas` | 表格数据处理 | 必须 |
| `numpy` | 数学计算 | 必须 |
| `matplotlib` | 图表生成 | 必须 |
| `scipy` | 统计分析 | 必须 |
| `pyarrow` | 更快的磁盘缓存 | 可选 |
| `pytest` | 运行单元测试 | 开发时 |

执行 `pip install easyquant-eqlib`（或 `pip install .`）会自动安装前 5 个。

---

## 3. Python 核心语法速查

以下是在 eqlib 策略中最常用的 Python 语法。

### 3.1 变量与数据类型

```python
# 数字
price = 5.23          # float
count = 100           # int
ratio = 0.3           # float（30%）

# 字符串
code = '601390'       # 股票代码用字符串

# 布尔值
has_position = True
is_bull_market = False

# None（空值）
signal = None
```

### 3.2 条件判断

```python
price = 5.23
ma20 = 5.10

# 单条件
if price > ma20:
    print('价格高于均线')

# 多条件
if price > ma20 * 1.02:
    print('买入信号')
elif price < ma20 * 0.98:
    print('卖出信号')
else:
    print('观望')

# and / or
if price > ma20 and volume > avg_volume:
    print('量价配合，强烈信号')
```

### 3.3 函数定义

```python
def calculate_ma(prices, period):
    """计算简单移动均线"""
    return prices.tail(period).mean()

# 调用
ma5 = calculate_ma(close_prices, 5)
ma20 = calculate_ma(close_prices, 20)
```

> eqlib 中 `initialize`、`market_open` 等都是你定义的函数，引擎在对应时机自动调用它们。

### 3.4 循环

```python
securities = ['601390', '600519', '000858']

# for 循环
for code in securities:
    print(code)

# 带索引的 for 循环
for i, code in enumerate(securities):
    print(i, code)

# 条件中断
for code in securities:
    if some_condition:
        break   # 终止循环
    if another_condition:
        continue  # 跳过本次，继续下一个
```

### 3.5 列表（List）

```python
# 创建
my_stocks = ['601390', '600519', '000858']

# 追加
my_stocks.append('000001')

# 删除
my_stocks.remove('600519')

# 检查是否包含
if '601390' in my_stocks:
    print('在股票池中')

# 列表推导式（简洁写法）
strong_stocks = [s for s in all_stocks if returns[s] > 0.05]
```

### 3.6 字典（Dict）

```python
# 持仓字典示例
positions = {
    '601390': {'amount': 1000, 'cost': 4.85},
    '600519': {'amount': 100,  'cost': 1680.0},
}

# 读取
amount = positions['601390']['amount']

# 安全读取（不存在时返回默认值）
pos = positions.get('000858', None)

# 检查是否存在
if '601390' in positions:
    print('持有该股票')

# 遍历
for code, pos_info in positions.items():
    print(code, pos_info['amount'])
```

### 3.7 类型转换与常用内置函数

```python
# 类型转换
x = int('100')        # 字符串 → 整数
y = float('3.14')     # 字符串 → 浮点数
s = str(100)          # 整数 → 字符串

# 数学
abs(-5)               # 绝对值 → 5
max(3, 5, 2)          # 最大值 → 5
min(3, 5, 2)          # 最小值 → 2
round(3.1415, 2)      # 四舍五入 → 3.14

# 长度
len([1, 2, 3])        # → 3
len('601390')         # → 6
```

---

## 4. pandas 核心用法

`pandas` 是 eqlib 中最核心的数据处理库。`attribute_history` 返回的就是 `DataFrame`。

### 4.1 DataFrame 基础

```python
import pandas as pd

# eqlib 中常见的 DataFrame 结构
# attribute_history('601390', 5, '1d', ['open', 'high', 'low', 'close', 'volume'])
# 返回类似：
#            open   high    low  close      volume
# 2024-01-02  4.85   4.92   4.80   4.88  1234567890
# 2024-01-03  4.89   4.95   4.85   4.92  987654321
# ...

df = attribute_history('601390', 20, '1d', ['close', 'volume'])

# 取单列（返回 Series）
close = df['close']        # 收盘价 Series
volume = df['volume']      # 成交量 Series

# 取多列（返回 DataFrame）
price_vol = df[['close', 'volume']]

# 检查是否为空
if df.empty:
    return

# 检查行数
if len(df) < 20:
    return  # 数据不足
```

### 4.2 Series 常用操作

```python
close = df['close']    # pandas Series

# 最新价（最后一行）
latest_price = close.iloc[-1]

# 最早一行
oldest_price = close.iloc[0]

# 取最后 N 行
last_5 = close.tail(5)
last_5_mean = last_5.mean()     # 5 日均价

# 取前 N 行
first_5 = close.head(5)

# 统计
close.mean()      # 均值
close.std()       # 标准差
close.max()       # 最大值
close.min()       # 最小值
close.sum()       # 求和

# 判断序列中每个值是否满足条件
above_ma = close > close.mean()    # 返回 True/False 的 Series
```

### 4.3 滚动计算（Rolling）

```python
# 20 日滚动均线
ma20 = close.rolling(window=20).mean()

# 20 日滚动标准差
std20 = close.rolling(window=20).std()

# 取最新的滚动值
latest_ma20 = ma20.iloc[-1]
```

### 4.4 日期索引

```python
# DataFrame 的索引通常是日期
# 按日期切片
recent = df.loc['2024-06-01':'2024-06-30']

# 获取最新日期
latest_date = df.index[-1]
```

### 4.5 常见的 NaN 处理

```python
import pandas as pd

# 检查是否有 NaN
has_nan = df.isnull().any().any()

# 删除含 NaN 的行
df_clean = df.dropna()

# 用 0 填充 NaN
df_filled = df.fillna(0)

# 检查某个值是否是 NaN
import math
if math.isnan(some_value):
    return
```

---

## 5. numpy 基础

`numpy` 主要提供高效的数值计算，在 eqlib 中常通过 pandas 间接使用。

```python
import numpy as np

prices = [4.85, 4.92, 4.88, 4.95, 5.01]  # Python 列表
arr = np.array(prices)                      # 转为 numpy 数组

# 数学运算（逐元素）
arr * 1.02          # 全部乘以 1.02
arr - arr.mean()    # 减去均值（标准化第一步）

# 统计
np.mean(arr)        # 均值
np.std(arr)         # 标准差
np.max(arr)         # 最大值
np.min(arr)         # 最小值

# 条件筛选
high_prices = arr[arr > 4.9]    # 筛选大于 4.9 的元素

# nan 安全版本（pandas NaN 与 numpy nan 兼容）
np.isnan(some_value)     # 检查是否 NaN
np.nanmean(arr)          # 忽略 NaN 的均值
```

---

## 6. 在 eqlib 策略中用到这些知识的位置

| 代码片段 | 用到的 Python/pandas 概念 |
|---------|--------------------------|
| `g.security = '601390'` | 变量赋值 |
| `hist = attribute_history(...)` | 函数调用，返回 DataFrame |
| `hist['close'].mean()` | DataFrame 列选取 + Series 方法 |
| `hist['close'].tail(5).mean()` | Series 尾部切片 + 均值 |
| `hist['close'].iloc[-1]` | 整数位置索引 |
| `if price > ma_fast > ma_slow:` | 链式比较 |
| `context.portfolio.positions.get(sec)` | 字典 `.get()` |
| `for sec in g.securities:` | 列表 for 循环 |
| `if df.empty or len(df) < 20: return` | 条件判断 + 函数提前返回 |

---

## 7. 下一步

- **继续前置知识**：[技术分析基础概念](technical_concepts.md)、[A 股市场基础知识](ashare_knowledge.md)
- **进入正式教程**：[Tutorial 00：环境与第一次运行](../00_environment_and_first_run.md)

> **推荐资源**：如需系统学习 Python，菜鸟教程（runoob.com/python3）或《Python 编程：从入门到实践》均适合零基础入门。pandas 官方文档（pandas.pydata.org/docs）是最权威的参考手册。
