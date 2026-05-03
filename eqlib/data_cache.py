"""Preloaded data cache for fast backtest execution.

Provides:
- In-memory DataFrame with all prices for the backtest period
- Disk-based parquet cache to avoid redundant network fetches
- O(1) lookup by (date, security)
- Local CSV data store for explicit offline backtesting
"""

import os
import hashlib
import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Disk cache directory (relative to project root or configurable)
_CACHE_DIR = os.environ.get("EQLIB_CACHE_DIR", None)

# Local data directory for user-managed CSV files
_LOCAL_DATA_DIR = os.environ.get("EQLIB_LOCAL_DATA_DIR", None)


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


def _cache_path(security: str, start: str, end: str, adjust: str) -> Path:
    """Generate a deterministic cache file path for a security+date range."""
    key = f"{security}_{start}_{end}_{adjust}"
    hash_ = hashlib.md5(key.encode()).hexdigest()[:12]
    return _get_cache_dir() / f"{hash_}.parquet"


def _load_from_disk(security: str, start: str, end: str, adjust: str) -> Optional[pd.DataFrame]:
    """Try to load cached data from parquet."""
    try:
        path = _cache_path(security, start, end, adjust)
        if path.exists():
            df = pd.read_parquet(path)
            if not df.empty:
                return df
    except Exception:
        pass
    return None


def _save_to_disk(df: pd.DataFrame, security: str, start: str, end: str, adjust: str):
    """Save data to parquet cache."""
    try:
        path = _cache_path(security, start, end, adjust)
        df.to_parquet(path, engine="pyarrow" if _has_pyarrow() else "fastparquet")
    except Exception:
        pass


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
        _save_to_disk(df, security, start_str, end_str, adjust)

    return df


# ============================================================
# Preloaded data store for backtest
# ============================================================

class PreloadedData:
    """
    Holds all price data for a backtest period in memory.

    Stores a single DataFrame with MultiIndex (date, security)
    for O(1) lookup. All data is fetched upfront before the
    backtest loop starts.

    Attributes:
        panel: DataFrame with columns (open, high, low, close, volume, money)
               indexed by MultiIndex (date, security).
    """

    def __init__(self):
        self.panel: Optional[pd.DataFrame] = None
        self._close_matrix: Optional[pd.DataFrame] = None
        self._securities: list = []
        self._dates: pd.DatetimeIndex = pd.DatetimeIndex([])

    def load(
        self,
        securities: list[str],
        start_date,
        end_date,
        adjust: str = "qfq",
        progress: bool = True,
        use_local: bool = False,
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
        """
        start_str = str(start_date).replace("-", "")[:10]
        end_str = str(end_date).replace("-", "")[:10]

        frames = {}
        total = len(securities)
        for i, sec in enumerate(securities):
            if progress and total > 5:
                pct = (i + 1) / total * 100
                print(f"\r  Loading data: {i+1}/{total} ({pct:.0f}%)", end="", flush=True)

            df = None
            if use_local:
                # Try local CSV first
                df = load_stock_local(sec, start_str, end_str, adjust)
                if df is not None:
                    frames[sec] = df
                    continue

                # Not found locally — download and save
                from eqlib.data import fetch_stock_data
                df = fetch_stock_data(sec, start_date, end_date, adjust)
                if not df.empty:
                    _save_to_disk(df, sec, start_str, end_str, adjust)
                    # Also save to local CSV
                    save_stock_local(sec, start_date, end_date, adjust)
            else:
                # Use existing parquet cache logic
                df = _load_from_disk(sec, start_str, end_str, adjust)
                if df is None:
                    from eqlib.data import fetch_stock_data
                    df = fetch_stock_data(sec, start_date, end_date, adjust)
                    if not df.empty:
                        _save_to_disk(df, sec, start_str, end_str, adjust)

            if df is not None and not df.empty:
                # Ensure datetime index
                if not isinstance(df.index, pd.DatetimeIndex):
                    try:
                        df.index = pd.to_datetime(df.index)
                    except Exception:
                        continue
                frames[sec] = df

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

        # Build close price matrix for fast lookup
        close_frames = {}
        for sec, df in frames.items():
            if "close" in df.columns:
                close_frames[sec] = df["close"]
        if close_frames:
            self._close_matrix = pd.DataFrame(close_frames)
            self._close_matrix.sort_index(inplace=True)

        self._securities = sorted(frames.keys())
        self._dates = self.panel.index

    def get_close(self, date, security) -> Optional[float]:
        """Get closing price for a given date and security."""
        if self._close_matrix is None:
            return None
        try:
            date_key = pd.Timestamp(date)
            if date_key in self._close_matrix.index and security in self._close_matrix.columns:
                val = self._close_matrix.at[date_key, security]
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
        """Get full OHLCV bar for a given date and security."""
        if self.panel is None or self.panel.empty:
            return None
        try:
            date_key = pd.Timestamp(date)
            if date_key not in self.panel.index:
                return None
            row = self.panel.loc[date_key]
            if security not in row.columns.get_level_values(0):
                return None
            bar = {}
            for field in ["open", "high", "low", "close", "volume", "money"]:
                try:
                    val = row[(security, field)]
                    if pd.notna(val):
                        bar[field] = float(val)
                except KeyError:
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
        self._securities = []
        self._dates = pd.DatetimeIndex([])


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
