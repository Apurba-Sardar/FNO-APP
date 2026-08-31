from app.market_data.discovery import MarketDiscoveryService
from app.services.coindcx.models import CoinDCXInstrument


class FakeDiscoveryClient:
    async def active_instruments(self):
        return ["B-BTC_USDT", "BROKEN", "B-ETH_USDT", "B-X_INR"]

    async def instrument(self, pair):
        if pair == "B-ETH_USDT":
            raise RuntimeError("malformed metadata")
        quote = pair.rsplit("_", 1)[-1]
        return CoinDCXInstrument(
            pair=pair,
            status="active",
            settle_currency_short_name=quote,
            quote_currency_short_name=quote,
            underlying_currency_short_name="BTC",
        )


async def test_fast_discovery_filters_non_usdt_and_malformed_symbols():
    markets, errors = await MarketDiscoveryService(FakeDiscoveryClient()).get_eligible_markets()
    assert [market.symbol for market in markets] == ["B-BTC_USDT", "B-ETH_USDT"]
    assert "BROKEN" in errors


async def test_detailed_discovery_isolates_one_failed_symbol():
    markets, errors = await MarketDiscoveryService(FakeDiscoveryClient()).get_eligible_markets(
        include_details=True
    )
    assert [market.symbol for market in markets] == ["B-BTC_USDT"]
    assert "B-ETH_USDT" in errors
