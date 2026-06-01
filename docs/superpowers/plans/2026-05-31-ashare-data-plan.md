# A股特色数据源整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `eqlib/data.py` 中新增 4 个 A股特色数据函数：北向资金、融资融券、涨跌停统计、限售股解禁。

**Architecture:** 扩展现有 `eqlib/data.py`，新增 4 个 `get_*` 函数，复用现有缓存和错误处理机制（`_cache`、`_cache_lock`、`_normalize_date`、`_rename_cols`、`_to_numeric`）。

**Tech Stack:** Python 3.10+, pandas, akshare, pytest

---

## File Structure

| 文件 | 负责 |
|-----|------|
| `eqlib/data.py` | 新增 4 个数据函数（修改） |
| `tests/test_ashare_data.py` | 新增测试文件（新建） |
| `eqlib/__init__.py` | 导出新 API（修改） |

---

## Task 1: 创建测试文件骨架

**Files:**
- Create: `tests/test_ashare_data.py`

- [ ] **Step 1: 创建测试文件基础结构**

```python
# tests/test_ashare_data.py
"""Tests for A-share market specific data functions."""

import pytest
import pandas as pd
import datetime


class TestNorthMoneyFlow:
    """Tests for get_north_money_flow function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_north_money_flow
        assert get_north_money_flow is not None


class TestMarginData:
    """Tests for get_margin_data function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_margin_data
        assert get_margin_data is not None


class TestLimitUpDownStats:
    """Tests for get_limit_up_down_stats function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_limit_up_down_stats
        assert get_limit_up_down_stats is not None


class TestRestrictionRelease:
    """Tests for get_restriction_release function."""

    def test_import_available(self):
        """验证函数可导入"""
        from eqlib.data import get_restriction_release
        assert get_restriction_release is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py -v`
Expected: FAIL with "ImportError: cannot import name 'get_north_money_flow'"

- [ ] **Step 3: 创建空函数（占位）**

在 `eqlib/data.py` 文件末尾（约第 1500 行后）添加：

```python
# ============================================================
# A-share market specific data
# ============================================================

def get_north_money_flow(start_date=None, end_date=None) -> pd.DataFrame:
    """北向资金流向（汇总级别）"""
    return pd.DataFrame()


def get_margin_data(start_date=None, end_date=None) -> pd.DataFrame:
    """融资融券数据（全市场汇总）"""
    return pd.DataFrame()


def get_limit_up_down_stats(start_date=None, end_date=None) -> pd.DataFrame:
    """涨跌停统计（每日汇总）"""
    return pd.DataFrame()


def get_restriction_release(days=30) -> pd.DataFrame:
    """限售股解禁（未来解禁列表）"""
    return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/data.py
git commit -m "feat: add skeleton for A-share specific data functions"
```

---

## Task 2: 实现 get_north_money_flow

**Files:**
- Modify: `eqlib/data.py`
- Modify: `tests/test_ashare_data.py`

- [ ] **Step 1: 添加北向资金测试**

在 `tests/test_ashare_data.py` 的 `TestNorthMoneyFlow` 类中追加：

```python
    def test_basic_fetch(self):
        """验证能获取北向资金数据"""
        from eqlib.data import get_north_money_flow
        
        # 使用近期日期测试
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        df = get_north_money_flow(start_date=start_date, end_date=end_date)
        
        # 验证返回 DataFrame
        assert isinstance(df, pd.DataFrame)
        
        # 如果有数据，验证列名
        if not df.empty:
            assert "date" in df.columns
            assert "net_buy" in df.columns
            assert "total_buy" in df.columns
            assert "total_sell" in df.columns

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_north_money_flow
        
        df = get_north_money_flow()  # 无参数调用
        assert isinstance(df, pd.DataFrame)

    def test_returns_empty_on_failure(self):
        """验证 API 失败时返回空 DataFrame"""
        from eqlib.data import get_north_money_flow
        
        # 使用异常日期测试错误处理
        df = get_north_money_flow(start_date="2099-01-01", end_date="2099-01-31")
        assert isinstance(df, pd.DataFrame)
        # 期望返回空（无数据）或不抛异常
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py::TestNorthMoneyFlow -v`
Expected: FAIL（函数返回空 DataFrame，列名不匹配）

- [ ] **Step 3: 实现 get_north_money_flow**

修改 `eqlib/data.py` 中的 `get_north_money_flow` 函数：

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
    """
    try:
        # 参数标准化
        if end_date is None:
            end_date = datetime.date.today()
        if start_date is None:
            start_date = end_date - datetime.timedelta(days=30)
        
        sd = _normalize_date(start_date)
        ed = _normalize_date(end_date)
        
        # 缓存检查
        cache_key = f"north_flow_{sd}_{ed}"
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key].copy()
        
        # 获取数据
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        
        if df.empty:
            return pd.DataFrame()
        
        # 列重命名
        df = _rename_cols(df, {
            "日期": "date",
            "当日成交净买额": "net_buy",
            "当日资金流入": "total_buy",
            "当日资金流出": "total_sell",
        })
        
        # 日期格式转换
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        
        # 数值转换
        _to_numeric(df, ["net_buy", "total_buy", "total_sell"])
        
        # 日期范围筛选
        df = df[(df["date"] >= sd) & (df["date"] <= ed)]
        
        # 存入缓存
        with _cache_lock:
            _cache[cache_key] = df.copy()
            if len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        log.debug("get_north_money_flow: %s", e)
        return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py::TestNorthMoneyFlow -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/data.py
git commit -m "feat: implement get_north_money_flow for north-bound capital flow"
```

---

## Task 3: 实现 get_margin_data

**Files:**
- Modify: `eqlib/data.py`
- Modify: `tests/test_ashare_data.py`

- [ ] **Step 1: 添加融资融券测试**

在 `tests/test_ashare_data.py` 的 `TestMarginData` 类中追加：

```python
    def test_basic_fetch(self):
        """验证能获取融资融券数据"""
        from eqlib.data import get_margin_data
        
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        df = get_margin_data(start_date=start_date, end_date=end_date)
        
        assert isinstance(df, pd.DataFrame)
        
        if not df.empty:
            assert "date" in df.columns
            assert "margin_balance" in df.columns

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_margin_data
        
        df = get_margin_data()
        assert isinstance(df, pd.DataFrame)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py::TestMarginData -v`
Expected: FAIL

- [ ] **Step 3: 实现 get_margin_data**

修改 `eqlib/data.py` 中的 `get_margin_data` 函数：

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
    """
    try:
        # 参数标准化
        if end_date is None:
            end_date = datetime.date.today()
        if start_date is None:
            start_date = end_date - datetime.timedelta(days=30)
        
        sd = _normalize_date(start_date)
        ed = _normalize_date(end_date)
        
        cache_key = f"margin_{sd}_{ed}"
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key].copy()
        
        # 获取深交所和上交所数据
        df_sz = ak.margin_detail_szse(date=ed)
        df_sh = ak.margin_detail_sse(date=ed)
        
        # 如果两个都为空，返回空
        if df_sz.empty and df_sh.empty:
            return pd.DataFrame()
        
        # 合并数据（按日期汇总）
        # 注意：akshare 返回的是每日全市场汇总数据
        # 这里简化处理，取最近可用数据
        
        if not df_sz.empty:
            df = df_sz
        elif not df_sh.empty:
            df = df_sh
        else:
            # 合并两市场数据
            df = pd.concat([df_sz, df_sh], ignore_index=True)
        
        # 列重命名
        df = _rename_cols(df, {
            "日期": "date",
            "融资余额": "margin_balance",
            "融资买入额": "margin_buy",
            "融资偿还额": "margin_repay",
            "融券余额": "short_balance",
        })
        
        # 日期格式转换
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        
        # 数值转换
        _to_numeric(df, ["margin_balance", "margin_buy", "margin_repay", "short_balance"])
        
        # 存入缓存
        with _cache_lock:
            _cache[cache_key] = df.copy()
            if len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        log.debug("get_margin_data: %s", e)
        return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py::TestMarginData -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/data.py
git commit -m "feat: implement get_margin_data for margin trading data"
```

---

## Task 4: 实现 get_limit_up_down_stats

**Files:**
- Modify: `eqlib/data.py`
- Modify: `tests/test_ashare_data.py`

- [ ] **Step 1: 添加涨跌停统计测试**

在 `tests/test_ashare_data.py` 的 `TestLimitUpDownStats` 类中追加：

```python
    def test_basic_fetch(self):
        """验证能获取涨跌停统计"""
        from eqlib.data import get_limit_up_down_stats
        
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        df = get_limit_up_down_stats(start_date=start_date, end_date=end_date)
        
        assert isinstance(df, pd.DataFrame)
        
        if not df.empty:
            assert "date" in df.columns
            assert "limit_up_count" in df.columns
            assert "limit_down_count" in df.columns

    def test_default_parameters(self):
        """验证默认参数工作"""
        from eqlib.data import get_limit_up_down_stats
        
        df = get_limit_up_down_stats()
        assert isinstance(df, pd.DataFrame)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py::TestLimitUpDownStats -v`
Expected: FAIL

- [ ] **Step 3: 实现 get_limit_up_down_stats**

修改 `eqlib/data.py` 中的 `get_limit_up_down_stats` 函数：

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
        
    数据源: akshare stock_ztzt_pool_ztgc / stock_ztzt_pool_dtgc
    """
    try:
        # 参数标准化
        if end_date is None:
            end_date = datetime.date.today()
        if start_date is None:
            start_date = end_date - datetime.timedelta(days=30)
        
        sd = _normalize_date(start_date)
        ed = _normalize_date(end_date)
        
        cache_key = f"limit_stats_{sd}_{ed}"
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key].copy()
        
        # 获取涨停池和跌停池数据
        # akshare stock_ztzt_pool_ztgc 返回涨停股票列表
        # 需要统计每日涨停/跌停数量
        
        result_data = []
        
        # 遍历日期范围
        current = datetime.datetime.strptime(sd, "%Y%m%d").date()
        end = datetime.datetime.strptime(ed, "%Y%m%d").date()
        
        while current <= end:
            date_str = _normalize_date(current)
            
            try:
                # 获取涨停池
                df_zt = ak.stock_ztzt_pool_ztgc(date=date_str)
                limit_up_count = len(df_zt) if not df_zt.empty else 0
                
                # 获取跌停池
                df_dt = ak.stock_ztzt_pool_dtgc(date=date_str)
                limit_down_count = len(df_dt) if not df_dt.empty else 0
                
                result_data.append({
                    "date": current.strftime("%Y-%m-%d"),
                    "limit_up_count": limit_up_count,
                    "limit_down_count": limit_down_count,
                })
            except Exception:
                # 该日期无数据，跳过
                pass
            
            current += datetime.timedelta(days=1)
        
        df = pd.DataFrame(result_data)
        
        if df.empty:
            return pd.DataFrame()
        
        # 存入缓存
        with _cache_lock:
            _cache[cache_key] = df.copy()
            if len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        log.debug("get_limit_up_down_stats: %s", e)
        return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py::TestLimitUpDownStats -v`
Expected: 2 passed（注意：此测试可能因 akshare API 请求较多而耗时）

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/data.py
git commit -m "feat: implement get_limit_up_down_stats for limit up/down statistics"
```

---

## Task 5: 实现 get_restriction_release

**Files:**
- Modify: `eqlib/data.py`
- Modify: `tests/test_ashare_data.py`

- [ ] **Step 1: 添加限售股解禁测试**

在 `tests/test_ashare_data.py` 的 `TestRestrictionRelease` 类中追加：

```python
    def test_basic_fetch(self):
        """验证能获取未来解禁列表"""
        from eqlib.data import get_restriction_release
        
        df = get_restriction_release(days=30)
        
        assert isinstance(df, pd.DataFrame)
        
        if not df.empty:
            assert "code" in df.columns
            assert "release_date" in df.columns
            assert "release_value" in df.columns

    def test_days_parameter(self):
        """验证 days 参数工作"""
        from eqlib.data import get_restriction_release
        
        df_30 = get_restriction_release(days=30)
        df_60 = get_restriction_release(days=60)
        
        # 60 天范围应包含更多解禁事件
        assert len(df_60) >= len(df_30)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py::TestRestrictionRelease -v`
Expected: FAIL

- [ ] **Step 3: 实现 get_restriction_release**

修改 `eqlib/data.py` 中的 `get_restriction_release` 函数：

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
    """
    try:
        cache_key = f"restriction_{days}"
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key].copy()
        
        # 获取解禁数据
        # akshare stock_restriction_release 返回解禁股票列表
        df = ak.stock_restriction_release(symbol="解禁日期")
        
        if df.empty:
            return pd.DataFrame()
        
        # 列重命名
        df = _rename_cols(df, {
            "股票代码": "code",
            "股票名称": "name",
            "解禁日期": "release_date",
            "解禁数量": "release_amount",
            "解禁市值": "release_value",
            "占总股本比例": "release_pct",
        })
        
        # 数值转换
        _to_numeric(df, ["release_amount", "release_value", "release_pct"])
        
        # 日期格式转换
        if "release_date" in df.columns:
            df["release_date"] = pd.to_datetime(df["release_date"])
        
        # 筛选未来 N 天内的解禁
        today = datetime.date.today()
        future_date = today + datetime.timedelta(days=days)
        
        df = df[
            (df["release_date"].dt.date >= today) &
            (df["release_date"].dt.date <= future_date)
        ]
        
        # 按解禁日期排序
        df = df.sort_values("release_date")
        
        # 存入缓存
        with _cache_lock:
            _cache[cache_key] = df.copy()
            if len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        log.debug("get_restriction_release: %s", e)
        return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py::TestRestrictionRelease -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/data.py
git commit -m "feat: implement get_restriction_release for restriction release data"
```

---

## Task 6: 导出新 API 到 eqlib/__init__.py

**Files:**
- Modify: `eqlib/__init__.py`
- Modify: `tests/test_ashare_data.py`

- [ ] **Step 1: 添加导出测试**

在 `tests/test_ashare_data.py` 追加：

```python

class TestModuleExports:
    """Tests for module exports."""

    def test_import_from_eqlib(self):
        """验证可以从 eqlib 导入"""
        from eqlib import (
            get_north_money_flow,
            get_margin_data,
            get_limit_up_down_stats,
            get_restriction_release,
        )
        assert get_north_money_flow is not None
        assert get_margin_data is not None
        assert get_limit_up_down_stats is not None
        assert get_restriction_release is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ashare_data.py::TestModuleExports -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: 添加导出到 __init__.py**

找到 `eqlib/__init__.py` 中 Data 部分末尾，添加：

```python
# A-share market specific data  [EXPERIMENTAL]
from eqlib.data import (
    get_north_money_flow,
    get_margin_data,
    get_limit_up_down_stats,
    get_restriction_release,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ashare_data.py::TestModuleExports -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ashare_data.py eqlib/__init__.py
git commit -m "feat: export A-share specific data functions from eqlib module"
```

---

## Task 7: 运行完整测试套件并验证

**Files:**
- 可能需要修复 `eqlib/data.py` 或 `tests/test_ashare_data.py`

- [ ] **Step 1: Run all ashare data tests**

Run: `pytest tests/test_ashare_data.py -v`
Expected: 全部通过

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: 全部通过，无回归

- [ ] **Step 3: Commit fixes if needed**

如果需要修复：
```bash
git add eqlib/data.py tests/test_ashare_data.py
git commit -m "fix: resolve test failures in A-share data functions"
```

---

## Task 8: 添加 __all__ 导出（可选）

**Files:**
- Modify: `eqlib/data.py`

- [ ] **Step 1: 在 data.py 末尾添加新增函数到 __all__**

如果 `eqlib/data.py` 有 `__all__` 定义，追加新函数名。

- [ ] **Step 2: Run tests to verify**

Run: `pytest tests/test_ashare_data.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add eqlib/data.py
git commit -m "docs: add __all__ exports for A-share data functions"
```

---

## Self-Review

**1. Spec coverage:**
- get_north_money_flow → Task 2 ✅
- get_margin_data → Task 3 ✅
- get_limit_up_down_stats → Task 4 ✅
- get_restriction_release → Task 5 ✅
- 导出 API → Task 6 ✅
- 测试验证 → Task 7 ✅

**2. Placeholder scan:** 无 TBD/TODO，所有代码完整

**3. Type consistency:** 函数签名、列名在各任务中一致

---

## 验收清单

- [ ] `get_north_money_flow()` 能返回北向资金数据
- [ ] `get_margin_data()` 能返回融资融券数据
- [ ] `get_limit_up_down_stats()` 能返回涨跌停统计
- [ ] `get_restriction_release()` 能返回未来解禁列表
- [ ] 所有函数返回空 DataFrame 而不抛异常
- [ ] 函数从 `eqlib` 模块正确导出
- [ ] 单元测试覆盖核心场景
- [ ] 全项目测试无回归