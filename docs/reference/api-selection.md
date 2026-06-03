# 选股策略 API

> 选股函数、过滤器、TopN 和多因子选择器。

---

## 编写选股策略

**模式一：普通函数**

```python
def my_selection(context):
    candidates = filter_st_stocks(["601390", "600519"])
    df = fetch_factor_data(candidates, fields=["pe"])
    return df.sort_values("pe").head(5).index.tolist()
```

**模式二：StockSelector 子类**

```python
class MySelector(StockSelector):
    def filter(self, candidates, context):
        return filter_st_stocks(candidates)
    def rank(self, securities, context):
        return TopNSelector(factor="pe", top_n=5).rank(securities, context)
```

**模式三：内置选择器**

```python
TopNSelector(factor="pe", top_n=5, ascending=True)
MultiFactorSelector(factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4}, top_n=5)
```

## 注册与调用

```python
# 在 initialize 中调用
run_selection(my_selection, rebalance="monthly:1")

# 或通过 run_strategy 参数
result = run_strategy(initialize, selection_func=my_selection, selection_rebalance="weekly:0")
```

## 工具函数

| API | 说明 |
|-----|------|
| `StockSelector` | 选股基类 |
| `filter_st_stocks(securities)` | 剔除 ST 股票 |
| `filter_paused_stocks(securities, context)` | 剔除停牌股票 |
| `filter_low_price_stocks(securities, min_price=2.0)` | 剔除低价股 |
| `filter_high_pe_stocks(securities, max_pe=100.0)` | 剔除高 PE 股 |
| `fetch_factor_data(securities, fields=None)` | 获取多维度因子数据 |
| `TopNSelector(factor, top_n, ascending)` | 单因子 Top-N 选择器 |
| `MultiFactorSelector(factors, top_n)` | 多因子加权选择器 |

### TopNSelector

单因子 Top-N 选股器，按单个因子排序选出前 N 只股票。

```python
TopNSelector(factor="pe", top_n=5, ascending=True)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `factor` | `str` | 因子名称，如 `"pe"`, `"pb"`, `"pct_change"` |
| `top_n` | `int` | 选出股票数量 |
| `ascending` | `bool` | `True` 升序（越小越好），`False` 降序（越大越好） |

```python
# 选 PE 最低的 5 只股票
selector = TopNSelector(factor="pe", top_n=5, ascending=True)
top_stocks = selector.rank(candidates, context)
```

### MultiFactorSelector

多因子加权选股器，按加权综合得分排序选出前 N 只股票。

```python
MultiFactorSelector(factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4}, top_n=5)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `factors` | `dict` | 因子权重映射，负权重表示越低越好 |
| `top_n` | `int` | 选出股票数量 |

```python
# 多因子选股：低 PE (40%)、低 PB (20%)、高动量 (40%)
selector = MultiFactorSelector(
    factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
    top_n=10
)
selected = selector.rank(candidates, context)
```

### fetch_factor_data

获取多维度因子数据，用于选股筛选和打分。

```python
fetch_factor_data(securities, fields=None)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `securities` | `list[str]` | 股票代码列表 |
| `fields` | `list[str]` | 因子字段列表，默认全部 |

可用字段：`price`, `pct_change`, `total_value`, `pe`, `pb`, `turnover`, `ma5`, `ma10`, `ma20`, `rsi14`。

```python
# 获取候选股票的 PE、PB、动量因子
candidates = ["601390", "600519", "000858"]
df = fetch_factor_data(candidates, fields=["pe", "pb", "pct_change"])

# 按 PE 排序
df_sorted = df.sort_values("pe", ascending=True)
```
