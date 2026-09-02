from .models import FundingStatus


class PaperFundingModel:
    """Funding is never fabricated; Phase 9 public feed has no normalized funding stream."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.status = FundingStatus.UNAVAILABLE if enabled else FundingStatus.DISABLED

    def cost(self, *_args, **_kwargs) -> float:
        return 0.0
