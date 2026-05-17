"""Data fetching layer using akshare."""

import datetime
import threading
import requests
from functools import lru_cache
from typing import Optional, Union

import akshare as ak
import pandas as pd
from eqlib.data_cache import _slice_by_date

# Chinese calendar — primary source for A-share holiday detection.
# Falls back to hardcoded holidays + fixed-date rules if unavailable.
try:
    import chinese_calendar as _cc
    _CC_AVAILABLE = True
except ImportError:
    _CC_AVAILABLE = False


# ============================================================
# Internal caches
# ============================================================

_cache: dict = {}
_cache_lock = threading.Lock()  # guards _cache for concurrent access (M3)
_spot_cache: Optional[pd.DataFrame] = None
_spot_fetch_time: float = 0
_spot_lock = threading.Lock()  # guards _spot_cache / _spot_fetch_time
_LOOKBACK_DAYS_FACTOR = 2
_LOOKBACK_EXTRA_DAYS = 60


def _invalidate_spot_cache(max_age_seconds=60):
    """Invalidate spot data cache if older than max_age_seconds.

    Must be called with ``_spot_lock`` held.
    """
    global _spot_cache, _spot_fetch_time
    import time
    if _spot_cache is not None and (time.time() - _spot_fetch_time) > max_age_seconds:
        _spot_cache = None
        _spot_fetch_time = 0


def _get_spot_data():
    """Get current A-share spot data with short-lived cache.

    All functions that need real-time market data go through this
    to avoid redundant network calls within the same minute.
    Thread-safe via ``_spot_lock``.
    """
    global _spot_cache, _spot_fetch_time
    import time

    with _spot_lock:
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


def _compute_lookback(count: int, end_date: datetime.datetime) -> datetime.datetime:
    """Compute fallback lookback start date with a warmup buffer."""
    return end_date - datetime.timedelta(
        days=count * _LOOKBACK_DAYS_FACTOR + _LOOKBACK_EXTRA_DAYS
    )


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
    """Heuristic: exchange-traded fund codes (incl. 588 STAR board ETFs).

    Used for stamp-duty exemption on sell. New product codes appear over time;
    treat unknown codes as non-ETF (conservative on tax).
    """
    return code.startswith(("51", "15", "16", "18")) or code.startswith("588")


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


# ============================================================
# Daily OHLCV — Multi-source fallback
# ============================================================

def _fetch_from_em(symbol: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    """Source 1: EastMoney via akshare (primary)."""
    return ak.stock_zh_a_hist(
        symbol=symbol, period="daily",
        start_date=start_date, end_date=end_date, adjust=adjust,
    )


def _fetch_from_tencent(symbol: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    """Source 2: Tencent Finance direct API.

    URL: https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get
    Returns JSON with kline data: [date, open, close, high, low, volume, {}, change%, amount, '']
    Prices are ×100 (e.g., 1595.36 = ¥15.9536). Amount is in thousands of yuan.
    Note: Tencent requires YYYY-MM-DD date format (not YYYYMMDD).
    """
    prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
    full_symbol = f"{prefix}{symbol}"
    # adjust: qfq -> qfq, hfq -> hfq, "" -> ""
    adj_param = adjust if adjust else ""
    # Tencent needs YYYY-MM-DD format
    start_fmt = start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:8]
    end_fmt = end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:8]
    url = (
        "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        f"?param={full_symbol},day,{start_fmt},{end_fmt},1000,{adj_param}"
    )
    try:
        r = requests.get(
            url, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        data = r.json()
        raw_data = data.get("data", {})
        if not raw_data or isinstance(raw_data, list):
            return pd.DataFrame()
        stock_data = raw_data.get(full_symbol, {})
        if not stock_data:
            return pd.DataFrame()
        klines = stock_data.get(
            "qfqday" if adjust else "day", []
        )
    except Exception:
        return pd.DataFrame()

    if not klines:
        return pd.DataFrame()

    records = []
    for k in klines:
        # [date, open, close, high, low, volume, {}, change%, amount, '']
        try:
            row = {
                "date": k[0],
                "open": float(k[1]) / 100,
                "close": float(k[2]) / 100,
                "high": float(k[3]) / 100,
                "low": float(k[4]) / 100,
                "volume": float(k[5]),  # already in lots (手)
                "pct_change": float(k[7]) if len(k) > 7 else 0,
                "money": float(k[8]) * 1000 if len(k) > 8 else 0,  # ×1000 → yuan
                "price_change": 0,
                "turnover": 0,
            }
            records.append(row)
        except (ValueError, IndexError):
            continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    # Reorder columns to match standard format
    cols = ["open", "high", "low", "close", "volume", "money", "pct_change", "price_change", "turnover"]
    df = df[[c for c in cols if c in df.columns]]
    return df


def _fetch_from_sina(symbol: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    """Source 3: Sina Finance via akshare stock_zh_a_daily().

    Prices are ×100 (e.g., 1595.36 = ¥15.9536). Volume is in shares (股), needs ÷100 → lots.
    """
    prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
    full_symbol = f"{prefix}{symbol}"
    adj_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
    try:
        df = ak.stock_zh_a_daily(
            symbol=full_symbol, start_date=start_date, end_date=end_date,
            adjust=adj_map.get(adjust, ""),
        )
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Normalize: ÷100 for prices, ÷100 for volume (shares → lots)
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col] / 100
    if "volume" in df.columns:
        df["volume"] = df["volume"] / 100

    # Rename to standard format
    df = _rename_cols(df, {
        "date": "date", "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume", "amount": "money",
    })

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    # Add missing standard columns
    for col in ["pct_change", "price_change", "turnover"]:
        if col not in df.columns:
            df[col] = 0

    cols = ["open", "high", "low", "close", "volume", "money", "pct_change", "price_change", "turnover"]
    df = df[[c for c in cols if c in df.columns]]
    return df


def _fetch_from_baostock(symbol: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    """Source 4: BaoStock (optional dependency, pip install baostock).

    Uses its own socket protocol, works independently of EastMoney.
    adjust: qfq→2, hfq→1, ""→3 (no adjust)
    """
    try:
        import baostock as bs
    except ImportError:
        return pd.DataFrame()

    prefix = "sh." if symbol.startswith(("6", "9")) else "sz."
    full_symbol = f"{prefix}{symbol}"
    adjust_flag = {"qfq": "2", "hfq": "1", "": "3"}.get(adjust, "3")

    try:
        bs.login()
        rs = bs.query_history_k_data_plus(
            full_symbol,
            "date,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start_date, end_date=end_date,
            frequency="daily", adjustflag=adjust_flag,
        )
        if rs.error_code != "0":
            bs.logout()
            return pd.DataFrame()

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
    except Exception:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=rs.fields)
    numeric_cols = ["open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # BaoStock volume is in 股, convert to 手
    if "volume" in df.columns:
        df["volume"] = df["volume"] / 100
    # amount is already in 元

    df = _rename_cols(df, {
        "date": "date", "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume", "amount": "money",
        "pctChg": "pct_change", "turn": "turnover",
    })

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    if "price_change" not in df.columns:
        df["price_change"] = 0

    cols = ["open", "high", "low", "close", "volume", "money", "pct_change", "price_change", "turnover"]
    df = df[[c for c in cols if c in df.columns]]
    return df


# Data source priority chain — tried in order until one succeeds.
_DATA_FETCHERS = [
    ("eastmoney", _fetch_from_em),
    ("tencent", _fetch_from_tencent),
    ("sina", _fetch_from_sina),
    ("baostock", _fetch_from_baostock),
]


def fetch_stock_data(code: str, start_date, end_date, adjust: str = "qfq") -> pd.DataFrame:
    """Fetch daily OHLCV data from multiple sources with automatic fallback.

    Tries data sources in priority order: EastMoney → Tencent → Sina → BaoStock.
    Returns data from the first source that succeeds.
    """
    symbol = _code_to_akshare(code)
    is_idx = _is_index(code)

    # Indices: canonical cache key excludes date range
    if is_idx:
        cache_key = (symbol, "index", adjust)
    else:
        cache_key = (symbol, str(start_date), str(end_date), adjust)

    if cache_key in _cache:
        with _cache_lock:
            df_cached = _cache.get(cache_key)
        if df_cached is not None:
            if is_idx and start_date and end_date:
                return _slice_by_date(df_cached, start_date, end_date)
            return df_cached

    start_str = _normalize_date(start_date)
    end_str = _normalize_date(end_date)

    # Index data: try EastMoney, Sina, then csindex
    if is_idx:
        prefix = "sh" if ".XSHG" in code else "sz"
        try:
            df = ak.stock_zh_index_daily_em(symbol=f"{prefix}{symbol}")
        except Exception:
            try:
                df = ak.stock_zh_index_daily(symbol=f"{prefix}{symbol}")
            except Exception:
                df = pd.DataFrame()

        if not df.empty:
            with _cache_lock:
                _cache[cache_key] = df
            return _slice_by_date(df, start_date, end_date) if start_date and end_date else df

        # Try csindex
        try:
            df = ak.stock_zh_index_hist_csindex(
                symbol=symbol, start_date=start_str, end_date=end_str,
            )
            if not df.empty:
                df = _rename_cols(df, {
                    "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                    "收盘": "close", "成交量": "volume", "成交金额": "money",
                    "涨跌幅": "pct_change",
                })
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                for col in ["price_change", "turnover"]:
                    if col not in df.columns:
                        df[col] = 0
                cols = ["open", "high", "low", "close", "volume", "money", "pct_change", "price_change", "turnover"]
                df = df[[c for c in cols if c in df.columns]]
                with _cache_lock:
                    _cache[cache_key] = df
                return _slice_by_date(df, start_date, end_date)
        except Exception:
            pass

        return pd.DataFrame()

    # ETF/Stock: try each source in priority order
    for source_name, fetcher in _DATA_FETCHERS:
        try:
            if source_name == "baostock":
                df = fetcher(symbol, start_str, end_str, adjust)
            elif source_name == "tencent":
                df = fetcher(symbol, start_str, end_str, adjust)
            elif source_name == "sina":
                df = fetcher(symbol, start_str, end_str, adjust)
            elif source_name == "eastmoney":
                if _is_etf(symbol):
                    df = ak.fund_etf_hist_em(
                        symbol=symbol, period="daily",
                        start_date=start_str, end_date=end_str, adjust=adjust,
                    )
                else:
                    df = ak.stock_zh_a_hist(
                        symbol=symbol, period="daily",
                        start_date=start_str, end_date=end_str, adjust=adjust,
                    )
            else:
                df = pd.DataFrame()

            if not df.empty:
                if source_name == "eastmoney":
                    df = _rename_cols(df, {
                        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                        "收盘": "close", "成交量": "volume", "成交额": "money",
                        "涨跌幅": "pct_change", "涨跌额": "price_change", "换手率": "turnover",
                    })
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df.set_index("date", inplace=True)

                with _cache_lock:
                    _cache[cache_key] = df
                return df
        except Exception:
            continue

    # MED-32: bare 000xxx codes may actually be Shanghai indices.
    # If stock lookup fails, auto-retry as index with .XSHG suffix.
    if ".XSHG" not in code and ".XSHE" not in code and symbol.startswith("000"):
        idx_code = f"{symbol}.XSHG"
        return fetch_stock_data(idx_code, start_date, end_date, adjust)

    return pd.DataFrame()


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
        start_date = datetime.datetime.combine(lookback, datetime.time())
        start_date = _compute_lookback(count, start_date)

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
    start_date = _compute_lookback(count, end_date)

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
    """Get historical attribute data for a single security.

    Parameters:
        security: stock code (with or without exchange suffix)
        count: number of bars to return
        unit: bar size — only '1d' (daily) is currently supported
        fields: tuple of field names to fetch (default ``('close',)``)
        df: if True return a DataFrame, else a Series / dict
        skip_paused: reserved for future use
        fq: adjustment mode.  In backtest mode (preloaded panel), only
            ``'pre'`` (前复权 / qfq) and ``None`` (no adjustment) are supported
            because the preloaded data is always stored with ``adjust='qfq'``.
            Requesting ``'post'`` in backtest mode will raise a
            ``ValueError`` to prevent silent incorrect data.  In live
            mode all three modes are supported via the fallback path.

    Returns:
        DataFrame with columns for each requested field, indexed by date.
    """
    from eqlib._state import _context
    from eqlib.engine import _get_preloaded

    # Fast path: use prebuilt Series dicts from PreloadedData
    preloaded = _get_preloaded()
    if preloaded is not None and preloaded._field_series:
        sec_data = preloaded._field_series.get(security)
        if sec_data is not None:
            if fq not in ("pre", None):
                raise ValueError(
                    f"attribute_history: fq='{fq}' is not supported in backtest mode. "
                    "The preloaded OHLCV panel is stored with adjust='qfq' (前复权). "
                    "Use fq='pre' (the default), or switch to the network fallback by "
                    "not preloading data."
                )
            available = [f for f in fields if f in sec_data]
            if not available:
                return pd.DataFrame()
            current = _context.current_dt
            if current is not None:
                ts = pd.Timestamp(current)
                # Strict less-than: exclude any bar on the current day to prevent
                # look-ahead bias (e.g., getting today's close in a 09:30 callback).
                cutoff = ts.normalize()  # midnight of the current day
                result = pd.DataFrame(
                    {f: sec_data[f][sec_data[f].index < cutoff] for f in available}
                )
            else:
                result = pd.DataFrame(
                    {f: sec_data[f] for f in available}
                )
            return result.tail(count)

    # Fallback: slice from preloaded panel (legacy path)
    if preloaded is not None and preloaded.panel is not None:
        sec_df = preloaded.panel.get(security)
        if sec_df is not None and not sec_df.empty:
            if fq not in ("pre", None):
                raise ValueError(
                    f"attribute_history: fq='{fq}' is not supported in backtest mode. "
                    "The preloaded panel is stored with adjust='qfq'. Use fq='pre'."
                )
            available = [f for f in fields if f in sec_df.columns]
            if not available:
                return pd.DataFrame()
            # Filter to bars strictly before the current day (avoid look-ahead).
            current = _context.current_dt
            if current is not None:
                cutoff = pd.Timestamp(current).normalize()
                sec_df = sec_df[sec_df.index < cutoff]
            result = sec_df[available].tail(count)
            return result

    # Fallback: fetch from disk/network
    end_date = _context.current_dt
    start_date = _compute_lookback(count, end_date)

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

# Fixed-date Chinese public holidays that cause A-share market closure.
# These occur on the same Gregorian date every year (though observance may
# shift to adjacent weekdays; we mark the date itself).
_FIXED_HOLIDAYS = [
    (1, 1),   # New Year's Day
    (5, 1),   # Labor Day
    (5, 2),   # Labor Day extended
    (5, 3),   # Labor Day extended
    (10, 1),  # National Day
    (10, 2),  # National Day extended
    (10, 3),  # National Day extended
]


def _is_ashare_holiday(date: datetime.date) -> bool:
    """Return True if *date* is a known A-share non-trading day.

    Checks in order:
    1. ``chinese_calendar.is_workday()`` — accurate for 2004-2026,
       including make-up workdays on weekends.
    2. Hardcoded holiday set (covers 2020-2028).
    3. Fixed-date holiday rules (New Year, Labor Day, National Day) —
       catches basic holidays for any year beyond 2028.
    """
    # Tier 1: chinese_calendar (primary, covers 2004-2026)
    if _CC_AVAILABLE:
        try:
            return not _cc.is_workday(date)
        except NotImplementedError:
            pass  # Year out of range — fall through

    # Tier 2: hardcoded holiday set (2020-2028)
    if date in _ASHARE_HOLIDAYS:
        return True

    # Tier 3: fixed-date holidays for any year
    return (date.month, date.day) in _FIXED_HOLIDAYS


def _iter_days(start, end):
    """Iterate days between start and end inclusive."""
    current = start
    while current <= end:
        yield current
        current += datetime.timedelta(days=1)


# MED-23: wrap to normalize date/datetime/Timestamp inputs to string before cache lookup
@lru_cache(maxsize=64)
def _get_trading_days_range_raw(start_str: str, end_str: str) -> tuple:
    """Return trading days between start and end using local holiday fallback."""
    start_date = pd.Timestamp(start_str).date()
    end_date = pd.Timestamp(end_str).date()
    return tuple(
        d for d in _iter_days(start_date, end_date)
        if d.weekday() < 5 and not _is_ashare_holiday(d)
    )


# MED-23: wrap to normalize date/datetime/Timestamp inputs to string before cache lookup
@lru_cache(maxsize=64)
def _get_trading_days_range(
    start: Union[datetime.date, datetime.datetime, pd.Timestamp],
    end: Union[datetime.date, datetime.datetime, pd.Timestamp],
) -> tuple:
    """Return trading days between start and end using local holiday fallback."""
    s = pd.Timestamp(start).date().isoformat()
    e = pd.Timestamp(end).date().isoformat()
    return _get_trading_days_range_raw(s, e)


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

    mask = pd.Series(True, index=df.index)
    for col, constraint in filters.items():
        if col not in df.columns:
            continue
        if isinstance(constraint, tuple):
            lo, hi = constraint
            if lo is not None:
                mask &= df[col] >= lo
            if hi is not None:
                mask &= df[col] <= hi
        else:
            mask &= df[col] >= constraint

    df = df[mask]
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
