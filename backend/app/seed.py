"""
Seed script: imports data from the Excel spreadsheet into PostgreSQL.
Also creates the admin user.

Usage: python -m app.seed
"""
import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from app.database import engine, AsyncSessionLocal, Base
from app.models.user import User
from app.models.motorista import Motorista
from app.models.disponibilidade import Disponibilidade
from app.services.auth_service import hash_password
from app.config import settings


# Excel data extracted from DISPONIBILIDADE ORIGINAL sheet
SEED_DATA = [
    {"mes": "JULHO", "dia": 1, "motorista": "Adenor Ribeiro Rodrigues", "plts": 25, "origem": "Canpack Itumbiara", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-01"},
    {"mes": "JULHO", "dia": 1, "motorista": "Ismael", "plts": 25, "origem": "Planta - Mirassol", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "NOK", "data": "2026-07-01"},
    {"mes": "JULHO", "dia": 2, "motorista": "Motorista Exemplo A", "plts": 25, "origem": "Planta - Mirassol", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 2, "motorista": "Julio Barros", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 2, "motorista": "Motorista Exemplo B", "plts": 25, "origem": "Planta - Três Rios", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 3, "motorista": "Sibeli", "plts": 25, "origem": "Planta - Pouso Alegre", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 3, "motorista": "Adriano", "plts": 25, "origem": "Planta - Três Rios", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 3, "motorista": "Valmir", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-02"},
    {"mes": "JULHO", "dia": 3, "motorista": "Motorista Exemplo B", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 3, "motorista": "Sibeli", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino TERESINA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 4, "motorista": "Adriano", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 5, "motorista": "Valmir", "plts": 25, "origem": "Planta - Viamão", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 5, "motorista": "Cleber", "plts": 25, "origem": "Planta - Pouso Alegre", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 5, "motorista": "Tomas", "plts": 25, "origem": "Canpack - Fortaleza", "destino": "Destino TERESINA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 5, "motorista": "Gustavo", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "NOK", "gr": "NOK", "data": "2026-07-03"},
    {"mes": "JULHO", "dia": 6, "motorista": "Giovani", "plts": 25, "origem": "Planta - Viamão", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "NOK", "gr": "NOK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 6, "motorista": "Lucio", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 6, "motorista": "Vinicius", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 8, "motorista": "Cesar", "plts": 25, "origem": "Planta - Viamão", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 8, "motorista": "Maicon", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 8, "motorista": "Silvio", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 10, "motorista": "Santos", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 10, "motorista": "Moreira", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-05"},
    {"mes": "JULHO", "dia": 10, "motorista": "Neymar", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-06"},
    {"mes": "JULHO", "dia": 15, "motorista": "Zeca", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-06"},
    {"mes": "JULHO", "dia": 15, "motorista": "Nilton", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-06"},
    {"mes": "JULHO", "dia": 15, "motorista": "Enner", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-07"},
    {"mes": "JULHO", "dia": 28, "motorista": "Roberto", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-07"},
    {"mes": "JULHO", "dia": 28, "motorista": "TWV", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-07"},
    {"mes": "JULHO", "dia": 28, "motorista": "Jairton", "plts": 25, "origem": "Planta - Pouso Alegre", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-08"},
    {"mes": "JULHO", "dia": 29, "motorista": "Cicero", "plts": 25, "origem": "Canpack - Fortaleza", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-08"},
    {"mes": "JULHO", "dia": 30, "motorista": "Jhon Robert", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-08"},
    {"mes": "JULHO", "dia": 30, "motorista": "Hananel", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-09"},
    {"mes": "JULHO", "dia": 30, "motorista": "Eloi", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Marcos Aurelio", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Alexandre", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Joao Rodrigues", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino TERESINA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Julio Enner Valencia", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ESTANCIA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Cleber", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Fabricio Melo", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Arthur Coala", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Jorge Delafon", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Gregory", "plts": 25, "origem": "Planta - Frutal", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "OK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Simba", "plts": 25, "origem": "Planta - Jacareí", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Jimmy", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Meireles", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "NOK", "data": "2026-07-10"},
    {"mes": "JULHO", "dia": 30, "motorista": "Hananel", "plts": 25, "origem": "Planta - Cabo De Santo Agostinho", "destino": "Destino ITAPISSUMA", "valor": 390, "cadastro": "NOK", "gr": "OK", "data": "2026-07-11"},
]


async def seed():
    """Create tables and seed initial data."""
    print("🔧 Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(User))
        if result.scalar_one_or_none():
            print("⚠️  Database already seeded. Skipping.")
            return

        # Create admin user
        print("👤 Creating admin user...")
        admin = User(
            username=settings.ADMIN_USERNAME,
            email="admin@example.com",
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            full_name="Administrador CARGO",
            role="admin",
        )
        db.add(admin)
        await db.flush()

        # Create motoristas and disponibilidades
        print("🚛 Seeding motoristas and disponibilidades...")
        motorista_cache = {}

        for entry in SEED_DATA:
            nome = entry["motorista"]

            # Get or create motorista
            if nome not in motorista_cache:
                result = await db.execute(
                    select(Motorista).where(Motorista.nome == nome)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    motorista_cache[nome] = existing
                else:
                    m = Motorista(nome=nome, tipo="motorista")
                    db.add(m)
                    await db.flush()
                    motorista_cache[nome] = m

            motorista = motorista_cache[nome]

            # Derive pode_carregar_direto
            pode = "OK" if entry["cadastro"] == "OK" and entry["gr"] == "OK" else "NOK"

            disp = Disponibilidade(
                motorista_id=motorista.id,
                mes=entry["mes"],
                dia_disponivel=entry["dia"],
                plts=entry["plts"],
                origem=entry["origem"],
                destino_preferencia=entry["destino"],
                valor=Decimal(str(entry["valor"])),
                cadastro=entry["cadastro"],
                gr=entry["gr"],
                pode_carregar_direto=pode,
                data_conversa=datetime.strptime(entry["data"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                ),
                updated_by=admin.id,
            )
            db.add(disp)

        await db.commit()
        print(f"✅ Seeded {len(SEED_DATA)} disponibilidades and {len(motorista_cache)} motoristas.")
        print(f"📋 Admin login: {settings.ADMIN_USERNAME} / {settings.ADMIN_PASSWORD}")


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
