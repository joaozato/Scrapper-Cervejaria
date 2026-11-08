import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT data_captura FROM cargas ORDER BY data_captura DESC LIMIT 20;'))
        rows = result.fetchall()
        print("Últimas 20 cargas inseridas (por data_captura):")
        for row in rows:
            print(row[0])
            
        print("\nContagem por data_captura (truncada para dia):")
        result = await db.execute(text("SELECT date(data_captura), count(*) FROM cargas GROUP BY date(data_captura) ORDER BY date(data_captura) DESC;"))
        for row in result.fetchall():
            print(f"{row[0]}: {row[1]} cargas")

asyncio.run(main())
