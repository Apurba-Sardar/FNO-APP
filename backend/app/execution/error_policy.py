from enum import StrEnum


class APIErrorCategory(StrEnum):
    AUTH_ERROR = "auth_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    INSUFFICIENT_MARGIN = "insufficient_margin"
    INVALID_SYMBOL = "invalid_symbol"
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_PRICE = "invalid_price"
    ORDER_REJECTED = "order_rejected"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


NON_RETRYABLE = {
    APIErrorCategory.AUTH_ERROR,
    APIErrorCategory.INVALID_REQUEST,
    APIErrorCategory.INSUFFICIENT_MARGIN,
    APIErrorCategory.INVALID_SYMBOL,
    APIErrorCategory.INVALID_QUANTITY,
    APIErrorCategory.INVALID_PRICE,
    APIErrorCategory.ORDER_REJECTED,
}


def classify_api_error(status: int | None, message: str) -> APIErrorCategory:
    value = message.lower()
    if status in {401, 403} or "signature" in value or "auth" in value:
        return APIErrorCategory.AUTH_ERROR
    if status == 429:
        return APIErrorCategory.RATE_LIMIT
    if "timeout" in value:
        return APIErrorCategory.TIMEOUT
    if "insufficient" in value or "margin" in value and "insufficient" in value:
        return APIErrorCategory.INSUFFICIENT_MARGIN
    if "symbol" in value or "pair" in value and "invalid" in value:
        return APIErrorCategory.INVALID_SYMBOL
    if "quantity" in value:
        return APIErrorCategory.INVALID_QUANTITY
    if "price" in value:
        return APIErrorCategory.INVALID_PRICE
    if "reject" in value:
        return APIErrorCategory.ORDER_REJECTED
    if status is not None and status >= 500:
        return APIErrorCategory.SERVER_ERROR
    if status is not None and status >= 400:
        return APIErrorCategory.INVALID_REQUEST
    return APIErrorCategory.UNKNOWN_ERROR
