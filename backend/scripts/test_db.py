import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT load_id, origem, destino, quantidade, fonte FROM cargas;'))
        for row in result.fetchall():
            print(row)

asyncio.run(main())
