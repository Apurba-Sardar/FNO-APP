class RiskError(Exception):
    """Base error for deterministic risk evaluation."""


class RiskContextUnavailable(RiskError):
    """Requested setup or market context is unavailable."""
