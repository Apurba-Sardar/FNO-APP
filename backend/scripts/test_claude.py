import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

load_dotenv(backend_root.parent / ".env")

from app.ai.claude_advisor import ClaudeScalpAdvisor


async def test():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    print(f"Loaded key length: {len(key)} | Model: {model}")

    advisor = ClaudeScalpAdvisor(api_key=key, model=model)
    res = await advisor.analyze_scalp(
        symbol="B-XRP_USDT",
        current_price=1.45,
        direction="buy",
        metrics={"quote_volume": 1800000, "rsi": 54.2, "spread_bps": 3.2, "trend": "BULLISH"},
    )

    print("\n--- CLAUDE AI SCALP ANALYSIS ---")
    print(f"AI Provider: {res.ai_provider}")
    print(f"Conviction Score: {res.conviction_score} / 100")
    print(f"Sentiment: {res.sentiment}")
    print(f"Pre-Flight Approved: {res.pre_flight_approved}")
    print(f"Optimal Entry Zone: {res.optimal_entry_zone}")
    print(f"Target Price: ${res.target_price:,.4g}")
    print(f"Stop Price: ${res.stop_price:,.4g}")
    print(f"Institutional Rationale: {res.pro_trader_rationale}\n")


if __name__ == "__main__":
    asyncio.run(test())
