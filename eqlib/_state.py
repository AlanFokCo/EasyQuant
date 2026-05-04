"""Global state shared across eqlib modules (avoids circular imports)."""

_context = None
_g = None
_order_cost = None
_order_cost_config = None
_benchmark = None
_options = {}
_scheduled_funcs = []
_recorded_values: dict = {}   # date -> dict (was list, now O(1) lookup)
_trade_log = []
_handle_data_func = None
_before_trading_start_funcs = []
_after_trading_end_funcs = []


def reset_all():
    global _context, _g, _order_cost, _order_cost_config, _benchmark, _options
    global _scheduled_funcs, _recorded_values, _trade_log, _handle_data_func
    global _before_trading_start_funcs, _after_trading_end_funcs

    _context = None
    _g = None
    _order_cost = None
    _order_cost_config = None
    _benchmark = None
    _options = {}
    _scheduled_funcs = []
    _recorded_values = {}
    _trade_log = []
    _handle_data_func = None
    _before_trading_start_funcs = []
    _after_trading_end_funcs = []
