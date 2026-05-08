"""Data fetching layer using akshare."""

import datetime
from functools import lru_cache
from typing import Optional

import akshare as ak
import pandas as pd
from eqlib.data_cache import _slice_by_date


# ============================================================
# Internal caches
# ============================================================

_cache: dict = {}
_spot_cache: Optional[pd.DataFrame] = None
_spot_fetch_time: float = 0


def _invalidate_spot_cache(max_age_seconds=60):
    """Invalidate spot data cache if older than max_age_seconds."""
    global _spot_cache, _spot_fetch_time
    import time
    if _spot_cache is not None and (time.time() - _spot_fetch_time) > max_age_seconds:
        _spot_cache = None
        _spot_fetch_time = 0


def _get_spot_data():
    """Get current A-share spot data with short-lived cache.

    All functions that need real-time market data go through this
    to avoid redundant network calls within the same minute.
    """
    global _spot_cache, _spot_fetch_time
    import time

    _invalidate_spot_cache()
    if _spot_cache is not None:
        return _spot_cache

    try:
        df = ak.stock_zh_a_spot_em()
        _spot_cache = df
        _spot_fetch_time = time.time()
        return df
    except Exception:
        return pd.DataFrame()


def _code_to_akshare(code: str) -> str:
    """Strip exchange suffix: '601390.XSHG' -> '601390'."""
    return code.replace(".XSHG", "").replace(".XSHE", "")


def _normalize_date(d) -> str:
    """Convert date to YYYYMMDD string."""
    if isinstance(d, datetime.datetime):
        return d.strftime("%Y%m%d")
    if isinstance(d, datetime.date):
        return d.strftime("%Y%m%d")
    return str(d).replace("-", "")


def _to_numeric(df: pd.DataFrame, cols: list[str]):
    """Vectorized numeric conversion for selected columns."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def _rename_cols(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename columns, keeping only those that exist."""
    available = {k: v for k, v in mapping.items() if k in df.columns}
    if available:
        df = df[list(available.keys())].copy()
        df.rename(columns=available, inplace=True)
    return df


# ============================================================
# Daily OHLCV
# ============================================================

def _is_etf(code: str) -> bool:
    """Check if a code is an ETF (51xxxx, 15xxxx, 16xxxx, 18xxxx)."""
    return code.startswith(("51", "15", "16", "18"))


def _is_index(code: str) -> bool:
    """Check if a code is a common A-share index.

    Uses the exchange suffix to disambiguate Shanghai indices from Shenzhen
    stocks that share the same 000xxx code prefix:

    - ``000xxx.XSHG`` → Shanghai index  (e.g. 000300.XSHG 沪深300)
    - ``399xxx``       → Shenzhen index (e.g. 399001.XSHE 深证成指)
    - ``000xxx.XSHE``  → Shenzhen stock (e.g. 000858.XSHE 五粮液)
    - ``000xxx``       → treated as stock (no suffix → ambiguous, safe default)
    """
    stripped = code.replace(".XSHG", "").replace(".XSHE", "")
    # Shanghai indices: require the explicit .XSHG suffix so that plain
    # 000xxx codes (Shenzhen stocks like 000858 五粮液) are NOT misclassified.
    if ".XSHG" in code and stripped.startswith("000"):
        return True
    # Shenzhen indices always start with 399 regardless of suffix presence.
    return stripped.startswith("399")


def fetch_stock_data(code: str, start_date, end_date, adjust: str = "qfq") -> pd.DataFrame:
    """Fetch daily OHLCV data from akshare for a single stock, ETF, or index.

    Index data is cached by ``(symbol, adjust)`` only (without the date range)
    because ``stock_zh_index_daily_em`` returns the full history in one call.
    Subsequent requests for different date ranges reuse the same cached frame,
    eliminating redundant full-history downloads.
    """
    symbol = _code_to_akshare(code)
    is_idx = _is_index(code)

    # Indices: canonical cache key excludes date range (full history is always fetched)
    if is_idx:
        cache_key = (symbol, "index", adjust)
    else:
        cache_key = (symbol, str(start_date), str(end_date), adjust)

    if cache_key in _cache:
        df_cached = _cache[cache_key]
        # For index data cached without date range, slice to the requested window
        if is_idx and start_date and end_date:
            return _slice_by_date(df_cached, start_date, end_date)
        return df_cached

    try:
        if is_idx:
            # Indices: always download full history once and cache it all
            prefix = "sh" if ".XSHG" in code else "sz"
            df = ak.stock_zh_index_daily_em(symbol=f"{prefix}{symbol}")
        elif _is_etf(symbol):
            df = ak.fund_etf_hist_em(
                symbol=symbol, period="daily",
                start_date=_normalize_date(start_date),
                end_date=_normalize_date(end_date), adjust=adjust,
            )
        else:
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=_normalize_date(start_date),
                end_date=_normalize_date(end_date), adjust=adjust,
            )
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df = _rename_cols(df, {
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "money",
        "涨跌幅": "pct_change", "涨跌额": "price_change", "换手率": "turnover",
    })

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    # Store the full frame under the canonical key
    _cache[cache_key] = df

    # Slice to the requested window before returning
    if is_idx and start_date and end_date:
        return _slice_by_date(df, start_date, end_date)

    return df


def get_price(security, start_date=None, end_date=None, frequency: str = "daily",
              fields=None, count=None):
    """Get historical price data.

    Parameters:
        security: stock code (str or list)
        start_date / end_date: date range
        frequency: 'daily' or '1m'
        fields: list of fields to return
        count: number of bars (alternative to date range)
    """
    if isinstance(security, (list, tuple)):
        return {sec: f for sec in security
                if not (f := get_price(sec, start_date, end_date, frequency, fields, count)).empty}

    if count is not None and start_date is None:
        end_date = end_date or datetime.datetime.now()
        lookback = end_date if isinstance(end_date, datetime.date) else end_date.date()
        start_date = datetime.datetime.combine(lookback, datetime.time()) - datetime.timedelta(days=count * 2 + 60)

    if end_date is None:
        end_date = datetime.datetime.now()
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=count * 2 if count else 365)

    df = fetch_stock_data(security, start_date, end_date)
    if not df.empty and fields:
        df = df[[f for f in fields if f in df.columns]]
    return df


def history(count: int, unit: str = "1d", field: str = "close",
            security=None, df: bool = False):
    """Get the most recent `count` bars ending at current_dt."""
    from eqlib._state import _context

    if security is None:
        security = _context.universe

    end_date = _context.current_dt
    start_date = end_date - datetime.timedelta(days=count * 2 + 60)

    df_data = get_price(security, start_date=start_date, end_date=end_date)
    if isinstance(df_data, dict):
        result = {sec: frame[field].tail(count)
                  for sec, frame in df_data.items()
                  if not frame.empty and field in frame.columns}
        return pd.DataFrame(result) if df else result

    if not df_data.empty and field in df_data.columns:
        series = df_data[field].tail(count)
        return series.to_frame() if df else series
    return pd.DataFrame()


def attribute_history(security, count: int, unit: str = "1d",
                      fields=("close",), df: bool = True,
                      skip_paused: bool = True, fq: str = "pre"):
    """Get historical attribute data for a single security."""
    from eqlib._state import _context
    from eqlib.engine import _get_preloaded

    # Fast path: slice from preloaded in-memory data
    preloaded = _get_preloaded()
    if preloaded is not None and preloaded.panel is not None:
        sec_df = preloaded.panel.get(security)
        if sec_df is not None and not sec_df.empty:
            available = [f for f in fields if f in sec_df.columns]
            if not available:
                return pd.DataFrame()
            # Filter up to current date (avoid future data leakage)
            current = _context.current_dt
            if current is not None:
                sec_df = sec_df[sec_df.index <= current]
            result = sec_df[available].tail(count)
            return result

    # Fallback: fetch from disk/network
    end_date = _context.current_dt
    start_date = end_date - datetime.timedelta(days=count * 2 + 60)

    adjust_map = {"pre": "qfq", "post": "hfq", None: ""}
    df_data = fetch_stock_data(security, start_date, end_date, adjust=adjust_map.get(fq, "qfq"))
    if df_data.empty:
        return pd.DataFrame()

    df_data = df_data.tail(count)
    available = [f for f in fields if f in df_data.columns]
    if available:
        df_data = df_data[available]
    return df_data


# ============================================================
# Security lists
# ============================================================

def get_all_securities(types=None, date=None) -> pd.DataFrame:
    """Get list of all A-share stocks."""
    try:
        df = _get_spot_data()
        if df.empty:
            return pd.DataFrame()
        result = df[["代码", "名称"]].copy()
        result.rename(columns={"代码": "code", "名称": "name"}, inplace=True)
        return result
    except Exception:
        return pd.DataFrame()


def get_trade_days(start_date=None, end_date=None, count=None) -> list[datetime.date]:
    """Get list of trading days."""
    try:
        df = ak.tool_trade_date_hist_sina()
        if df.empty:
            return []
        col = df.columns[0]
        dates = pd.to_datetime(df[col]).dt.date.unique()
        dates = sorted(dates.tolist())

        if count is not None:
            return dates[-count:]

        if start_date:
            sd = pd.Timestamp(start_date).date()
            dates = [d for d in dates if d >= sd]
        if end_date:
            ed = pd.Timestamp(end_date).date()
            dates = [d for d in dates if d <= ed]
        return dates
    except Exception:
        # Fallback: use bundled A-share holiday list to exclude non-trading days.
        # This prevents including Chinese public holidays when akshare is offline.
        end_date = end_date or datetime.date.today()
        start_date = start_date or (end_date - datetime.timedelta(days=365))
        return [d for d in _iter_days(start_date, end_date)
                if d.weekday() < 5 and not _is_ashare_holiday(d)]


# ── Bundled A-share holiday calendar (fallback when akshare is unavailable) ────
#
# Key mainland Chinese public holidays that cause trading halts.
# Format: set of datetime.date objects.  This list covers 2020-2028 and should
# be extended when adding backtests beyond that range.

def _build_holiday_set() -> frozenset:
    """Return a frozenset of known A-share non-trading dates (2020-2028)."""
    raw = [
        # 2020
        "2020-01-01", "2020-01-24", "2020-01-27", "2020-01-28", "2020-01-29",
        "2020-01-30", "2020-01-31", "2020-04-04", "2020-04-06",
        "2020-05-01", "2020-05-04", "2020-05-05",
        "2020-06-25", "2020-06-26",
        "2020-10-01", "2020-10-02", "2020-10-05", "2020-10-06", "2020-10-07",
        "2020-10-08",
        # 2021
        "2021-01-01",
        "2021-02-11", "2021-02-12", "2021-02-15", "2021-02-16", "2021-02-17",
        "2021-04-05",
        "2021-05-03", "2021-05-04", "2021-05-05",
        "2021-06-14",
        "2021-09-20", "2021-09-21",
        "2021-10-01", "2021-10-04", "2021-10-05", "2021-10-06", "2021-10-07",
        # 2022
        "2022-01-03",
        "2022-01-31", "2022-02-01", "2022-02-02", "2022-02-03", "2022-02-04",
        "2022-04-04", "2022-04-05",
        "2022-05-02", "2022-05-03", "2022-05-04",
        "2022-06-03",
        "2022-09-12",
        "2022-10-03", "2022-10-04", "2022-10-05", "2022-10-06", "2022-10-07",
        # 2023
        "2023-01-02",
        "2023-01-23", "2023-01-24", "2023-01-25", "2023-01-26", "2023-01-27",
        "2023-04-05",
        "2023-05-01", "2023-05-02", "2023-05-03",
        "2023-06-22", "2023-06-23",
        "2023-09-29",
        "2023-10-02", "2023-10-03", "2023-10-04", "2023-10-05", "2023-10-06",
        # 2024
        "2024-01-01",
        "2024-02-12", "2024-02-13", "2024-02-14", "2024-02-15", "2024-02-16",
        "2024-04-04", "2024-04-05",
        "2024-05-01", "2024-05-02", "2024-05-03",
        "2024-06-10",
        "2024-09-17",
        "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-07",
        # 2025
        "2025-01-01",
        "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-03",
        "2025-04-04",
        "2025-05-01", "2025-05-02",
        "2025-05-31",
        "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07",
        # 2026
        "2026-01-01",
        "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
        "2026-04-06",
        "2026-05-01",
        "2026-06-19",
        "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
        # 2027
        "2027-01-01",
        "2027-02-08", "2027-02-09", "2027-02-10", "2027-02-11",
        "2027-04-05",
        "2027-05-03",
        "2027-06-09",
        "2027-10-01", "2027-10-04", "2027-10-05", "2027-10-06", "2027-10-07",
        # 2028
        "2028-01-03",
        "2028-01-27", "2028-01-28", "2028-01-31", "2028-02-01",
        "2028-04-04",
        "2028-05-01",
        "2028-05-29",
        "2028-10-02", "2028-10-03", "2028-10-04", "2028-10-05", "2028-10-06",
    ]
    return frozenset(
        datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in raw
    )


_ASHARE_HOLIDAYS: frozenset = _build_holiday_set()


def _is_ashare_holiday(date: datetime.date) -> bool:
    """Return True if *date* is a known A-share public holiday (non-trading day)."""
    return date in _ASHARE_HOLIDAYS


def _iter_days(start, end):
    """Iterate days between start and end inclusive."""
    current = start
    while current <= end:
        yield current
        current += datetime.timedelta(days=1)


# ============================================================
# Market scanning / screening
# ============================================================

def scan_market(min_price=10, min_pct_change=3, max_pct_change=5,
                max_pe=50) -> pd.DataFrame:
    """Scan A-shares and filter by price, change, and P/E."""
    try:
        return _filter_spot({
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_change", "市盈率-动态": "pe",
        }, {
            "price": min_price,
            "pct_change": (min_pct_change, max_pct_change),
            "pe": (None, max_pe),
        })
    except Exception:
        return pd.DataFrame()


def get_financial_screen(min_pe=None, max_pe=None, min_pb=None, max_pb=None,
                         min_roe=None, min_revenue=None, min_profit=None) -> pd.DataFrame:
    """Screen stocks by financial criteria using real-time market data."""
    try:
        filters = {
            "pe": (min_pe, max_pe),
            "pb": (min_pb, max_pb),
        }
        return _filter_spot({
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_change", "市盈率-动态": "pe",
            "市净率": "pb", "总市值": "total_value", "换手率": "turnover",
        }, filters)
    except Exception:
        return pd.DataFrame()


def _filter_spot(rename_map: dict, filters: dict) -> pd.DataFrame:
    """Shared helper: fetch spot data, rename columns, apply filters."""
    df = _get_spot_data()
    if df.empty:
        return pd.DataFrame()

    df = _rename_cols(df, rename_map)

    num_cols = [c for c in set(rename_map.values()) if c not in ("code", "name")]
    _to_numeric(df, num_cols)

    for col, constraint in filters.items():
        if col not in df.columns:
            continue
        if isinstance(constraint, tuple):
            lo, hi = constraint
            if lo is not None:
                df = df[df[col] >= lo]
            if hi is not None:
                df = df[df[col] <= hi]
        else:
            df = df[df[col] >= constraint]

    return df.reset_index(drop=True)


def check_golden_cross(code, fast_period=5, slow_period=20, min_rows=30) -> bool:
    """Check if a stock has a golden cross (fast MA crossing above slow MA)."""
    try:
        symbol = _code_to_akshare(code)
        stock_df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
    except Exception:
        return False

    if len(stock_df) < min_rows or "收盘" not in stock_df.columns:
        return False

    fast = stock_df["收盘"].rolling(fast_period).mean()
    slow = stock_df["收盘"].rolling(slow_period).mean()

    return fast.iloc[-2] < slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]


# ============================================================
# File I/O
# ============================================================

def download_stock_data(code, start_date, end_date, adjust: str = "qfq",
                        output_dir=None, filename=None) -> Optional[str]:
    """Download daily OHLCV data and save to CSV."""
    import os

    df = fetch_stock_data(code, start_date, end_date, adjust)
    if df.empty:
        return None

    filename = filename or f"{_code_to_akshare(code)}_daily.csv"
    path = os.path.join(output_dir, filename) if output_dir else filename
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    df.to_csv(path)
    return path


def load_csv(path, index_col: str = "date", parse_dates: bool = True) -> pd.DataFrame:
    """Load stock data from a local CSV file."""
    try:
        return pd.read_csv(path, index_col=index_col, parse_dates=parse_dates)
    except Exception:
        return pd.DataFrame()


def clear_cache():
    """Clear the internal data cache."""
    _cache.clear()
    global _spot_cache, _spot_fetch_time
    _spot_cache = None
    _spot_fetch_time = 0


# ============================================================
# Financial data
# ============================================================

def get_financial_abstract(code) -> pd.DataFrame:
    """Get financial summary for a stock."""
    try:
        df = ak.stock_financial_abstract(symbol=_code_to_akshare(code))
        if df.empty:
            return pd.DataFrame()
        df = df.set_index(df.columns[0])
        df.index.name = "metric"
        return df
    except Exception:
        return pd.DataFrame()


def get_fundamentals(code, date=None) -> pd.DataFrame:
    """Get fundamental data for a stock (alias for get_financial_abstract)."""
    return get_financial_abstract(code)


# ============================================================
# Index and industry constituents
# ============================================================

def get_index_stocks(index_code) -> pd.DataFrame:
    """Get constituent stocks of an index."""
    try:
        df = ak.index_stock_cons(symbol=_code_to_akshare(index_code))
        if df.empty:
            return pd.DataFrame()
        return _rename_cols(df, {
            "品种代码": "code", "品种名称": "name", "纳入日期": "include_date",
        })
    except Exception:
        return pd.DataFrame()


def get_industry_list() -> list[str]:
    """Get list of all industry board names."""
    try:
        df = ak.stock_board_industry_name_em()
        if df.empty:
            return []
        col = "板块名称" if "板块名称" in df.columns else df.columns[0]
        return df[col].tolist()
    except Exception:
        return []


def get_industry_stocks(industry_name) -> pd.DataFrame:
    """Get constituent stocks of an industry board."""
    try:
        df = ak.stock_board_industry_cons_em(symbol=industry_name)
        if df.empty:
            return pd.DataFrame()
        df = _rename_cols(df, {
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_change", "成交量": "volume", "成交额": "money",
            "振幅": "amplitude", "最高": "high", "最低": "low",
            "今开": "open", "昨收": "prev_close", "换手率": "turnover",
            "市盈率-动态": "pe", "市净率": "pb", "总市值": "total_value",
            "流通市值": "float_value",
        })
        _to_numeric(df, ["price", "pct_change", "volume", "money",
                          "pe", "pb", "total_value", "float_value", "turnover"])
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_industry(code) -> Optional[dict]:
    """Get industry classification for a single stock."""
    try:
        df = ak.stock_individual_info_em(symbol=_code_to_akshare(code))
        if df.empty:
            return None
        data = dict(zip(df["item"], df["value"]))
        return {
            "code": _code_to_akshare(code),
            "name": data.get("股票简称", ""),
            "industry": data.get("行业", ""),
        }
    except Exception:
        return None


# ============================================================
# Concept/theme boards
# ============================================================

def get_concept_list() -> list[str]:
    """Get list of all concept/theme board names."""
    try:
        df = ak.stock_board_concept_name_em()
        if df.empty:
            return []
        col = "板块名称" if "板块名称" in df.columns else df.columns[0]
        return df[col].tolist()
    except Exception:
        return []


def get_concept_stocks(concept_name) -> pd.DataFrame:
    """Get constituent stocks of a concept/theme board."""
    try:
        df = ak.stock_board_concept_cons_em(symbol=concept_name)
        if df.empty:
            return pd.DataFrame()
        df = _rename_cols(df, {
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_change", "成交量": "volume", "成交额": "money",
            "换手率": "turnover", "市盈率-动态": "pe", "市净率": "pb",
        })
        _to_numeric(df, ["price", "pct_change", "volume", "money",
                          "turnover", "pe", "pb"])
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# ============================================================
# Minute-level K-line data
# ============================================================

def fetch_minute_data(code, period: str = "5m", start_date=None,
                      end_date=None, adjust: str = "qfq") -> pd.DataFrame:
    """Fetch minute-level K-line data."""
    try:
        symbol = _code_to_akshare(code)
        period_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
        ak_period = period_map.get(period, "5")

        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period=ak_period, adjust=adjust)
        if df.empty:
            return pd.DataFrame()

        df = _rename_cols(df, {
            "时间": "datetime", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "涨跌幅": "pct_change",
            "涨跌额": "price_change", "成交量": "volume", "成交额": "money",
            "振幅": "amplitude", "换手率": "turnover",
        })

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)

        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df.index <= pd.Timestamp(end_date)]

        return df
    except Exception:
        return pd.DataFrame()


def get_price_minute(security, count=None, period: str = "5m",
                     fields=None, adjust: str = "qfq"):
    """Get minute-level price data."""
    if isinstance(security, (list, tuple)):
        return {sec: f for sec in security
                if not (f := get_price_minute(sec, count, period, fields, adjust)).empty}

    df = fetch_minute_data(security, period=period, adjust=adjust)
    if df.empty:
        return df
    if count is not None:
        df = df.tail(count)
    if fields:
        df = df[[f for f in fields if f in df.columns]]
    return df


# ============================================================
# Tick data
# ============================================================

def get_tick_data(code, trade_date=None) -> pd.DataFrame:
    """Fetch intraday tick (transaction) data for current day."""
    try:
        symbol = _code_to_akshare(code)
        ak_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        df = ak.stock_zh_a_tick_tx_js(symbol=ak_symbol)
        if df.empty:
            return pd.DataFrame()

        rename = {}
        for col in df.columns:
            if col in ("时间", "trade_time", "time"):
                rename[col] = "time"
            elif col in ("价格", "price"):
                rename[col] = "price"
            elif col in ("成交量", "volume", "手数"):
                rename[col] = "volume"
            elif col in ("成交额", "money", "amount"):
                rename[col] = "money"
            elif col in ("买卖", "direction", "方向"):
                rename[col] = "direction"

        available = {k: v for k, v in rename.items() if k in df.columns}
        df.rename(columns=available, inplace=True)
        return df
    except Exception:
        return pd.DataFrame()


# ============================================================
# P0: Market snapshot, security info
# ============================================================

def get_current_data() -> dict:
    """Get current market snapshot for all A-shares.

    Returns dict mapping code -> dict with attributes:
    code, name, price, pct_change, volume, money, high, low,
    open, prev_close, turnover, pe, pb, total_value, float_value.
    """
    try:
        df = _get_spot_data()
        if df.empty:
            return {}

        df = _rename_cols(df, {
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_change", "成交量": "volume", "成交额": "money",
            "最高": "high", "最低": "low", "今开": "open",
            "昨收": "prev_close", "换手率": "turnover",
            "市盈率-动态": "pe", "市净率": "pb", "总市值": "total_value",
            "流通市值": "float_value",
        })

        _to_numeric(df, ["price", "pct_change", "volume", "money",
                          "high", "low", "open", "prev_close",
                          "turnover", "pe", "pb", "total_value", "float_value"])

        if "code" not in df.columns:
            return {}
        return {row["code"]: row.to_dict() for _, row in df.iterrows()}
    except Exception:
        return {}


def get_security_info(code):
    """Get basic information for a single security."""
    try:
        df = ak.stock_individual_info_em(symbol=_code_to_akshare(code))
        if df.empty:
            return None
        data = dict(zip(df["item"], df["value"]))
        info = type("SecurityInfo", (), {})()
        info.code = code
        info.name = data.get("股票简称", "")
        info.industry = data.get("行业", "")
        info.total_shares = data.get("总股本", 0)
        info.float_shares = data.get("流通股", 0)
        info.total_value = data.get("总市值", 0)
        info.float_value = data.get("流通市值", 0)
        info.list_date = data.get("上市时间", "")
        return info
    except Exception:
        return None


def get_valuation(code) -> Optional[dict]:
    """Get valuation data for a stock (uses cached spot data)."""
    try:
        symbol = _code_to_akshare(code)
        df = _get_spot_data()
        if df.empty:
            return None

        row = df[df["代码"] == symbol]
        if row.empty:
            return None

        r = row.iloc[0]
        return {
            "code": symbol,
            "name": str(r.get("名称", "")),
            "price": _safe_float(r.get("最新价")),
            "pe": _safe_float(r.get("市盈率-动态")),
            "pb": _safe_float(r.get("市净率")),
            "total_value": _safe_float(r.get("总市值")),
            "float_value": _safe_float(r.get("流通市值")),
            "turnover": _safe_float(r.get("换手率")),
            "pct_change": _safe_float(r.get("涨跌幅")),
        }
    except Exception:
        return None


def _safe_float(val) -> float:
    """Safely convert to float, returning 0 on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# P1: Money flow, billboard, index weights, extras
# ============================================================

def get_money_flow(code, start_date=None, end_date=None, count=None) -> pd.DataFrame:
    """Get capital flow data for a stock.

    Note: start_date/end_date are not supported by the underlying API;
    use `count` to limit the number of recent days returned.
    """
    try:
        symbol = _code_to_akshare(code)
        market = "sh" if symbol.startswith("6") else "sz"
        if count is None:
            count = 100

        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if df.empty:
            return pd.DataFrame()

        df = _rename_cols(df, {
            "日期": "date", "收盘价": "close", "涨跌幅": "pct_change",
            "主力净流入-净额": "main_net_inflow",
            "主力净流入-净占比": "main_net_pct",
            "超大单净流入-净额": "super_order_net",
            "超大单净流入-净占比": "super_order_pct",
            "大单净流入-净额": "big_order_net",
            "大单净流入-净占比": "big_order_pct",
            "中单净流入-净额": "mid_order_net",
            "中单净流入-净占比": "mid_order_pct",
            "小单净流入-净额": "small_order_net",
            "小单净流入-净占比": "small_order_pct",
        })

        if count > 0:
            df = df.tail(count)
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_billboard_list(stock_list=None, date=None, start_date=None,
                       end_date=None) -> pd.DataFrame:
    """Get dragon/tiger list (abnormal trading activity stocks)."""
    try:
        if date is not None:
            sd = ed = _normalize_date(date)
        else:
            sd = _normalize_date(start_date) if start_date else _normalize_date(datetime.date.today())
            ed = _normalize_date(end_date) if end_date else sd

        df = ak.stock_lhb_detail_em(start_date=sd, end_date=ed)
        if df.empty:
            return pd.DataFrame()

        df = _rename_cols(df, {
            "代码": "code", "名称": "name", "上榜日": "trade_date",
            "收盘价": "close", "涨跌幅": "pct_change",
            "龙虎榜净买额": "net_buy", "龙虎榜买入额": "total_buy",
            "龙虎榜卖出额": "total_sell", "龙虎榜成交额": "total_amount",
            "市场总成交额": "market_amount", "换手率": "turnover",
            "上榜原因": "reason", "上榜后1日": "post_1d",
            "上榜后2日": "post_2d", "上榜后5日": "post_5d",
            "上榜后10日": "post_10d",
        })

        _to_numeric(df, ["close", "pct_change", "net_buy", "total_buy",
                          "total_sell", "total_amount", "market_amount",
                          "turnover", "post_1d", "post_2d", "post_5d", "post_10d"])

        if stock_list:
            df = df[df["code"].isin(stock_list)]
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_index_weights(index_code, date=None) -> pd.DataFrame:
    """Get constituent stock weights for an index."""
    try:
        df = ak.index_stock_cons_weight_csindex(symbol=_code_to_akshare(index_code))
        if df.empty:
            return pd.DataFrame()
        df = _rename_cols(df, {
            "成分券代码": "code", "成分券名称": "name", "权重": "weight",
        })
        _to_numeric(df, ["weight"])
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_extras(field: str, security_list=None, start_date=None,
               end_date=None) -> dict:
    """Get extra data fields (is_st, net_value, etc.) for securities.

    Uses vectorized operations instead of per-row iteration.
    """
    try:
        df = _get_spot_data()
        if df.empty:
            return {}

        if field == "is_st":
            df["code"] = df["代码"]
            df["name"] = df["名称"]
            df["is_st"] = df["name"].str.contains("ST", na=False)
            result = dict(zip(df["code"], df["is_st"]))
        elif field in ("net_value", "unit_net_value"):
            df["code"] = df["代码"]
            price = pd.to_numeric(df["最新价"], errors="coerce")
            pb = pd.to_numeric(df["市净率"], errors="coerce")
            result = dict(zip(df["code"], (price / pb).fillna(0)))
        else:
            return {}

        if security_list:
            result = {k: v for k, v in result.items() if k in security_list}
        return result
    except Exception:
        return {}


# ============================================================
# Universe management
# ============================================================

def set_universe(security_list):
    """Set the current stock universe for the strategy."""
    from eqlib._state import _context
    if _context is not None:
        _context.universe = security_list


def get_universe() -> list:
    """Get the current strategy's stock universe."""
    from eqlib._state import _context
    if _context is not None:
        return _context.universe or []
    return []


# ============================================================
# P0: Lifecycle callbacks
# ============================================================

def before_trading_start(func):
    """Register a function to be called before market open (9:30)."""
    from eqlib.engine import _register_before_start
    _register_before_start(func)


def after_trading_end(func):
    """Register a function to be called after market close (15:00)."""
    from eqlib.engine import _register_after_end
    _register_after_end(func)
