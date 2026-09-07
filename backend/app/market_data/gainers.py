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
    high_24h: float | None = None
    low_24h: float | None = None
    spread_bps: float = 3.5
    is_top_gainer: bool = True
    gain_rank: int = 1


class DynamicGainerScanner:
    """Discovers and ranks high-volume 24h top gainers across all 537+ CoinDCX futures pairs."""

    def __init__(
        self,
        min_volume_usdt: float = 2_000_000.0,
        min_gain_pct: float = 0.5,
        max_spread_bps: float = 15.0,
    ) -> None:
        self.min_volume_usdt = min_volume_usdt
        self.min_gain_pct = min_gain_pct
        self.max_spread_bps = max_spread_bps
        self.log = structlog.get_logger().bind(component="DynamicGainerScanner")

    async def scan_market_gainers(
        self,
        client: CoinDCXPublicClient,
        limit: int = 15,
    ) -> list[GainerCandidate]:
        """Fetch all real-time market prices, filter for USDT futures with high volume and positive 24h change,

        and rank by institutional momentum.
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

            # Filter for liquidity and positive 24h gain
            if last_px <= 0 or vol_24 < self.min_volume_usdt or chg_24 < self.min_gain_pct:
                continue

            # Composite momentum: 24h percentage gain weighted by institutional volume depth
            # Ensures high volume breakout coins (e.g. +30% with $50M+ vol) rank highest
            vol_log = math.log10(max(vol_24, 1_000_000.0))
            momentum_score = round(chg_24 * vol_log, 2)

            candidates.append({
                "symbol": symbol,
                "last_price": last_px,
                "volume_24h": vol_24,
                "change_24h_pct": round(chg_24, 2),
                "momentum_score": momentum_score,
                "high_24h": high_24,
                "low_24h": low_24,
            })

        # Rank by composite momentum score descending
        candidates.sort(key=lambda x: x["momentum_score"], reverse=True)

        results: list[GainerCandidate] = []
        for rank, item in enumerate(candidates[:limit], start=1):
            results.append(
                GainerCandidate(
                    symbol=item["symbol"],
                    last_price=item["last_price"],
                    volume_24h=item["volume_24h"],
                    change_24h_pct=item["change_24h_pct"],
                    momentum_score=item["momentum_score"],
                    high_24h=item["high_24h"],
                    low_24h=item["low_24h"],
                    spread_bps=3.5,
                    is_top_gainer=True,
                    gain_rank=rank,
                )
            )

        self.log.info(
            "DYNAMIC_GAINERS_DISCOVERED",
            total_usdt_pairs=len(prices),
            eligible_gainers=len(candidates),
            top_picked=len(results),
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
