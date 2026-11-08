import asyncio
from sqlalchemy import text
from app.database import engine, AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import hash_password

async def alter_db():
    print("Alterando banco de dados...")
    
    # Adicionar coluna rota_frequente
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE motoristas ADD COLUMN rota_frequente VARCHAR(255);"))
            print("Coluna 'rota_frequente' adicionada na tabela 'motoristas'.")
        except Exception as e:
            if "already exists" in str(e).lower() or "já existe" in str(e).lower() or "42701" in str(e):
                print("Coluna 'rota_frequente' já existe, ignorando...")
            else:
                print(f"Erro ao adicionar coluna: {e}")

    # Criar operadores
    async with AsyncSessionLocal() as db:
        operadores = ["operador1", "operador2", "operador3"]
        for op in operadores:
            # Check if exists
            result = await db.execute(text(f"SELECT id FROM users WHERE username = '{op}'"))
            existing = result.scalar_one_or_none()
            
            if not existing:
                print(f"Criando {op}...")
                user = User(
                    username=op,
                    email=f"{op}@example.com",
                    hashed_password=hash_password(f"Cargo{op.capitalize()}!2026"),
                    full_name=f"Operador {op.replace('operador', '')}",
                    role="viewer",
                )
                db.add(user)
            else:
                print(f"{op} já existe.")
        
        await db.commit()
        print("Operadores verificados/criados.")

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(alter_db())
