class StrategyError(Exception):
    """Base exception for the deterministic, non-executing strategy layer."""


class StrategyContextUnavailable(StrategyError):
    """Raised when a symbol has no Phase 4/5 analytical context."""
