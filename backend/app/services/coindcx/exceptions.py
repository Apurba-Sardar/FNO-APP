class CoinDCXError(RuntimeError):
    """Base error for public CoinDCX market-data operations."""


class CoinDCXTimeoutError(CoinDCXError):
    pass


class CoinDCXRateLimitError(CoinDCXError):
    pass


class CoinDCXMalformedResponseError(CoinDCXError):
    pass


class CoinDCXWebSocketError(CoinDCXError):
    pass
