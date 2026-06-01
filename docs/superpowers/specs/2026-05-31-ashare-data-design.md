# A股特色数据源整合设计规格

> 创建时间：2026-05-31
> 状态：设计完成，待实现

---

## 一、概述

### 背景

EasyQuant 已有完善的数据获取模块（`eqlib/data.py`），但缺少 A股市场特有的数据维度。这些数据是 A股独有的超额收益来源，对风控和市场判断至关重要。

### 目标

在 `eqlib/data.py` 中新增 4 个数据获取函数：
- 北向资金流向
- 融资融券数据
- 涨跌停统计
- 限售股解禁

### 优先级

P1（高）— A股特色数据是超额收益来源，对实盘风控重要。

---

## 二、架构

### 方案选择

**扩展 data.py**（方案 A）

在现有 `eqlib/data.py` 中新增函数，与 `get_price()`、`get_money_flow()` 等并列。

**理由**：
- 与现有风格统一
- 用户导入方便
- `get_billboard_list()` 已按此模式实现

### 模块位置

```
eqlib/data.py（扩展）
├── get_north_money_flow()     # 北向资金流向
├── get_margin_data()          # 融资融券数据
├── get_limit_up_down_stats()  # 涨跌停统计
└── get_restriction_release()  # 限售股解禁
```

---

## 三、函数设计

### 3.1 get_north_money_flow（北向资金流向）

**数据粒度**：汇总级别（沪股通+深股通合计）

```python
def get_north_money_flow(start_date=None, end_date=None) -> pd.DataFrame:
    """北向资金流向（汇总级别）
    
    Parameters:
        start_date: 开始日期 (YYYY-MM-DD 或 datetime)
        end_date: 结束日期，默认今天
        
    Returns:
        DataFrame with columns:
        - date: 交易日期
        - net_buy: 净买入额（亿元）
        - total_buy: 总买入额（亿元）
        - total_sell: 总卖出额（亿元）
        
    数据源: akshare stock_hsgt_north_net_flow_in_em
    
    用途:
    1. 北向连续3日大买入（> 50亿）→ 预期上涨
    2. 北向连续3日大卖出（> 50亿）→ 预期下跌
    3. 北向流向与指数走势背离 → 反转信号
    """
```

### 3.2 get_margin_data（融资融券数据）

**市场范围**：全市场汇总

```python
def get_margin_data(start_date=None, end_date=None) -> pd.DataFrame:
    """融资融券数据（全市场汇总）
    
    Parameters:
        start_date: 开始日期
        end_date: 结束日期，默认今天
        
    Returns:
        DataFrame with columns:
        - date: 交易日期
        - margin_balance: 融资余额（亿元）
        - margin_buy: 融资买入额（亿元）
        - margin_repay: 融资偿还额（亿元）
        - short_balance: 融券余额（亿元）
        
    数据源: akshare margin_detail_szse / margin_detail_sse
    
    用途:
    1. 融资余额快速上升（5日增速 > 10%）→ 情绪过热预警
    2. 融资余额快速下降（5日降速 > 10%）→ 情绪恐慌
    3. 融资买入占比过高（> 15%）→ 杠杆风险
    """
```

### 3.3 get_limit_up_down_stats（涨跌停统计）

**返回格式**：每日汇总

```python
def get_limit_up_down_stats(start_date=None, end_date=None) -> pd.DataFrame:
    """涨跌停统计（每日汇总）
    
    Parameters:
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        DataFrame with columns:
        - date: 交易日期
        - limit_up_count: 涨停数量
        - limit_down_count: 跌停数量
        - limit_up_pct: 涨停占比（可选）
        - limit_down_pct: 跌停占比（可选）
        
    数据源: akshare stock_ztzt_pool_ztgc / stock_ztzt_pool_dtgc
    
    用途:
    1. 跌停数 > 100 → 系统性风险预警，减仓
    2. 涨停数 > 100 且跌停数 < 10 → 情绪亢奋，注意回调
    3. 涨跌停比值持续 < 0.5 → 市场转弱
    """
```

### 3.4 get_restriction_release（限售股解禁）

**筛选范围**：未来解禁列表

```python
def get_restriction_release(days=30) -> pd.DataFrame:
    """限售股解禁（未来解禁列表）
    
    Parameters:
        days: 未来天数范围，默认 30 天
        
    Returns:
        DataFrame with columns:
        - code: 股票代码
        - name: 股票名称
        - release_date: 解禁日期
        - release_amount: 解禁数量（万股）
        - release_value: 解禁市值（亿元）
        - release_pct: 占总股本比例
        
    数据源: akshare stock_restriction_release
    
    用途:
    1. 大额解禁（> 50亿）临近 → 预期下跌
    2. 解禁后股价异常强势 → 警惕庄家托盘
    """
```

---

## 四、akshare API 映射

| 函数 | akshare API | 主要原始列 |
|-----|-------------|----------|
| `get_north_money_flow` | `stock_hsgt_north_net_flow_in_em(symbol="北上")` | 日期、当日成交净买额、当日资金流入、当日资金流出 |
| `get_margin_data` | `margin_detail_szse()` + `margin_detail_sse()` | 日期、融资余额、融资买入额、融资偿还额、融券余额 |
| `get_limit_up_down_stats` | `stock_ztzt_pool_ztgc()` + `stock_ztzt_pool_dtgc()` | 日期、涨停家数、跌停家数 |
| `get_restriction_release` | `stock_restriction_release(symbol="解禁日期")` | 股票代码、股票名称、解禁日期、解禁数量、解禁市值 |

---

## 五、缓存与错误处理

### 缓存策略

**简单缓存**：复用现有 `_cache` 和 `_cache_lock` 机制

```python
cache_key = f"north_flow_{sd}_{ed}"

with _cache_lock:
    if cache_key in _cache:
        return _cache[cache_key]

# ... 获取数据后存入缓存
with _cache_lock:
    _cache[cache_key] = df
    if len(_cache) > _MAX_CACHE_ENTRIES:
        _cache.popitem(last=False)
```

### 错误处理

**返回空 DataFrame**：API 失败时返回空 DataFrame，与现有函数一致

```python
try:
    df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
    # ... 数据处理
    return df
except Exception as e:
    log.debug("get_north_money_flow: %s", e)
    return pd.DataFrame()
```

---

## 六、导出配置

`eqlib/__init__.py` 的 Data 部分追加：

```python
# A-share market specific data  [EXPERIMENTAL]
from eqlib.data import (
    get_north_money_flow,
    get_margin_data,
    get_limit_up_down_stats,
    get_restriction_release,
)
```

---

## 七、测试策略

### 测试文件

新建 `tests/test_ashare_data.py`

### 测试内容

```python
class TestNorthMoneyFlow:
    def test_basic_fetch(self):
        """验证能获取北向资金数据"""
        df = get_north_money_flow(start_date="2024-01-01", end_date="2024-01-31")
        assert len(df) > 0
        assert "net_buy" in df.columns
        
    def test_date_range_filtering(self):
        """验证日期范围筛选正确"""
        
    def test_empty_result_handling(self):
        """验证 API 失败时返回空 DataFrame"""

class TestMarginData:
    def test_basic_fetch(self):
        """验证能获取融资融券数据"""
        
    def test_market_merge(self):
        """验证深交所和上交所数据正确合并"""

class TestLimitUpDownStats:
    def test_basic_fetch(self):
        """验证能获取涨跌停统计"""
        df = get_limit_up_down_stats(...)
        assert "limit_up_count" in df.columns
        assert "limit_down_count" in df.columns

class TestRestrictionRelease:
    def test_future_releases(self):
        """验证能获取未来解禁列表"""
        df = get_restriction_release(days=30)
        assert "release_date" in df.columns
        assert "release_value" in df.columns
        
    def test_date_filtering(self):
        """验证只返回未来 N 天的解禁"""
```

---

## 八、使用示例

```python
# === 北向资金风向标 ===
from eqlib import get_north_money_flow

df = get_north_money_flow(start_date="2024-01-01", end_date="2024-01-31")

# 连续3日大买入判断
if df["net_buy"].iloc[-3:].sum() > 150:
    print("北向资金大买入，预期上涨")

# === 融资融券情绪预警 ===
from eqlib import get_margin_data

df = get_margin_data(start_date="2024-01-01", end_date="2024-01-31")

margin_change = df["margin_balance"].pct_change(5).iloc[-1]
if margin_change > 0.10:
    print("融资余额快速上升，情绪过热预警")

# === 涨跌停系统性风险预警 ===
from eqlib import get_limit_up_down_stats

df = get_limit_up_down_stats(start_date="2024-01-01", end_date="2024-01-31")

if df["limit_down_count"].iloc[-1] > 100:
    print("跌停数超100，系统性风险预警")

# === 限售股解禁预警 ===
from eqlib import get_restriction_release

df = get_restriction_release(days=30)

large_releases = df[df["release_value"] > 50]
if len(large_releases) > 0:
    print(f"未来30天有 {len(large_releases)} 只股票大额解禁")

# === 与 PortfolioRiskMonitor 结合 ===
from eqlib import PortfolioRiskMonitor, get_limit_up_down_stats

stats = get_limit_up_down_stats(days=1)
if stats["limit_down_count"].iloc[-1] > 100:
    # 在 daily_check 中触发系统性风险预警
    ...
```

---

## 九、验收标准

1. 4 个数据函数能正常返回 DataFrame
2. 列名标准化正确
3. 日期范围筛选正确
4. API 失败时返回空 DataFrame
5. 数据单位统一为"亿元"
6. 缓存机制正确工作
7. 函数从 `eqlib` 模块正确导出
8. 单元测试覆盖核心场景

---

## 十、后续扩展

- 将涨跌停数据集成到 PortfolioRiskMonitor 的 daily_check
- 北向资金与指数走势背离检测
- 融资融券情绪极值预警通知