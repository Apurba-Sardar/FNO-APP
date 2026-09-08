import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field


class ClaudeScalpAnalysis(BaseModel):
    symbol: str
    direction: str  # "buy" or "sell"
    conviction_score: int = Field(ge=0, le=100)
    sentiment: str  # "STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH"
    pro_trader_rationale: str
    optimal_entry_zone: str
    target_price: float
    stop_price: float
    pre_flight_approved: bool
    ai_provider: str  # "Pro Trader Quantitative Engine" | "Claude 3.5 Sonnet"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProTraderScalpAdvisor:
    """Zero-Cost Institutional Quantitative Scalping Engine.
    
    Replaces costly external LLM API calls with deterministic, micro-second
    quantitative models evaluating orderbook depth skew, spread efficiency,
    24h momentum velocity, parabolic exhaustion traps, and short-term RSI/EMA structure.
    Cost: $0.00 | Latency: < 0.5ms | Zero External Dependencies
    """

    def __init__(self, min_conviction: int = 70) -> None:
        self.min_conviction = min_conviction
        self.log = structlog.get_logger()

    def evaluate(
        self,
        symbol: str,
        current_price: float,
        direction: str,
        metrics: dict[str, Any] | None = None,
    ) -> ClaudeScalpAnalysis:
        metrics = metrics or {}
        is_buy = direction.lower() in ("buy", "long")

        # 1. Extract Metrics
        spread_bps = float(metrics.get("spread_bps", 3.0))
        vol_24 = float(metrics.get("quote_volume", 5_000_000.0))
        change_24 = float(metrics.get("change_24h_pct", 0.0))
        rsi = float(metrics.get("rsi", 52.0))
        trend = str(metrics.get("trend", "BULLISH" if is_buy else "BEARISH")).upper()
        skew = str(metrics.get("skew", "Neutral Depth"))

        # 2. Base Quantitative Score
        base_score = 72

        # 3. Order Book Depth Skew & Spread Efficiency
        spread_points = 0
        if spread_bps <= 1.5:
            spread_points = 12  # Ultra-liquid institutional spread (< 0.015%)
        elif spread_bps <= 3.0:
            spread_points = 6
        elif spread_bps <= 5.5:
            spread_points = 0
        elif spread_bps <= 8.0:
            spread_points = -12  # Moderate slippage penalty
        else:
            spread_points = -30  # High slippage trap (> 8 bps)

        depth_points = 0
        if "BUYER BID DEPTH" in skew.upper():
            depth_points = 10 if is_buy else -10
        elif "SELLER ASK WALL" in skew.upper():
            depth_points = -12 if is_buy else 10

        # 4. Volume Participation
        vol_points = 0
        if vol_24 >= 100_000_000:
            vol_points = 8
        elif vol_24 >= 20_000_000:
            vol_points = 5
        elif vol_24 < 2_000_000:
            vol_points = -15

        # 5. Momentum Velocity & Parabolic Exhaustion Gate
        momentum_points = 0
        rationale = ""
        is_exhaustion = False

        if is_buy:
            # Trap Detection: Chasing overextended parabolic pumps
            if change_24 >= 25.0 and rsi >= 58.0:
                is_exhaustion = True
                momentum_points = -35
                rationale = (
                    f"Parabolic Exhaustion Warning: +{change_24:.1f}% 24h pump with RSI at {rsi:.1f} signals "
                    f"late-stage retail chasing into distribution. High risk of local top rejection."
                )
            # Golden Setup: High-momentum gainer in healthy pullback accumulation
            elif change_24 >= 5.0 and 35.0 <= rsi <= 55.0:
                momentum_points = 16
                rationale = (
                    f"Pullback Accumulation in Top Gainer: Healthy RSI ({rsi:.1f}) retest after +{change_24:.1f}% 24h trend. "
                    f"Buyers defending support with tight {spread_bps:.1f} bps spread for 3x momentum continuation."
                )
            # Oversold Mean Reversion Bounce
            elif rsi < 35.0:
                momentum_points = 14
                rationale = (
                    f"Oversold Mean Reversion: RSI ({rsi:.1f}) in prime liquidity absorption zone. "
                    f"Support defense confirms high-probability mean reversion bounce with tight risk."
                )
            # Standard Bullish Continuation
            elif 45.0 <= rsi <= 65.0:
                momentum_points = 8
                rationale = (
                    f"Bullish Flow Alignment: Steady order flow with RSI at {rsi:.1f} and positive institutional participation. "
                    f"Favorable 3x risk/reward toward breakout target."
                )
            else:
                momentum_points = -5
                rationale = (
                    f"Neutral Consolidation: Market lacking directional conviction with RSI at {rsi:.1f}. "
                    f"Patience recommended for clearer liquidity sweep."
                )
        else:
            # Short / Sell Setup
            if change_24 >= 25.0 and rsi >= 68.0:
                momentum_points = 18
                rationale = (
                    f"Overextended Breakdown Rejection: Parabolic surge (+{change_24:.1f}%) rejecting key resistance with "
                    f"RSI overbought ({rsi:.1f}). Prime short reversal scalp toward equilibrium."
                )
            elif rsi > 60.0:
                momentum_points = 10
                rationale = (
                    f"Overhead Supply Wall: Heavy selling pressure near local highs with RSI at {rsi:.1f}. "
                    f"Favoring breakdown scalp with controlled stop."
                )
            else:
                momentum_points = -5
                rationale = f"Neutral flow: RSI at {rsi:.1f} without clear short exhaustion trigger."

        # 6. Composite Conviction Calculation
        total_score = base_score + spread_points + depth_points + vol_points + momentum_points
        if is_exhaustion:
            total_score = min(total_score, 45)  # Hard cap on parabolic traps

        final_score = max(20, min(96, int(total_score)))

        # 7. Sentiment & Approval
        if final_score >= 82:
            sentiment = "STRONG_BULLISH" if is_buy else "STRONG_BEARISH"
        elif final_score >= 68:
            sentiment = "BULLISH" if is_buy else "BEARISH"
        else:
            sentiment = "NEUTRAL"

        # 8. Precision Dynamic Target and Micro-Stop Levels
        pz_low = round(current_price * 0.998, 4)
        pz_high = round(current_price * 1.002, 4)
        if is_buy:
            target = round(current_price * 1.011, 4)  # +1.1%
            stop = round(current_price * 0.991, 4)    # -0.9%
        else:
            target = round(current_price * 0.989, 4)  # -1.1%
            stop = round(current_price * 1.009, 4)    # +0.9%

        approved = bool(final_score >= self.min_conviction and spread_bps <= 7.5 and not is_exhaustion)

        return ClaudeScalpAnalysis(
            symbol=symbol,
            direction=direction,
            conviction_score=final_score,
            sentiment=sentiment,
            pro_trader_rationale=rationale,
            optimal_entry_zone=f"${pz_low:,.4g} – ${pz_high:,.4g}",
            target_price=target,
            stop_price=stop,
            pre_flight_approved=approved,
            ai_provider="Pro Trader Quantitative Engine",
        )


class ClaudeScalpAdvisor:
    """Unified Scalp Advisor powered 100% by the Zero-Cost Pro Trader Algorithmic Engine.
    
    Zero External API calls ($0.00 cost, <0.1ms latency, 100% uptime).
    Anthropic API calls are completely omitted.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "pro-trader-algo",
        min_conviction: int = 70,
        timeout_seconds: float = 0.0,
        enabled: bool = False,
    ) -> None:
        self.min_conviction = min_conviction
        self.algo_engine = ProTraderScalpAdvisor(min_conviction=min_conviction)
        self._cache: dict[str, tuple[datetime, ClaudeScalpAnalysis]] = {}
        self.log = structlog.get_logger()

    @property
    def is_configured(self) -> bool:
        return False

    async def analyze_scalp(
        self,
        symbol: str,
        current_price: float,
        direction: str,
        metrics: dict[str, Any] | None = None,
    ) -> ClaudeScalpAnalysis:
        metrics = metrics or {}
        cache_key = f"{symbol}:{direction.lower()}"
        now = datetime.now(UTC)

        # 20-second cache
        if cache_key in self._cache:
            cached_time, cached_res = self._cache[cache_key]
            if (now - cached_time).total_seconds() < 20:
                return cached_res

        # 100% Quantitative Algorithmic Engine ($0 cost, micro-second execution)
        result = self.algo_engine.evaluate(symbol, current_price, direction, metrics)
        self._cache[cache_key] = (now, result)
        return result

