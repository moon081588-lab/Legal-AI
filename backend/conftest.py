"""Shared test fixtures.

Global process state (circuit breaker, rate-limit counters) leaks between tests
otherwise: as the suite grows, the 20-req/min limiter would start rejecting
legitimate test requests and tests would fail in ways that look random.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import app as app_module  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_process_state():
    app_module.breaker.reset()
    app_module._hits.clear()
    yield
    app_module.breaker.reset()
    app_module._hits.clear()
