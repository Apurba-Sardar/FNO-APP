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

    assert len(gainers) == 3
    assert gainers[0].symbol == "B-HFT_USDT"
    assert gainers[0].change_24h_pct == 33.16
    assert gainers[0].gain_rank == 1
    assert gainers[0].is_top_gainer is True
    assert gainers[0].direction == "buy"

    assert gainers[1].symbol == "B-CATI_USDT"
    assert gainers[1].change_24h_pct == 28.22
    assert gainers[1].gain_rank == 2
    assert gainers[1].direction == "buy"

    assert gainers[2].symbol == "B-DUMP_USDT"
    assert gainers[2].direction == "sell"
    assert gainers[2].change_24h_pct == -12.5


def test_high_volume_majors_fallback():
    prices = {
        "B-BTC_USDT": {"ls": 68000.0, "v": 500_000_000.0, "pc": 2.5},
        "B-ETH_USDT": {"ls": 2500.0, "v": 300_000_000.0, "pc": -1.2},
    }
    majors = DynamicGainerScanner.get_high_volume_majors(prices, symbols=("B-BTC_USDT", "B-ETH_USDT"))
    assert len(majors) == 2
    assert majors[0].symbol == "B-BTC_USDT"
    assert majors[0].last_price == 68000.0


@pytest.mark.asyncio
async def test_lower_circuit_detection_and_penalties():
    mock_client = AsyncMock()
    mock_snapshot = MagicMock()
    mock_snapshot.prices = {
        # Moderate breakdown candidate
        "B-MODERATE_USDT": {"ls": 1.0, "v": 20_000_000.0, "pc": -10.0, "h": 1.1, "l": 0.95},
        # Lower circuit pair (-20%)
        "B-LC_USDT": {"ls": 0.5, "v": 20_000_000.0, "pc": -20.0, "h": 0.7, "l": 0.45},
        # Extreme waterfall dump (-42%)
        "B-CRASH_USDT": {"ls": 0.1, "v": 20_000_000.0, "pc": -42.0, "h": 0.2, "l": 0.08},
    }
    mock_client.current_prices.return_value = mock_snapshot

    scanner = DynamicGainerScanner(min_volume_usdt=5_000_000.0, min_gain_pct=0.5)
    candidates = await scanner.scan_market_gainers(mock_client, limit=10)

    by_sym = {c.symbol: c for c in candidates}
    assert by_sym["B-LC_USDT"].is_lower_circuit is True
    assert by_sym["B-CRASH_USDT"].is_lower_circuit is True
    assert by_sym["B-MODERATE_USDT"].is_lower_circuit is False

    # Moderate breakdown should have higher opportunity score than extreme waterfall crash
    assert by_sym["B-MODERATE_USDT"].opportunity_score > by_sym["B-CRASH_USDT"].opportunity_score

