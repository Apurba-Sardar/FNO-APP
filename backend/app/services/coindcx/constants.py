from typing import Final

API_BASE_URL: Final = "https://api.coindcx.com"
PUBLIC_BASE_URL: Final = "https://public.coindcx.com"
WEBSOCKET_URL: Final = "wss://stream.coindcx.com"

ACTIVE_INSTRUMENTS_PATH: Final = "/exchange/v1/derivatives/futures/data/active_instruments"
INSTRUMENT_PATH: Final = "/exchange/v1/derivatives/futures/data/instrument"
TRADES_PATH: Final = "/exchange/v1/derivatives/futures/data/trades"
CANDLES_PATH: Final = "/market_data/candlesticks"
ORDERBOOK_PATH: Final = "/market_data/v3/orderbook/{pair}-futures/{depth}"
CURRENT_PRICES_PATH: Final = "/market_data/v3/current_prices/futures/rt"

REST_RESOLUTIONS: Final = frozenset({"1", "5", "60", "1D"})
ORDERBOOK_DEPTHS: Final = frozenset({10, 20, 50})
WEBSOCKET_CANDLE_INTERVALS: Final = frozenset(
    {"1m", "5m", "15m", "30m", "1h", "4h", "8h", "1d", "3d", "1w", "1M"}
)
CURRENT_PRICES_CHANNEL: Final = "currentPrices@futures@rt"
CURRENT_PRICES_EVENT: Final = "currentPrices@futures#update"

# Authenticated futures endpoints from the official CoinDCX API reference.
FUTURES_ORDERS_PATH: Final = "/exchange/v1/derivatives/futures/orders"
FUTURES_CREATE_ORDER_PATH: Final = "/exchange/v1/derivatives/futures/orders/create"
FUTURES_CANCEL_ORDER_PATH: Final = "/exchange/v1/derivatives/futures/orders/cancel"
FUTURES_POSITIONS_PATH: Final = "/exchange/v1/derivatives/futures/positions"
FUTURES_EXIT_POSITION_PATH: Final = "/exchange/v1/derivatives/futures/positions/exit"
FUTURES_CREATE_TPSL_PATH: Final = "/exchange/v1/derivatives/futures/positions/create_tpsl"
FUTURES_TRADES_PATH: Final = "/exchange/v1/derivatives/futures/trades"
FUTURES_WALLETS_PATH: Final = "/exchange/v1/derivatives/futures/positions/cross_margin_details"
