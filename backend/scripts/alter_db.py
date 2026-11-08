import os
import asyncio
import asyncpg

async def run():
    db_url = os.getenv("DATABASE_URL", "postgresql://cargo_admin:change_me@localhost:5433/cargo_disponibilidade")
    conn = await asyncpg.connect(db_url)
    await conn.execute('ALTER TABLE cargas ADD COLUMN IF NOT EXISTS quantidade INTEGER DEFAULT 1 NOT NULL')
    await conn.execute('ALTER TABLE cargas ADD COLUMN IF NOT EXISTS tags VARCHAR(255)')
    await conn.execute('ALTER TABLE cargas ADD COLUMN IF NOT EXISTS ultima_visualizacao TIMESTAMP WITH TIME ZONE')
    await conn.execute('UPDATE cargas SET ultima_visualizacao = data_captura WHERE ultima_visualizacao IS NULL')
    await conn.close()
    print("Database altered successfully!")

asyncio.run(run())
