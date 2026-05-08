"""PTrade/QMT adapter — run EasyQuant (eqlib) strategies on the QMT platform.

Usage in QMT strategy editor:
    from eqlib.ptrade_adapter import *

    def initialize(context):
        g.security = '601390'
        set_benchmark('000300.XSHG')
        run_daily(market_open, time='every_bar')

    def market_open(context):
        close_data = attribute_history(g.security, 5, '1d', ['close'])
        MA5 = close_data['close'].mean()
        current_price = close_data['close'][-1]
        if current_price > 1.01 * MA5:
            order_value(g.security, context.portfolio.available_cash)
        elif current_price < MA5 and context.portfolio.positions.get(g.security):
            order_target(g.security, 0)

    # Note: in QMT, the lifecycle is driven by init() / handlebar().
    # The adapter provides a run_strategy() function that bridges them.
    # In QMT strategy editor, add:
    #   from eqlib.ptrade_adapter import *
    #   ... your initialize + strategy callbacks above ...
    #   def init(ContextInfo):
    #       start(ContextInfo)   # bridges init -> initialize
    #
    #   def handlebar(ContextInfo):
    #       on_bar(ContextInfo)  # bridges handlebar -> your callbacks
"""

import datetime
import math
import pandas as pd
import numpy as np
from collections import defaultdict


# =====================================================================
# Global state
# =====================================================================

_context = None  # EQ-style Context wrapper
_initialize_func = None
_daily_funcs = []
_weekly_funcs = []
_monthly_funcs = []
_before_start_funcs = []
_after_end_funcs = []
_handle_data_func = None
_benchmark = '000300.XSHG'
_order_cost = None
_options = {}
_g = {}  # global variable dict (like eqlib's g)
_last_trade_day = None
_last_week = None
_last_month = None
_account = ''  # QMT account ID for trading


# =====================================================================
# Security code conversion
# =====================================================================

def _to_qmt_code(code):
    """Convert EasyQuant code to QMT format.

    EQ: '601390', '000300.XSHG', '000001.XSHE'
    QMT: '601390.SH', '000300.SH', '000001.SZ'
    """
    if code is None:
        return ''
    code = str(code).strip()
    if not code:
        return code

    # Already in QMT format (code.SH / code.SZ / code.BJ)
    if code.endswith(('.SH', '.SZ', '.BJ')):
        return code

    # EQ format: code.XSHG -> code.SH
    if code.endswith('.XSHG'):
        return code.replace('.XSHG', '.SH')
    if code.endswith('.XSHE'):
        return code.replace('.XSHE', '.SZ')

    # Pure numeric code: determine exchange by prefix
    if code.startswith(('6', '9')):
        return code + '.SH'
    if code.startswith(('0', '3')):
        return code + '.SZ'
    # Default: assume SH
    return code + '.SH'


def _to_eq_code(code):
    """Convert QMT code back to EasyQuant format."""
    if code is None:
        return ''
    code = str(code).strip()
    if code.endswith('.SH'):
        return code.replace('.SH', '.XSHG')
    if code.endswith('.SZ'):
        return code.replace('.SZ', '.XSHE')
    if code.endswith('.BJ'):
        return code  # keep as-is, BJ is same in both
    return code


# =====================================================================
# Context / Portfolio / Position simulation
# =====================================================================

class Position:
    """Simulated position, mirroring eqlib.objects.Position."""

    def __init__(self, security, amount=0, avg_cost=0.0):
        self.security = security
        self.amount = amount
        self.avg_cost = avg_cost

    @property
    def total_amount(self):
        return self.amount

    @property
    def value(self):
        return self.amount * self.avg_cost


class Portfolio:
    """Simulated portfolio state.

    In QMT live mode, actual account state comes from get_trade_detail_data.
    In backtest mode, we track a simulated portfolio.
    """

    def __init__(self, starting_cash=100000.0):
        self.starting_cash = starting_cash
        self.available_cash = starting_cash
        self.total_value = starting_cash
        self.positions = {}  # eq_code -> Position
        self.returns = 0.0

    def update_from_qmt(self, ContextInfo):
        """Refresh portfolio state from QMT real account data.

        This is called on each bar to keep the simulated Context
        in sync with the actual QMT account.
        """
        if not _account:
            return

        try:
            acct_list = get_trade_detail_data(_account, 'STOCK', 'ACCOUNT')
            if acct_list and len(acct_list) > 0:
                acct = acct_list[0]
                if hasattr(acct, 'm_dAvailable'):
                    self.available_cash = float(acct.m_dAvailable)
                if hasattr(acct, 'm_dBalance'):
                    self.total_value = float(acct.m_dBalance)
                elif hasattr(acct, 'm_dDynBalance'):
                    self.total_value = float(acct.m_dDynBalance)

            pos_list = get_trade_detail_data(_account, 'STOCK', 'POSITION')
            if pos_list:
                for pos in pos_list:
                    inst_id = getattr(pos, 'm_strInstrumentID', '')
                    if not inst_id:
                        continue
                    eq_code = _to_eq_code(inst_id)
                    amount = int(getattr(pos, 'm_nVolume', 0))
                    if amount > 0:
                        avg_price = float(getattr(pos, 'm_dOpenPrice', 0))
                        self.positions[eq_code] = Position(eq_code, amount, avg_price)
                    elif eq_code in self.positions:
                        del self.positions[eq_code]

            self.returns = (self.total_value - self.starting_cash) / self.starting_cash
        except Exception:
            pass


class Context:
    """EasyQuant-style Context object backed by QMT's ContextInfo."""

    def __init__(self, qmt_context, starting_cash=100000.0):
        self._qmt = qmt_context
        self.portfolio = Portfolio(starting_cash)
        self.current_dt = None
        self.run_params = None

    @property
    def start_date(self):
        return getattr(self._qmt, 'start', '')

    @property
    def end_date(self):
        return getattr(self._qmt, 'end', '')


# =====================================================================
# User-facing API (mirrors eqlib)
# =====================================================================

def set_account(account_id):
    """Set QMT account ID for trading. Must be called in initialize()."""
    global _account
    _account = account_id


def set_benchmark(security):
    """Set benchmark security."""
    global _benchmark
    _benchmark = security


def set_order_cost(cost, type='stock'):
    """Set order cost (no-op in QMT live mode, costs set by broker)."""
    global _order_cost
    _order_cost = cost


def set_option(name, value):
    """Set strategy option."""
    _options[name] = value


def run_daily(func, time='every_bar'):
    """Schedule a function to run every trading day."""
    _daily_funcs.append((time, func))


def run_weekly(func, day_of_week=1, time='09:30'):
    """Schedule a function to run weekly.

    Parameters:
        func: callback
        day_of_week: 0=Monday, 1=Tuesday, ..., 4=Friday
        time: execution time string (used in backtest, ignored in live)
    """
    _weekly_funcs.append((day_of_week, time, func))


def run_monthly(func, day_of_month=1, time='09:30'):
    """Schedule a function to run monthly.

    Parameters:
        func: callback
        day_of_month: day of month (1-31)
        time: execution time string (used in backtest, ignored in live)
    """
    _monthly_funcs.append((day_of_month, time, func))


def before_trading_start(func):
    """Register a pre-market callback."""
    _before_start_funcs.append(func)


def after_trading_end(func):
    """Register a post-market callback."""
    _after_end_funcs.append(func)


def set_handle_data(func):
    """Set the main handle_data callback."""
    global _handle_data_func
    _handle_data_func = func


def set_universe(securities):
    """Set the stock universe."""
    global _context
    if _context is not None:
        _context._qmt.set_universe([_to_qmt_code(s) for s in securities])


def get_universe():
    """Get the stock universe."""
    global _context
    if _context is None:
        return []
    raw = _context._qmt.get_universe()
    return [_to_eq_code(s) for s in raw]


def log(msg):
    """Print log message (maps to QMT's print)."""
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


# =====================================================================
# Data APIs (map to QMT ContextInfo methods)
# =====================================================================

def attribute_history(security, count, unit='1d', fields=('close',),
                      skip_paused=True, df=True, period='1d',
                      dividend_type='front', fill_paused=True):
    """Get recent historical data as a DataFrame.

    Mirrors eqlib's attribute_history — maps to QMT's get_market_data.
    """
    global _context
    if _context is None:
        return pd.DataFrame()

    qmt_code = _to_qmt_code(security)
    ci = _context._qmt

    try:
        data = ci.get_market_data(
            list(fields), stock_code=[qmt_code],
            skip_paused=skip_paused, period=period,
            dividend_type=dividend_type, count=count
        )
        return _format_market_data(data, fields)
    except Exception:
        return pd.DataFrame()


def history(end_date, count, unit='1d', fields=('close',),
            security_list=None, skip_paused=True, df=True,
            period='1d', dividend_type='front', fill_paused=True):
    """Get historical data up to end_date.

    Maps to QMT's get_market_data with explicit time range.
    """
    global _context
    if _context is None:
        return pd.DataFrame()

    codes = security_list
    if codes is None:
        codes = get_universe()
    if not isinstance(codes, list):
        codes = [codes]

    qmt_codes = [_to_qmt_code(c) for c in codes]
    ci = _context._qmt

    try:
        data = ci.get_market_data(
            list(fields), stock_code=qmt_codes,
            skip_paused=skip_paused, period=period,
            dividend_type=dividend_type, count=count
        )
        return _format_market_data(data, fields)
    except Exception:
        return pd.DataFrame()


def get_price(security, start_date=None, end_date=None, frequency='1d',
              fields=None, skip_paused=True, count=None,
              dividend_type='front'):
    """Get price data with date range or count.

    Maps to QMT's get_market_data or get_market_data_ex.
    """
    global _context
    if _context is None:
        return pd.DataFrame()

    qmt_code = _to_qmt_code(security)
    ci = _context._qmt

    if fields is None:
        fields = ['open', 'high', 'low', 'close', 'volume', 'money']

    try:
        if count is not None:
            data = ci.get_market_data(
                fields, stock_code=[qmt_code],
                skip_paused=skip_paused, period=frequency,
                dividend_type=dividend_type, count=count
            )
        else:
            start_str = start_date.strftime('%Y%m%d') if isinstance(start_date, datetime.date) else str(start_date or '')
            end_str = end_date.strftime('%Y%m%d') if isinstance(end_date, datetime.date) else str(end_date or '')
            data = ci.get_market_data_ex(
                fields, [qmt_code], period=frequency,
                start_time=start_str, end_time=end_str,
                dividend_type=dividend_type
            )
        if isinstance(data, dict):
            return data.get(qmt_code, pd.DataFrame())
        return _format_market_data(data, fields)
    except Exception:
        return pd.DataFrame()


def get_current_data():
    """Get current market snapshot.

    Maps to QMT's get_full_tick.
    """
    global _context
    if _context is None:
        return {}

    ci = _context._qmt
    try:
        codes = ci.get_universe()
        if not codes:
            return {}
        tick = ci.get_full_tick(codes)
        result = {}
        for code, d in tick.items():
            eq_code = _to_eq_code(code)
            obj = type('CurrentData', (), {})()
            obj.day_open = d.get('open', 0)
            obj.high = d.get('high', 0)
            obj.low = d.get('low', 0)
            obj.last_price = d.get('lastPrice', 0)
            obj.volume = d.get('volume', 0)
            obj.money = d.get('amount', 0)
            obj.ask = d.get('askPrice', [])
            obj.bid = d.get('bidPrice', [])
            obj.high_limit = 0
            obj.low_limit = 0
            result[eq_code] = obj
        return result
    except Exception:
        return {}


def get_all_securities(types=('stock',), date=None):
    """Get all securities.

    QMT does not have a direct equivalent; this returns a minimal
    placeholder. For full stock lists, use QMT's get_stock_list_in_sector.
    """
    # Return a placeholder; users should use QMT's native sector APIs
    return pd.DataFrame()


def get_index_stocks(index_code, date=None):
    """Get index constituent stocks.

    Maps to QMT's get_sector or get_stock_list_in_sector.
    """
    global _context
    if _context is None:
        return []

    qmt_code = _to_qmt_code(index_code)
    ci = _context._qmt

    try:
        stocks = ci.get_sector(qmt_code)
        if isinstance(stocks, list):
            return [_to_eq_code(s) for s in stocks]
        # Try get_stock_list_in_sector with the index name
        stocks = ci.get_stock_list_in_sector(qmt_code)
        if isinstance(stocks, list):
            return [_to_eq_code(s) for s in stocks]
    except Exception:
        pass
    return []


def get_security_info(code):
    """Get security info. Maps to QMT's get_instrumentdetail."""
    global _context
    if _context is None:
        return None

    qmt_code = _to_qmt_code(code)
    ci = _context._qmt

    try:
        info = ci.get_instrumentdetail(qmt_code)
        if isinstance(info, dict):
            obj = type('SecurityInfo', (), {})()
            obj.code = code
            obj.display_name = info.get('InstrumentName', '')
            obj.name = info.get('InstrumentName', '')
            obj.start_date = info.get('OpenDate', '')
            obj.end_date = info.get('ExpireDate', '')
            return obj
    except Exception:
        pass
    return None


def _format_market_data(data, fields):
    """Normalize QMT market data to a standard DataFrame.

    QMT's get_market_data returns data in various formats depending
    on parameters; we normalize to a DataFrame indexed by date with
    field columns.
    """
    if data is None:
        return pd.DataFrame()

    if isinstance(data, pd.DataFrame):
        return data

    if isinstance(data, dict):
        # Single stock: {field: [values]} or {code: DataFrame}
        # Multiple stocks: {code: {field: [values]}}
        if len(data) == 0:
            return pd.DataFrame()

        first_val = list(data.values())[0]
        if isinstance(first_val, pd.DataFrame):
            # Multi-stock dict, return first stock's DataFrame
            return list(data.values())[0]
        if isinstance(first_val, (list, np.ndarray)):
            # Single stock: {field: series}
            try:
                df = pd.DataFrame(data)
                return df
            except Exception:
                return pd.DataFrame()

    return pd.DataFrame()


# =====================================================================
# Trading APIs (map to QMT order functions)
# =====================================================================

def order(security, amount, price=None, ContextInfo=None):
    """Order by share count.

    Positive = buy, negative = sell.
    Maps to QMT's order_shares.
    """
    global _context
    qmt_code = _to_qmt_code(security)
    ci = ContextInfo if ContextInfo else (_context._qmt if _context else None)
    if ci is None:
        return

    style = 'LATEST'
    if price is not None:
        style = 'FIX'

    if amount > 0:
        order_shares(qmt_code, amount, style, price or 0, ci, _account)
    elif amount < 0:
        order_shares(qmt_code, abs(amount), style, price or 0, ci, _account)


def order_target(security, amount, price=None, ContextInfo=None):
    """Order to a target share count.

    Maps to QMT's order_shares with position-aware logic.
    """
    global _context
    if _context is None:
        return

    current = 0
    if security in _context.portfolio.positions:
        current = _context.portfolio.positions[security].amount

    diff = amount - current
    if diff != 0:
        order(security, diff, price, ContextInfo)


def order_value(security, value, price=None, ContextInfo=None):
    """Order by value (amount in yuan).

    Positive = buy, negative = sell.
    Maps to QMT's order_value.
    """
    qmt_code = _to_qmt_code(security)
    ci = ContextInfo if ContextInfo else (_context._qmt if _context else None)
    if ci is None:
        return

    if value > 0:
        order_value_qmt(qmt_code, value, 'LATEST', price or 0, ci, _account)
    elif value < 0:
        order_value_qmt(qmt_code, abs(value), 'LATEST', price or 0, ci, _account)


def order_target_value(security, target_value, price=None, ContextInfo=None):
    """Order to a target position value.

    Maps to QMT's order_target_value.
    """
    qmt_code = _to_qmt_code(security)
    ci = ContextInfo if ContextInfo else (_context._qmt if _context else None)
    if ci is None:
        return

    order_target_value_qmt(qmt_code, target_value, 'LATEST', price or 0, ci, _account)


def record(**kwargs):
    """Record custom values (stored in context for reporting)."""
    if _context is not None:
        if not hasattr(_context, 'recorded_values'):
            _context.recorded_values = []
        kwargs['_time'] = datetime.datetime.now()
        _context.recorded_values.append(kwargs)


# =====================================================================
# QMT native order wrappers (re-exported with qmt_ prefix)
# =====================================================================

def _qmt_order_shares(stockcode, shares, style='LATEST', price=0,
                      ContextInfo=None, accId=''):
    """Thin wrapper: QMT's order_shares.

    QMT's order_shares uses positive shares for buy, negative for sell.
    """
    if ContextInfo is None:
        return
    try:
        if accId:
            order_shares(stockcode, shares, style, price, ContextInfo, accId)
        else:
            order_shares(stockcode, shares, style, price, ContextInfo)
    except Exception as e:
        print(f'[PTrade Adapter] order_shares failed: {e}')


def _qmt_order_value(stockcode, value, style='LATEST', price=0,
                     ContextInfo=None, accId=''):
    """Thin wrapper: QMT's order_value.

    QMT's order_value uses positive for buy, negative for sell.
    """
    if ContextInfo is None:
        return
    try:
        if accId:
            order_value(stockcode, value, style, price, ContextInfo, accId)
        else:
            order_value(stockcode, value, style, price, ContextInfo)
    except Exception as e:
        print(f'[PTrade Adapter] order_value failed: {e}')


def _qmt_order_target_value(stockcode, target_value, style='LATEST',
                            price=0, ContextInfo=None, accId=''):
    """Thin wrapper: QMT's order_target_value."""
    if ContextInfo is None:
        return
    try:
        if accId:
            order_target_value(stockcode, target_value, style, price,
                               ContextInfo, accId)
        else:
            order_target_value(stockcode, target_value, style, price,
                               ContextInfo)
    except Exception as e:
        print(f'[PTrade Adapter] order_target_value failed: {e}')


# =====================================================================
# Lifecycle bridge
# =====================================================================

def start(ContextInfo):
    """Call this in QMT's init() to start the EasyQuant strategy.

    Example in QMT strategy editor:
        from eqlib.ptrade_adapter import *

        def initialize(context):
            g.security = '601390'
            set_benchmark('000300.XSHG')
            run_daily(market_open, time='every_bar')

        def market_open(context):
            ...

        def init(ContextInfo):
            start(ContextInfo)

        def handlebar(ContextInfo):
            on_bar(ContextInfo)
    """
    global _context, _last_trade_day, _last_week, _last_month

    starting_cash = getattr(ContextInfo, 'capital', 100000.0)
    _context = Context(ContextInfo, starting_cash)

    # Run EasyQuant's initialize
    if _initialize_func is not None:
        try:
            _initialize_func(_context)
        except Exception as e:
            print(f'[PTrade Adapter] initialize() error: {e}')
            import traceback
            traceback.print_exc()

    # Run before_trading_start callbacks
    for func in _before_start_funcs:
        try:
            func(_context)
        except Exception as e:
            print(f'[PTrade Adapter] before_trading_start() error: {e}')

    # Sync portfolio
    _context.portfolio.update_from_qmt(ContextInfo)

    now = datetime.datetime.now()
    _last_trade_day = now.date()
    _last_week = now.isocalendar()[:2]  # (year, week)
    _last_month = now.month

    log('PTrade adapter started. EQ strategy initialized.')


def on_bar(ContextInfo):
    """Call this in QMT's handlebar() to drive the EasyQuant strategy.

    Example:
        def handlebar(ContextInfo):
            on_bar(ContextInfo)
    """
    global _context, _last_trade_day, _last_week, _last_month

    if _context is None:
        return

    _context._qmt = ContextInfo  # refresh reference

    # Sync portfolio from QMT account
    _context.portfolio.update_from_qmt(ContextInfo)

    # Update current datetime
    try:
        bar_time = ContextInfo.get_bar_timetag()
        _context.current_dt = datetime.datetime.fromtimestamp(bar_time / 1000)
    except Exception:
        _context.current_dt = datetime.datetime.now()

    now = _context.current_dt
    today = now.date()

    # Check for new trading day: run before_trading_start and daily functions
    # on the first bar of each day.  The _last_trade_day flag is updated AFTER
    # both blocks so that the daily functions check still sees the old value.
    if today != _last_trade_day:
        # Run before_trading_start
        for func in _before_start_funcs:
            try:
                func(_context)
            except Exception as e:
                print(f'[PTrade Adapter] before_trading_start() error: {e}')

        # Run daily functions (on first bar of each day)
        for _, func in _daily_funcs:
            try:
                func(_context)
            except Exception as e:
                print(f'[PTrade Adapter] run_daily() error: {e}')

        _last_trade_day = today

    # Run weekly functions
    current_week = now.isocalendar()[:2]
    if current_week != _last_week:
        _last_week = current_week
        weekday = now.weekday()  # 0=Mon
        for day_of_week, _, func in _weekly_funcs:
            if weekday == day_of_week:
                try:
                    func(_context)
                except Exception as e:
                    print(f'[PTrade Adapter] run_weekly() error: {e}')

    # Run monthly functions
    if now.month != _last_month:
        _last_month = now.month
        for day_of_month, _, func in _monthly_funcs:
            if now.day == day_of_month:
                try:
                    func(_context)
                except Exception as e:
                    print(f'[PTrade Adapter] run_monthly() error: {e}')

    # Run handle_data
    if _handle_data_func is not None:
        try:
            _handle_data_func(_context, None)
        except Exception as e:
            print(f'[PTrade Adapter] handle_data() error: {e}')

    # Run all daily callbacks for every bar
    for _, func in _daily_funcs:
        try:
            func(_context)
        except Exception as e:
            print(f'[PTrade Adapter] run_daily(bar) error: {e}')

    # Check for last bar — run after_trading_end
    try:
        if ContextInfo.is_last_bar():
            for func in _after_end_funcs:
                try:
                    func(_context)
                except Exception as e:
                    print(f'[PTrade Adapter] after_trading_end() error: {e}')
    except Exception:
        pass


# =====================================================================
# Strategy registration helpers
# =====================================================================

def initialize(func):
    """Decorator: register as the strategy's initialize function.

    Usage:
        @initialize
        def my_init(context):
            g.security = '601390'
            set_benchmark('000300.XSHG')
            run_daily(market_open)
    """
    global _initialize_func
    _initialize_func = func
    return func


def handle_data(func):
    """Decorator: register as the strategy's handle_data function.

    Usage:
        @handle_data
        def my_handler(context, data):
            ...
    """
    global _handle_data_func
    _handle_data_func = func
    return func


# =====================================================================
# Code export / conversion utility
# =====================================================================

def export_ptrade_script(strategy_file=None, output_file=None):
    """Generate a ready-to-run QMT strategy script from an EasyQuant strategy.

    This function generates a new .py file that wraps the user's EasyQuant
    strategy code with the QMT init()/handlebar() entry points.

    Parameters:
        strategy_file: path to the EasyQuant strategy .py file. If None,
            prints the template to stdout.
        output_file: path for the generated QMT strategy file.

    Returns:
        str: the generated script content.
    """
    template = '''"""QMT Strategy — auto-generated from EasyQuant strategy.

Instructions:
1. Copy this file into QMT's strategy editor.
2. Set your account ID in init() below.
3. Run backtest or live trading in QMT.
"""

from eqlib.ptrade_adapter import *

# ============================================================
# === Paste your EasyQuant strategy below this line ===
# ============================================================

{strategy_code}

# ============================================================
# === QMT entry points — do not modify ===
# ============================================================

def init(ContextInfo):
    set_account('{account_id}')  # <-- set your account ID here
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
'''

    if strategy_file is not None:
        with open(strategy_file, 'r', encoding='utf-8') as f:
            code = f.read()
        # Remove initialize/handle_data decorator usages since the adapter
        # uses explicit registration via start()/on_bar()
        code = code.replace('@initialize\n', '# @initialize -> registered via start()\n')
        code = code.replace('@handle_data\n', '# @handle_data -> registered via on_bar()\n')
    else:
        code = '# <paste your EasyQuant strategy code here>'

    script = template.format(strategy_code=code, account_id='YOUR_ACCOUNT_ID')

    if output_file is not None:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script)
        print(f'Generated QMT strategy: {output_file}')

    return script


# =====================================================================
# Re-export QMT native functions for convenience
# Users can import these directly when they need QMT-specific features
# =====================================================================

# The following are QMT's native functions that are already in the global
# namespace when running in QMT. We re-assign them here so the module
# can be imported without error during local development (they'll be
# overwritten by QMT's runtime when the strategy actually runs).
try:
    from builtins import order_shares, order_value, order_percent
    from builtins import order_target_value, order_target_percent, order_lots
    from builtins import get_trade_detail_data, get_last_order_id
    from builtins import get_value_by_order_id, can_cancel_order, cancel
    from builtins import cancel_task, pause_task, resume_task, do_order
    from builtins import passorder, algo_passorder, smart_algo_passorder
    from builtins import get_etf_info, get_etf_iopv
    from builtins import query_credit_opvolume, credit_opvolume_callback
except ImportError:
    # When running outside QMT (e.g., local backtest), these won't exist.
    # They are provided by QMT's runtime environment.
    pass


# =====================================================================
# Quick-start template
# =====================================================================

QMT_TEMPLATE = '''"""QMT Strategy Template — replace with your EasyQuant strategy.

Step 1: Write your EasyQuant-style strategy below.
Step 2: Set your account ID in init().
Step 3: Run in QMT.
"""

from eqlib.ptrade_adapter import *

# ---- Strategy code ----

def initialize(context):
    """Called once at start. Set up globals, schedule functions."""
    g.security = '601390'
    set_benchmark('000300.XSHG')
    set_account('YOUR_ACCOUNT_ID')  # <-- replace with your QMT account
    run_daily(market_open, time='every_bar')

def market_open(context):
    """Called every trading day (scheduled via run_daily)."""
    # Get recent price history
    hist = attribute_history(g.security, 20, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return

    # Simple MA crossover
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].mean()
    current = hist['close'].iloc[-1]

    if current > ma5 and current > ma20:
        # Buy with all available cash
        order_value(g.security, context.portfolio.available_cash)
        log(f"BUY {g.security} @ {current}")
    elif current < ma5:
        # Sell all
        order_target(g.security, 0)
        log(f"SELL {g.security} @ {current}")

# ---- QMT entry points (do not modify) ----

def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')  # <-- replace with your QMT account
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
'''
