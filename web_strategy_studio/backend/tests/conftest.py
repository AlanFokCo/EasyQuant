"""Shared test configuration for studio backend tests."""

import os

# A-REG4: Enable test-mode fallback for ensure_admin_user so tests that
# create the FastAPI app don't need EQ_ADMIN_PASSWORD set explicitly.
os.environ.setdefault("EQ_STUDIO_TESTING", "1")
