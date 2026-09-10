import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://fno:fno@localhost:5432/fno")
    rows = await conn.fetch("SELECT position_id, pair, status FROM live_positions")
    print(f"Total live_positions in DB: {len(rows)}")
    for r in rows:
        print(f"  {r['position_id']} - {r['pair']} - {r['status']}")
    
    # Mark any stale open positions as closed so the bot starts completely clean
    result = await conn.execute("UPDATE live_positions SET status = 'closed' WHERE status = 'open'")
    print(f"Update result: {result}")
    
    # Also clean up live_runtime state record if needed
    runtime_record = await conn.fetchrow("SELECT key, payload FROM live_runtime WHERE key = 'current'")
    if runtime_record:
        print("Found live_runtime record")
    
    await conn.close()
    print("Database sync complete.")

if __name__ == "__main__":
    asyncio.run(main())
