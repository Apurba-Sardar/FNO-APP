import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.services.coindcx.public_client import CoinDCXPublicClient

async def test():
    client = CoinDCXPublicClient(
        api_base_url="https://api.coindcx.com",
        public_base_url="https://public.coindcx.com",
        timeout=10,
    )
    async with client:
        snap = await client.current_prices()
        print(f"Total pairs in snapshot: {len(snap.prices)}")
        usdt_pairs = []
        for k, v in snap.prices.items():
            if not k.startswith("B-") or not k.endswith("_USDT"):
                continue
            if not isinstance(v, dict):
                continue
            vol = float(v.get("v") or 0.0)
            pc = float(v.get("pc") or 0.0)
            ls = float(v.get("ls") or v.get("mp") or 0.0)
            if vol >= 1_000_000 and ls > 0:
                usdt_pairs.append({
                    "symbol": k,
                    "last_price": ls,
                    "volume_24h": vol,
                    "change_24h": pc,
                })
        print(f"Total USDT futures pairs with vol >= 1M: {len(usdt_pairs)}")
        
        # Sort by 24h change descending (top gainers)
        gainers = sorted(usdt_pairs, key=lambda x: x["change_24h"], reverse=True)
        print("\n--- TOP 15 24H GAINERS (VOLUME >= 1M USDT) ---")
        for g in gainers[:15]:
            print(f"{g['symbol']:<16} Change: {g['change_24h']:+6.2f}% | Vol: ${g['volume_24h']:>14,.0f} | Px: ${g['last_price']}")

        # Composite rank: high volume + high positive momentum
        import math
        momentum_pairs = [p for p in usdt_pairs if p["change_24h"] > 0]
        momentum_pairs.sort(key=lambda x: x["change_24h"] * math.log10(max(x["volume_24h"], 1)), reverse=True)
        print("\n--- TOP 10 MOMENTUM SCALP PAIRS (GAIN + VOLUME) ---")
        for m in momentum_pairs[:10]:
            print(f"{m['symbol']:<16} Change: {m['change_24h']:+6.2f}% | Vol: ${m['volume_24h']:>14,.0f} | Px: ${m['last_price']}")

if __name__ == "__main__":
    asyncio.run(test())
