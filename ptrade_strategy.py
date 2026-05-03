"""QMT Strategy — auto-generated from EasyQuant strategy.

Instructions:
1. Copy this file into QMT's strategy editor.
2. Set your account ID in init() below.
3. Run backtest or live trading in QMT.
"""

from eqlib.ptrade_adapter import *

# ============================================================
# === Paste your EasyQuant strategy below this line ===
# ============================================================

# <paste your EasyQuant strategy code here>

# ============================================================
# === QMT entry points — do not modify ===
# ============================================================

def init(ContextInfo):
    set_account('YOUR_ACCOUNT_ID')  # <-- set your account ID here
    start(ContextInfo)

def handlebar(ContextInfo):
    on_bar(ContextInfo)
