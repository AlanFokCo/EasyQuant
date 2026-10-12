"""pytest configuration for EasyQuant test suite."""

import os

# Enable eqlib logger propagation so pytest's caplog fixture can capture logs.
os.environ["EQLIB_LOG_PROPAGATE"] = "1"
