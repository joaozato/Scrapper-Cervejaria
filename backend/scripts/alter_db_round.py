import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def run():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is missing!")
        return
    conn = await asyncpg.connect(db_url)
    await conn.execute('ALTER TABLE cargas ADD COLUMN IF NOT EXISTS round_hora INTEGER')
    await conn.close()
    print("Database altered successfully: added round_hora column.")

if __name__ == "__main__":
    asyncio.run(run())
