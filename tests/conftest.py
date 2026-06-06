"""pytest configuration for EasyQuant test suite.

Adds the Web Strategy Studio backend directory to sys.path so that
``studio_api`` is importable without a separate package install step.
"""

import os
import sys
from pathlib import Path

# Enable eqlib logger propagation so pytest's caplog fixture can capture logs.
os.environ["EQLIB_LOG_PROPAGATE"] = "1"

_STUDIO_BACKEND = Path(__file__).parent.parent / "web_strategy_studio" / "backend"
if str(_STUDIO_BACKEND) not in sys.path:
    sys.path.insert(0, str(_STUDIO_BACKEND))
