"""Historical strategy simulation (deferred beyond Phase 1)."""
"""Isolated, deterministic historical backtesting package."""

from .config import BacktestConfig
from .engine import BacktestEngine
from .models import BacktestResult

__all__ = ["BacktestConfig", "BacktestEngine", "BacktestResult"]
