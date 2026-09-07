import pytest
from unittest.mock import AsyncMock, MagicMock
from app.market_data.gainers import DynamicGainerScanner, GainerCandidate


@pytest.mark.asyncio
async def test_dynamic_gainer_scanner_filters_and_ranks():
    mock_client = AsyncMock()
    mock_snapshot = MagicMock()
    mock_snapshot.prices = {
        # Valid high-volume gainer 1
        "B-HFT_USDT": {"ls": 0.027, "v": 350_000_000.0, "pc": 33.16, "h": 0.029, "l": 0.020},
        # Valid high-volume gainer 2
        "B-CATI_USDT": {"ls": 0.063, "v": 38_000_000.0, "pc": 28.22, "h": 0.065, "l": 0.048},
        # Filtered: negative 24h change (loser)
        "B-DUMP_USDT": {"ls": 1.0, "v": 50_000_000.0, "pc": -12.5, "h": 1.2, "l": 0.9},
        # Filtered: low volume (< $2M)
        "B-TINY_USDT": {"ls": 0.5, "v": 500_000.0, "pc": 45.0, "h": 0.6, "l": 0.4},
        # Filtered: not a futures USDT pair
        "BTC_INR": {"ls": 8000000.0, "v": 100_000_000.0, "pc": 5.0},
        # Filtered: invalid price
        "B-ZERO_USDT": {"ls": 0.0, "v": 10_000_000.0, "pc": 10.0},
    }
    mock_client.current_prices.return_value = mock_snapshot

    scanner = DynamicGainerScanner(min_volume_usdt=2_000_000.0, min_gain_pct=0.5)
    gainers = await scanner.scan_market_gainers(mock_client, limit=10)

    assert len(gainers) == 2
    assert gainers[0].symbol == "B-HFT_USDT"
    assert gainers[0].change_24h_pct == 33.16
    assert gainers[0].gain_rank == 1
    assert gainers[0].is_top_gainer is True

    assert gainers[1].symbol == "B-CATI_USDT"
    assert gainers[1].change_24h_pct == 28.22
    assert gainers[1].gain_rank == 2


def test_high_volume_majors_fallback():
    prices = {
        "B-BTC_USDT": {"ls": 68000.0, "v": 500_000_000.0, "pc": 2.5},
        "B-ETH_USDT": {"ls": 2500.0, "v": 300_000_000.0, "pc": -1.2},
    }
    majors = DynamicGainerScanner.get_high_volume_majors(prices, symbols=("B-BTC_USDT", "B-ETH_USDT"))
    assert len(majors) == 2
    assert majors[0].symbol == "B-BTC_USDT"
    assert majors[0].last_price == 68000.0
