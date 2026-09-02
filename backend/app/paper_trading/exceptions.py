class PaperTradingError(Exception):
    """Base paper-engine error."""


class PaperConfigurationError(PaperTradingError):
    """Unsafe or invalid paper configuration."""


class PaperExecutionRejected(PaperTradingError):
    """A simulated execution was rejected safely."""


class StaleMarketData(PaperExecutionRejected):
    """No simulation may enter on stale data."""
