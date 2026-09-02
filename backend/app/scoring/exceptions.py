class ScoringError(Exception):
    """Base deterministic scoring error."""


class NoScannerCandidates(ScoringError):
    """Raised when recalculation is requested before a scanner cycle exists."""
