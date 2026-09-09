import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel

from app.services.coindcx.public_client import CoinDCXPublicClient


class GainerCandidate(BaseModel):
    symbol: str
    last_price: float
    volume_24h: float
    change_24h_pct: float
    momentum_score: float
    direction: str = "buy"  # "buy" for long scalp, "sell" for short scalp
    high_24h: float | None = None
    low_24h: float | None = None
    spread_bps: float = 3.5
    is_top_gainer: bool = True
    gain_rank: int = 1
    opportunity_score: float = 0.0


class DynamicGainerScanner:
    """Discovers and ranks high-volume 24h momentum opportunities (both Long gainers and Short breakdowns) across CoinDCX futures."""

    def __init__(
        self,
        min_volume_usdt: float = 5_000_000.0,
        min_gain_pct: float = 2.5,
        max_spread_bps: float = 15.0,
    ) -> None:
        self.min_volume_usdt = min_volume_usdt
        self.min_gain_pct = min_gain_pct
        self.max_spread_bps = max_spread_bps
        self.log = structlog.get_logger().bind(component="DynamicGainerScanner")

    async def scan_market_gainers(
        self,
        client: CoinDCXPublicClient,
        limit: int = 20,
    ) -> list[GainerCandidate]:
        """Fetch all real-time market prices, filter for USDT futures with high volume and explosive movement,

        and rank by institutional momentum (Longs and Shorts).
        """
        try:
            snapshot = await client.current_prices()
            prices = snapshot.prices if hasattr(snapshot, "prices") else {}
        except Exception as exc:
            self.log.error("CURRENT_PRICES_SNAPSHOT_FAILED", error=str(exc))
            return []

        candidates: list[dict[str, Any]] = []

        for symbol, data in prices.items():
            # Must be USDT futures contract
            if not isinstance(symbol, str) or not symbol.startswith("B-") or not symbol.endswith("_USDT"):
                continue
            if not isinstance(data, dict):
                continue

            last_px = float(data.get("ls") or data.get("mp") or data.get("last_price") or 0.0)
            vol_24 = float(data.get("v") or 0.0)
            chg_24 = float(data.get("pc") or 0.0)
            high_24 = float(data.get("h") or 0.0) if data.get("h") is not None else None
            low_24 = float(data.get("l") or 0.0) if data.get("l") is not None else None

            # Filter for liquidity ($5M+ USDT) and meaningful momentum move (>= 2.5% in either direction)
            if last_px <= 0 or vol_24 < self.min_volume_usdt or abs(chg_24) < self.min_gain_pct:
                continue

            # Base composite institutional momentum: percentage move weighted by volume depth
            vol_log = math.log10(max(vol_24, 1_000_000.0))
            momentum_score = round(abs(chg_24) * vol_log, 2)
            trade_direction = "buy" if chg_24 > 0 else "sell"

            # Dynamic Opportunity Quality Rating:
            opp_score = momentum_score

            # 1. Proximity to Day's Extreme (Active Breakout / Breakdown continuation)
            if trade_direction == "buy" and high_24 and high_24 > 0:
                high_prox = last_px / high_24
                if high_prox >= 0.96:
                    opp_score += 30.0  # Fresh 24h high breakout zone
                elif high_prox >= 0.92:
                    opp_score += 18.0  # Continuation near highs
                elif high_prox < 0.85:
                    opp_score -= 20.0  # Deep stall / pullback penalty
            elif trade_direction == "sell" and low_24 and low_24 > 0:
                low_prox = low_24 / last_px
                if low_prox >= 0.96:
                    opp_score += 30.0  # Fresh 24h low breakdown zone
                elif low_prox >= 0.92:
                    opp_score += 18.0  # Continuation near lows
                elif low_prox < 0.85:
                    opp_score -= 20.0  # Deep bounce / rebound penalty

            # 2. Volume Depth & Liquidity Bonus
            if vol_24 >= 30_000_000.0:
                opp_score += 20.0
            elif vol_24 >= 15_000_000.0:
                opp_score += 12.0
            elif vol_24 >= 8_000_000.0:
                opp_score += 6.0

            # 3. Prime Scalp Velocity Zone (Sweet-spot 6% to 35% movement)
            abs_chg = abs(chg_24)
            if 6.0 <= abs_chg <= 35.0:
                opp_score += 15.0
            elif abs_chg > 55.0:
                opp_score -= 10.0  # Exhaustion penalty for overextended pairs

            candidates.append({
                "symbol": symbol,
                "last_price": last_px,
                "volume_24h": vol_24,
                "change_24h_pct": round(chg_24, 2),
                "momentum_score": momentum_score,
                "opportunity_score": round(opp_score, 2),
                "direction": trade_direction,
                "high_24h": high_24,
                "low_24h": low_24,
            })

        # Separate into Long and Short candidate pools
        long_candidates = [c for c in candidates if c["direction"] == "buy"]
        short_candidates = [c for c in candidates if c["direction"] == "sell"]

        # Rank each direction by opportunity score
        long_candidates.sort(key=lambda x: x["opportunity_score"], reverse=True)
        short_candidates.sort(key=lambda x: x["opportunity_score"], reverse=True)

        results: list[GainerCandidate] = []
        # Include top 10 Longs (ranks 1 to 10)
        for rank, item in enumerate(long_candidates[:10], start=1):
            results.append(
                GainerCandidate(
                    symbol=item["symbol"],
                    last_price=item["last_price"],
                    volume_24h=item["volume_24h"],
                    change_24h_pct=item["change_24h_pct"],
                    momentum_score=item["momentum_score"],
                    opportunity_score=item["opportunity_score"],
                    direction=item["direction"],
                    high_24h=item["high_24h"],
                    low_24h=item["low_24h"],
                    spread_bps=3.5,
                    is_top_gainer=True,
                    gain_rank=rank,
                )
            )

        # Include top 10 Shorts (ranks 1 to 10)
        for rank, item in enumerate(short_candidates[:10], start=1):
            results.append(
                GainerCandidate(
                    symbol=item["symbol"],
                    last_price=item["last_price"],
                    volume_24h=item["volume_24h"],
                    change_24h_pct=item["change_24h_pct"],
                    momentum_score=item["momentum_score"],
                    opportunity_score=item["opportunity_score"],
                    direction=item["direction"],
                    high_24h=item["high_24h"],
                    low_24h=item["low_24h"],
                    spread_bps=3.5,
                    is_top_gainer=False,
                    gain_rank=rank,
                )
            )

        # Sort the full 1-10 ranked pool by highest overall opportunity score
        results.sort(key=lambda x: x.opportunity_score, reverse=True)

        self.log.info(
            "DYNAMIC_MOVERS_DISCOVERED",
            total_usdt_pairs=len(prices),
            eligible_movers=len(candidates),
            top_longs=min(10, len(long_candidates)),
            top_shorts=min(10, len(short_candidates)),
            total_ranked_pool=len(results),
        )
        return results

    @staticmethod
    def get_high_volume_majors(
        prices: dict[str, Any],
        symbols: tuple[str, ...] = ("B-BTC_USDT", "B-ETH_USDT", "B-SOL_USDT", "B-XRP_USDT", "B-DOGE_USDT"),
    ) -> list[GainerCandidate]:
        """Always include major liquidity pairs for baseline comparative analysis."""
        majors: list[GainerCandidate] = []
        for sym in symbols:
            data = prices.get(sym, {})
            if not isinstance(data, dict):
                continue
            last_px = float(data.get("ls") or data.get("mp") or 0.0)
            if last_px <= 0:
                continue
            vol = float(data.get("v") or 5_000_000.0)
            chg = float(data.get("pc") or 0.0)
            majors.append(
                GainerCandidate(
                    symbol=sym,
                    last_price=last_px,
                    volume_24h=vol,
                    change_24h_pct=round(chg, 2),
                    momentum_score=round(chg * math.log10(max(vol, 1.0)), 2),
                    high_24h=float(data.get("h") or last_px * 1.02),
                    low_24h=float(data.get("l") or last_px * 0.98),
                    spread_bps=2.5,
                    is_top_gainer=False,
                    gain_rank=99,
                )
            )
        return majors
