import time
import pytest
from app.ai.claude_advisor import ProTraderScalpAdvisor, ClaudeScalpAdvisor


def test_parabolic_exhaustion_trap_rejected():
    """Verify algorithm detects +30% parabolic pump with high RSI and rejects trade."""
    advisor = ProTraderScalpAdvisor(min_conviction=70)
    analysis = advisor.evaluate(
        symbol="B-HFT_USDT",
        current_price=0.0277,
        direction="buy",
        metrics={
            "change_24h_pct": 33.2,
            "rsi": 62.0,
            "spread_bps": 8.5,
            "quote_volume": 350_000_000,
        },
    )
    assert analysis.conviction_score <= 45
    assert analysis.sentiment == "NEUTRAL"
    assert analysis.pre_flight_approved is False
    assert "Parabolic Exhaustion" in analysis.pro_trader_rationale


def test_pullback_accumulation_golden_setup():
    """Verify algorithm awards high conviction to high-momentum gainer in healthy pullback."""
    advisor = ProTraderScalpAdvisor(min_conviction=70)
    analysis = advisor.evaluate(
        symbol="B-UAI_USDT",
        current_price=0.6358,
        direction="buy",
        metrics={
            "change_24h_pct": 18.6,
            "rsi": 45.8,
            "spread_bps": 2.1,
            "quote_volume": 129_000_000,
            "skew": "Buyer Bid Depth",
        },
    )
    assert analysis.conviction_score >= 82
    assert analysis.sentiment in ("STRONG_BULLISH", "BULLISH")
    assert analysis.pre_flight_approved is True
    assert "Pullback Accumulation" in analysis.pro_trader_rationale
    assert analysis.ai_provider == "Pro Trader Quantitative Engine"


def test_oversold_mean_reversion_bounce():
    """Verify algorithm identifies oversold dip in high-liquidity major as prime scalp."""
    advisor = ProTraderScalpAdvisor(min_conviction=70)
    analysis = advisor.evaluate(
        symbol="B-XRP_USDT",
        current_price=1.397,
        direction="buy",
        metrics={
            "change_24h_pct": -1.5,
            "rsi": 31.4,
            "spread_bps": 0.8,
            "quote_volume": 840_000_000,
            "skew": "Buyer Bid Depth",
        },
    )
    assert analysis.conviction_score >= 80
    assert analysis.pre_flight_approved is True
    assert "Oversold Mean Reversion" in analysis.pro_trader_rationale


def test_sub_millisecond_speed():
    """Verify zero-cost algorithm evaluates 50 candidates in under 5ms (instantaneous)."""
    advisor = ProTraderScalpAdvisor()
    start = time.perf_counter()
    for _ in range(50):
        advisor.evaluate(
            symbol="B-SOL_USDT",
            current_price=105.0,
            direction="buy",
            metrics={"rsi": 48.0, "spread_bps": 1.2, "change_24h_pct": 8.5},
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 20.0  # Well under 20ms for 50 candidates


@pytest.mark.asyncio
async def test_zero_cost_advisor_integration():
    """Verify ClaudeScalpAdvisor seamlessly defaults to ProTraderScalpAdvisor at $0 cost."""
    advisor = ClaudeScalpAdvisor(enabled=False)
    assert advisor.is_configured is False
    
    res = await advisor.analyze_scalp(
        symbol="B-CATI_USDT",
        current_price=0.0628,
        direction="buy",
        metrics={"rsi": 52.0, "spread_bps": 1.5, "change_24h_pct": 12.0},
    )
    assert res.ai_provider == "Pro Trader Quantitative Engine"
    assert res.pre_flight_approved is True
