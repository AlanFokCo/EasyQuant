"""Point-in-time daily history for historical ML feature rows."""

import pandas as pd

from eqlib._state import get_session


def market_timestamp(value) -> pd.Timestamp:
    """Normalize an instant to the library's naive Shanghai market time."""
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("ML sample timestamps must not be missing")
    if result.tzinfo is not None:
        result = result.tz_convert("Asia/Shanghai").tz_localize(None)
    return result


def history_at(fetch_history, security, count, context, fields):
    """Slice before the requested day without rewinding the live session.

    The source is daily history at the active session time. Calendar days
    bound the extra number of daily bars needed to reach an earlier sample.
    Both the sample context and the actual session impose visibility limits.
    """
    as_of = market_timestamp(context.current_dt).normalize()
    active = getattr(get_session()._context, "current_dt", None)
    extra = 0
    if active is not None:
        active_day = market_timestamp(active).normalize()
        extra = max(0, (active_day - as_of).days)
        as_of = min(as_of, active_day)
    history = fetch_history(security, count + extra, "1d", fields=fields)
    if history is None or history.empty:
        return history
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("ML history requires a DatetimeIndex")
    index = history.index
    if index.tz is not None:
        index = index.tz_convert("Asia/Shanghai").tz_localize(None)
    return history.loc[index < as_of].tail(count)
