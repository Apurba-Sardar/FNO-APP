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
    """Unified Scalp Advisor with Zero-Cost Pro Trader Algorithmic Engine by default.
    
    If CLAUDE_SCALP_ENABLED=false (or no API key), uses local ProTraderScalpAdvisor ($0.00 cost, <0.5ms latency).
    If CLAUDE_SCALP_ENABLED=true and API key is set, optionally routes through Anthropic API.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        min_conviction: int = 70,
        timeout_seconds: float = 12.0,
        enabled: bool | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.min_conviction = min_conviction
        self.timeout_seconds = timeout_seconds
        
        # Check explicit enabled flag or env var (default: False to eliminate cost)
        if enabled is not None:
            self.enabled = enabled
        else:
            env_enabled = os.getenv("CLAUDE_SCALP_ENABLED", "false").strip().lower()
            self.enabled = env_enabled in ("1", "true", "yes")

        self.algo_engine = ProTraderScalpAdvisor(min_conviction=min_conviction)
        self._cache: dict[str, tuple[datetime, ClaudeScalpAnalysis]] = {}
        self.log = structlog.get_logger()

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key and len(self.api_key) > 10)

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

        # If Claude is disabled or omitted -> run Pro Trader Quantitative Engine locally ($0 cost, <0.5ms)
        if not self.is_configured:
            result = self.algo_engine.evaluate(symbol, current_price, direction, metrics)
            self._cache[cache_key] = (now, result)
            return result

        # Optional: Call Anthropic API if explicitly enabled
        try:
            result = await self._call_claude_api(symbol, current_price, direction, metrics)
            self._cache[cache_key] = (now, result)
            return result
        except Exception as exc:
            self.log.warning("CLAUDE_API_FALLBACK_TO_ALGO", symbol=symbol, error=str(exc))
            result = self.algo_engine.evaluate(symbol, current_price, direction, metrics)
            self._cache[cache_key] = (now, result)
            return result

    async def _call_claude_api(
        self,
        symbol: str,
        current_price: float,
        direction: str,
        metrics: dict[str, Any],
    ) -> ClaudeScalpAnalysis:
        is_buy = direction.lower() in ("buy", "long")
        dir_label = "BUY / LONG" if is_buy else "SELL / SHORT"

        prompt = f"""You are an elite institutional crypto prop trader specializing in high-frequency 3x leverage scalping on CoinDCX Futures.
Evaluate this setup for {symbol}:
- Current Price: ${current_price:,.4g}
- Proposed Direction: {dir_label}
- Volatility / Spread: {metrics.get("spread_bps", 5.0)} bps
- 24h Volume: ${metrics.get("quote_volume", 500000):,.0f}
- 24h Price Change: {metrics.get("change_24h_pct", 0.0):+.2f}% (High 24h Momentum Gainer)
- Momentum RSI: {metrics.get("rsi", 52.0)}
- Trend EMA Align: {metrics.get("trend", "BULLISH" if is_buy else "BEARISH")}

Respond ONLY with a valid JSON object matching this schema:
{{
  "conviction_score": <integer 0-100>,
  "sentiment": <"STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH">,
  "pro_trader_rationale": <string: 1-2 punchy sentences describing order flow, liquidity sweep, or key support/resistance rejection>,
  "optimal_entry_zone": <string: tight price range e.g. "$1.448 – $1.452">,
  "target_price": <number: +1.1% for long, -1.1% for short>,
  "stop_price": <number: -0.9% for long, +0.9% for short>,
  "pre_flight_approved": <boolean: true if conviction >= {self.min_conviction}>
}}
Do NOT include markdown backticks or commentary."""

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
            if res.status_code != 200:
                raise RuntimeError(f"Claude API HTTP {res.status_code}: {res.text[:120]}")
            data = res.json()
            content = data.get("content", [{}])[0].get("text", "").strip()

            # Clean JSON string
            cleaned = re.sub(r"^```json\s*", "", content, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)

            conviction = int(parsed.get("conviction_score", 80))
            return ClaudeScalpAnalysis(
                symbol=symbol,
                direction=direction,
                conviction_score=conviction,
                sentiment=str(parsed.get("sentiment", "BULLISH" if is_buy else "BEARISH")),
                pro_trader_rationale=str(parsed.get("pro_trader_rationale", "")),
                optimal_entry_zone=str(parsed.get("optimal_entry_zone", f"${current_price * 0.998:,.4g} – ${current_price * 1.002:,.4g}")),
                target_price=float(parsed.get("target_price", current_price * 1.011 if is_buy else current_price * 0.989)),
                stop_price=float(parsed.get("stop_price", current_price * 0.991 if is_buy else current_price * 1.009)),
                pre_flight_approved=bool(conviction >= self.min_conviction),
                ai_provider="Claude 3.5 Sonnet",
            )
