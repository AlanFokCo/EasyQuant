"""Preloaded data cache for fast backtest execution.

Provides:
- In-memory DataFrame with all prices for the backtest period
- Disk-based parquet cache to avoid redundant network fetches
- O(1) lookup by (date, security) via pure Python dicts (when memory allows)
- Local CSV data store for explicit offline backtesting
- Configurable memory limit with automatic fallback to compact storage
"""

import os
import hashlib
import datetime
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

# Disk cache directory (relative to project root or configurable)
_CACHE_DIR = os.environ.get("EQLIB_CACHE_DIR", None)

# Local data directory for user-managed CSV files
_LOCAL_DATA_DIR = os.environ.get("EQLIB_LOCAL_DATA_DIR", None)

# Default memory limit for preload (1 GB in MB)
_DEFAULT_MAX_MEMORY_MB = 1024

# Per-file locks to ensure thread-safe read-merge-write in _save_to_disk
_file_locks: dict = {}
_file_locks_lock = threading.Lock()


def _get_file_lock(path: Path) -> threading.Lock:
    """Return (creating if needed) the threading.Lock for a given cache file."""
    key = str(path)
    with _file_locks_lock:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


def _slice_by_date(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Return rows of *df* whose DatetimeIndex falls in [start, end].

    Shared by ``data.py`` and ``data_cache.py`` to avoid duplicating the
    filtering logic in each caller.
    """
    if df.empty:
        return df
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return df.loc[(df.index >= start_ts) & (df.index <= end_ts)]


def _get_cache_dir() -> Path:
    """Get or create the cache directory."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        base = Path(__file__).parent.parent / ".eqlib_cache"
        _CACHE_DIR = str(base)
    cache_dir = Path(_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def set_cache_dir(path: str):
    """Configure the disk cache directory."""
    global _CACHE_DIR
    _CACHE_DIR = path


def _cache_path(security: str, adjust: str) -> Path:
    """Generate a deterministic cache file path for a security.

    The key uses only ``security`` and ``adjust`` — *not* a date range — so
    that all requests for the same security reuse the same file regardless of
    the requested date window.  The stored frame always covers the full
    available history; callers slice to the dates they need after loading.
    """
    key = f"{security}_{adjust}"
    hash_ = hashlib.md5(key.encode()).hexdigest()[:12]
    return _get_cache_dir() / f"{hash_}.parquet"


def _load_from_disk(security: str, start: str, end: str, adjust: str) -> Optional[pd.DataFrame]:
    """Try to load cached data from parquet and slice to [start, end]."""
    try:
        path = _cache_path(security, adjust)
        if path.exists():
            df = pd.read_parquet(path)
            if df.empty:
                return None
            sliced = _slice_by_date(df, start, end)
            return sliced if not sliced.empty else None
    except Exception:
        pass
    return None


def _save_to_disk(df: pd.DataFrame, security: str, adjust: str):
    """Save data to parquet cache, merging with any existing cached frame.

    When the cache file already exists the new data is merged with the stored
    frame (union of dates, new values overwrite old ones) so the file always
    holds the most complete history available.

    Thread-safe: a per-file lock prevents concurrent read-merge-write races
    from corrupting the cache file.
    """
    from eqlib.logger import log as _log
    try:
        path = _cache_path(security, adjust)
        with _get_file_lock(path):
            if path.exists():
                existing = pd.read_parquet(path)
                if not existing.empty:
                    df = pd.concat([existing, df])
                    df = df[~df.index.duplicated(keep='last')].sort_index()
            df.to_parquet(path, engine="pyarrow" if _has_pyarrow() else "fastparquet")
    except Exception as e:
        _log.warning(f"Failed to save cache for {security}: {e}")


@lru_cache(maxsize=None)
def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_cached(security: str, start_date, end_date, adjust: str = "qfq") -> pd.DataFrame:
    """
    Fetch stock data: first try disk cache, then network.
    Falls back to the original fetch_stock_data if cache miss.

    Parameters:
        security: stock code
        start_date: start date
        end_date: end date
        adjust: adjust type

    Returns:
        DataFrame with OHLCV data
    """
    from eqlib.data import fetch_stock_data

    start_str = str(start_date).replace("-", "")[:10]
    end_str = str(end_date).replace("-", "")[:10]

    cached = _load_from_disk(security, start_str, end_str, adjust)
    if cached is not None:
        return cached

    df = fetch_stock_data(security, start_date, end_date, adjust)
    if not df.empty:
        _save_to_disk(df, security, adjust)

    return df


# ============================================================
# Preloaded data store for backtest
# ============================================================

# Memory estimation constants
_BYTES_PER_FLOAT = 8
_NUM_OHLCV_FIELDS = 9          # open, high, low, close, volume, money, pct_change, price_change, turnover
_PANDAS_OVERHEAD = 1.5         # DataFrame overhead multiplier (~50%)
_BAR_DICT_OVERHEAD = 500       # bytes per row for Python dict + 6 float objects
_CLOSE_DICT_OVERHEAD = 250     # bytes per row for Python dict entry {date: price}


def estimate_memory_mb(securities: list, rows_per_sec: int) -> dict:
    """Estimate memory usage for preloading data.

    Parameters:
        securities: list of stock codes
        rows_per_sec: number of trading days per security

    Returns:
        dict with estimated memory breakdown in MB:
            panel_mb: DataFrame with all data
            close_dict_mb: O(1) close price lookup dicts
            bar_cache_mb: O(1) full bar lookup dicts
            total_mb: sum of all above
    """
    n_sec = len(securities)
    n_rows = rows_per_sec

    # Panel: numpy array + MultiIndex
    panel_mb = (n_sec * n_rows * _NUM_OHLCV_FIELDS * _BYTES_PER_FLOAT * _PANDAS_OVERHEAD) / (1024 * 1024)

    # Dict caches: Python objects are much larger than numpy arrays
    bar_cache_mb = (n_sec * n_rows * _BAR_DICT_OVERHEAD) / (1024 * 1024)
    close_dict_mb = (n_sec * n_rows * _CLOSE_DICT_OVERHEAD) / (1024 * 1024)

    return {
        "panel_mb": round(panel_mb, 1),
        "close_dict_mb": round(close_dict_mb, 1),
        "bar_cache_mb": round(bar_cache_mb, 1),
        "total_mb": round(panel_mb + close_dict_mb + bar_cache_mb, 1),
        "securities": n_sec,
        "rows_per_sec": n_rows,
    }


class PreloadedData:
    """
    Holds all price data for a backtest period in memory.

    Memory management:
    - Always stores the panel DataFrame (compact, numpy-backed).
    - Builds dict caches (close_dict, bar_cache) only if within memory limit.
    - Falls back to panel slicing when dict caches are not built.

    Attributes:
        panel: DataFrame with MultiIndex columns (security, field).
        _close_matrix: DataFrame (date × security) for close prices.
        _close_dict: {security: {date: price}} — only if memory allows.
        _bar_cache: {security: {date: bar_dict}} — only if memory allows.
        _use_panel_fallback: if True, dict caches were not built due to memory limit.
    """

    def __init__(self):
        self.panel: Optional[pd.DataFrame] = None
        self._close_matrix: Optional[pd.DataFrame] = None
        self._close_dict: dict = {}
        self._bar_cache: dict = {}
        self._securities: list = []
        self._dates: pd.DatetimeIndex = pd.DatetimeIndex([])
        self._use_panel_fallback: bool = False  # True when dicts were skipped
        # Pre-built {security: {field: pd.Series}} for fast attribute_history
        self._field_series: dict = {}
        # Precomputed indicators: {security: pd.DataFrame} with columns:
        # rsi, bb_upper, bb_mid, bb_lower, macd_dif, macd_dea, macd_hist,
        # atr, dc_upper, dc_mid, dc_lower
        self._indicators: dict = {}

    def load(
        self,
        securities: list[str],
        start_date,
        end_date,
        adjust: str = "qfq",
        progress: bool = True,
        use_local: bool = False,
        max_memory_mb: int = _DEFAULT_MAX_MEMORY_MB,
    ):
        """
        Preload daily OHLCV data for all securities over the date range.

        Parameters:
            securities: list of stock codes
            start_date: backtest start date
            end_date: backtest end date
            adjust: adjust type
            progress: show progress indicator
            use_local: if True, load from local CSV files first;
                       download and save if local file not found.
            max_memory_mb: memory limit in MB (default 1024). If estimated
                           memory exceeds this, dict caches are skipped and
                           the system falls back to panel slicing.
        """
        start_str = str(start_date).replace("-", "")[:10]
        end_str = str(end_date).replace("-", "")[:10]

        # --- Parallel loading using ThreadPoolExecutor ---
        import concurrent.futures
        frames: dict = {}
        total = len(securities)

        def _load_one(sec: str) -> tuple:
            df = None
            if use_local:
                df = load_stock_local(sec, start_str, end_str, adjust)
                if df is not None:
                    return (sec, df)
                from eqlib.data import fetch_stock_data
                df = fetch_stock_data(sec, start_date, end_date, adjust)
                if not df.empty:
                    _save_to_disk(df, sec, adjust)
                    save_stock_local(sec, start_date, end_date, adjust)
            else:
                df = _load_from_disk(sec, start_str, end_str, adjust)
                if df is None:
                    from eqlib.data import fetch_stock_data
                    df = fetch_stock_data(sec, start_date, end_date, adjust)
                    if not df.empty:
                        _save_to_disk(df, sec, adjust)
            return (sec, df)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(8, total)
        ) as pool:
            future_to_sec = {pool.submit(_load_one, sec): sec for sec in securities}
            done_count = 0
            for future in concurrent.futures.as_completed(future_to_sec):
                sec, df = future.result()
                if df is not None and not df.empty:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        try:
                            df.index = pd.to_datetime(df.index)
                        except Exception:
                            continue
                    frames[sec] = df
                done_count += 1
                if progress and total > 5:
                    pct = done_count / total * 100
                    print(f"\r  Loading data: {done_count}/{total} ({pct:.0f}%)", end="", flush=True)

        if progress and total > 5:
            print()  # newline after progress

        if not frames:
            self.panel = pd.DataFrame()
            return

        # Build panel: columns = MultiIndex (security, field)
        self.panel = pd.concat(frames, axis=1)
        self.panel.columns = pd.MultiIndex.from_tuples(
            [(sec, col) for sec in frames for col in frames[sec].columns],
            names=["security", "field"],
        )

        # --- Memory-aware: decide whether to build dict caches ---
        n_sec = len(frames)
        n_rows = len(next(iter(frames.values())))
        mem = estimate_memory_mb(list(frames.keys()), n_rows)

        can_build_dicts = mem["total_mb"] <= max_memory_mb
        self._use_panel_fallback = not can_build_dicts

        if progress and total > 5:
            if can_build_dicts:
                print(f"  Memory estimate: {mem['total_mb']} MB (within {max_memory_mb} MB limit, using dict caches)")
            else:
                print(f"  Memory estimate: {mem['total_mb']} MB (exceeds {max_memory_mb} MB limit, using panel fallback)")

        if can_build_dicts:
            # Build fast-lookup dicts (O(1) Python dict lookups)
            close_frames = {}
            for sec, df in frames.items():
                if "close" in df.columns:
                    close_frames[sec] = df["close"]
                    self._close_dict[sec] = dict(zip(df.index, df["close"]))

                fields = ["open", "high", "low", "close", "volume", "money"]
                self._bar_cache[sec] = df.reindex(columns=fields, fill_value=0).to_dict("index")

            if close_frames:
                self._close_matrix = pd.DataFrame(close_frames)
                self._close_matrix.sort_index(inplace=True)
        else:
            # Memory-limited: only build close_matrix (compact DataFrame)
            # No dict caches — get_close/get_bar will use panel slicing
            close_frames = {}
            for sec, df in frames.items():
                if "close" in df.columns:
                    close_frames[sec] = df["close"]
            if close_frames:
                self._close_matrix = pd.DataFrame(close_frames)
                self._close_matrix.sort_index(inplace=True)

        self._securities = sorted(frames.keys())
        self._dates = self.panel.index

        # Build {security: {field: pd.Series}} for fast attribute_history
        fields = ["open", "high", "low", "close", "volume", "money",
                   "pct_change", "price_change", "turnover"]
        for sec, df in frames.items():
            self._field_series[sec] = {}
            for f in fields:
                if f in df.columns:
                    self._field_series[sec][f] = df[f]

        # Precompute all technical indicators once per stock
        self._compute_indicators(frames)

    def _compute_indicators(self, frames: dict):
        """Precompute technical indicators for all securities at once.

        Called automatically at the end of load().  Computes RSI, MACD,
        Bollinger Bands, ATR, and Donchian Channel for each stock's full
        price history in a single pass, storing the results in
        ``self._indicators[security]`` as a DataFrame.
        """
        from eqlib.utils.indicators import compute_all_indicators

        for sec, df in frames.items():
            if not all(f in df.columns for f in ["close", "high", "low"]):
                continue
            try:
                ind_df = compute_all_indicators(
                    close=df["close"], high=df["high"], low=df["low"],
                    volume=df.get("volume", pd.Series()),
                )
                self._indicators[sec] = ind_df
            except Exception:
                pass

    def get_indicators(self, security, count, current_dt):
        """Get precomputed indicators for a security up to current_dt.

        Returns a DataFrame with indicator columns, limited to *count* rows
        ending at or before *current_dt*.  If precomputed indicators are not
        available, returns None.
        """
        ind_df = self._indicators.get(security)
        if ind_df is None:
            return None

        if current_dt is not None:
            ts = pd.Timestamp(current_dt)
            result = ind_df.loc[:ts]
        else:
            result = ind_df

        return result.tail(count)

    def get_history(self, security, count, fields, current_dt):
        """Fast attribute_history from preloaded data.

        Returns a DataFrame with the requested fields and up to *count* rows
        ending at or before *current_dt*.  Uses pre-built Series dicts to avoid
        repeated DataFrame slicing.

        Parameters:
            security: stock code
            count: number of bars to return
            fields: list of field names
            current_dt: datetime (may be None, in which case no date filter)
        """
        sec_data = self._field_series.get(security)
        if sec_data is None:
            return None

        available = [f for f in fields if f in sec_data]
        if not available:
            return pd.DataFrame()

        if current_dt is not None:
            ts = pd.Timestamp(current_dt)
            result = pd.DataFrame(
                {f: sec_data[f].loc[:ts] for f in available}
            )
        else:
            result = pd.DataFrame(
                {f: sec_data[f] for f in available}
            )
        return result.tail(count)

    def get_close(self, date, security) -> Optional[float]:
        """Get closing price for a given date and security."""
        # Fast path: dict cache
        if self._close_dict:
            sec_dict = self._close_dict.get(security)
            if sec_dict is not None:
                try:
                    val = sec_dict.get(date)
                    if val is not None and val == val:
                        return float(val)
                except Exception:
                    pass
                try:
                    ts = pd.Timestamp(date)
                    val = sec_dict.get(ts)
                    if val is not None and val == val:
                        return float(val)
                except Exception:
                    pass

        # Fallback: panel slicing
        if self._close_matrix is not None:
            try:
                ts = pd.Timestamp(date)
                if ts in self._close_matrix.index and security in self._close_matrix.columns:
                    val = self._close_matrix.at[ts, security]
                    if pd.notna(val):
                        return float(val)
            except Exception:
                pass
        return None

    def get_close_series(self, security) -> Optional[pd.Series]:
        """Get full close price series for a security."""
        if self._close_matrix is None or security not in self._close_matrix.columns:
            return None
        return self._close_matrix[security].dropna()

    def get_bar(self, date, security) -> Optional[dict]:
        """Get full OHLCV bar for a given date and security.

        Returns a copy of the cached bar dict so that callers cannot mutate
        the shared cache.
        """
        # Fast path: dict cache
        if self._bar_cache:
            sec_dict = self._bar_cache.get(security)
            if sec_dict is not None:
                bar = sec_dict.get(date)
                if bar is not None:
                    return dict(bar)
                try:
                    ts = pd.Timestamp(date)
                    bar = sec_dict.get(ts)
                    if bar is not None:
                        return dict(bar)
                except Exception:
                    pass

        # Fallback: panel slicing
        if self.panel is not None:
            try:
                ts = pd.Timestamp(date)
                if ts in self.panel.index:
                    bar = {}
                    for field in ["open", "high", "low", "close", "volume", "money"]:
                        try:
                            val = self.panel.loc[ts, (security, field)]
                            if pd.notna(val):
                                bar[field] = float(val)
                        except (KeyError, TypeError):
                            pass
                    return bar if bar else None
            except Exception:
                pass
        return None

    def get_returns_matrix(self) -> Optional[pd.DataFrame]:
        """Get daily returns matrix (columns = securities, index = date)."""
        if self._close_matrix is None:
            return None
        return self._close_matrix.pct_change().dropna()

    @property
    def securities(self) -> list:
        return list(self._securities)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self._dates

    def clear(self):
        """Free memory."""
        self.panel = None
        self._close_matrix = None
        self._close_dict = {}
        self._bar_cache = {}
        self._securities = []
        self._dates = pd.DatetimeIndex([])
        self._use_panel_fallback = False
        self._field_series = {}
        self._indicators = {}


# ============================================================
# Local CSV data store — user-managed, visible, editable
# ============================================================

def _get_local_data_dir() -> Path:
    """Get or create the local data directory."""
    global _LOCAL_DATA_DIR
    if _LOCAL_DATA_DIR is None:
        base = Path(__file__).parent.parent / "data"
        _LOCAL_DATA_DIR = str(base)
    data_dir = Path(_LOCAL_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def set_local_data_dir(path: str):
    """Configure the local data directory for CSV files."""
    global _LOCAL_DATA_DIR
    _LOCAL_DATA_DIR = path


def _local_csv_path(security: str, adjust: str = "qfq") -> Path:
    """Generate a local CSV file path for a security."""
    code = security.replace(".XSHG", "").replace(".XSHE", "")
    return _get_local_data_dir() / f"{code}_daily_{adjust}.csv"


def save_stock_local(security: str, start_date=None, end_date=None,
                     adjust: str = "qfq") -> Optional[str]:
    """Download stock data and save to local CSV.

    If start_date/end_date are None, downloads full history.
    If the file already exists, appends/overwrites with new data.

    Parameters:
        security: stock code
        start_date: optional start date
        end_date: optional end date
        adjust: adjust type ('qfq', 'hfq', '')

    Returns:
        CSV file path, or None on failure.
    """
    from eqlib.data import fetch_stock_data

    df = fetch_stock_data(security, start_date or "20000101",
                          end_date or datetime.date.today(), adjust)
    if df.empty:
        return None

    path = _local_csv_path(security, adjust)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return str(path)


def load_stock_local(security: str, start_date, end_date,
                     adjust: str = "qfq") -> Optional[pd.DataFrame]:
    """Load stock data from local CSV.

    Parameters:
        security: stock code
        start_date: start date to filter
        end_date: end date to filter
        adjust: adjust type

    Returns:
        DataFrame filtered by date range, or None if file not found.
    """
    path = _local_csv_path(security, adjust)
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty:
            return None

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        df = df[(df.index >= start_ts) & (df.index <= end_ts)]

        if df.empty:
            return None
        return df
    except Exception:
        return None


def has_local_data(security: str, adjust: str = "qfq") -> bool:
    """Check if local CSV data exists for a security."""
    path = _local_csv_path(security, adjust)
    return path.exists()


def list_local_stocks(adjust: str = "qfq") -> list[str]:
    """List all stocks that have local CSV data."""
    data_dir = _get_local_data_dir()
    if not data_dir.exists():
        return []

    suffix = f"_daily_{adjust}.csv"
    files = [f for f in data_dir.iterdir() if f.name.endswith(suffix)]
    return [f.name.replace(suffix, "") for f in sorted(files)]


def remove_local_data(security: str, adjust: str = "qfq") -> bool:
    """Remove local CSV data for a security.

    Returns True if file was removed, False if not found.
    """
    path = _local_csv_path(security, adjust)
    if path.exists():
        path.unlink()
        return True
    return False


def clear_all_local_data(adjust: str = "qfq") -> int:
    """Remove all local CSV data files.

    Returns the number of files removed.
    """
    data_dir = _get_local_data_dir()
    if not data_dir.exists():
        return 0

    suffix = f"_daily_{adjust}.csv"
    count = 0
    for f in data_dir.iterdir():
        if f.name.endswith(suffix):
            f.unlink()
            count += 1
    return count
