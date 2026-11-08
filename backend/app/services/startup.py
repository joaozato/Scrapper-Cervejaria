import os
import logging
from sqlalchemy import text, select
from app.database import engine, Base, AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import hash_password

logger = logging.getLogger("cargo.database.startup")

async def run_startup_migrations():
    """Runs database migrations and initial seeding."""
    try:
        # Quick DB patch for new columns
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE disponibilidades ADD COLUMN IF NOT EXISTS tarifa_cargo VARCHAR(3) DEFAULT 'NOK' NOT NULL"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS load_id VARCHAR(100)"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS fonte VARCHAR(50) DEFAULT 'Carga Prioritária' NOT NULL"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS tags VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS ultima_visualizacao TIMESTAMP WITH TIME ZONE"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS round_hora INTEGER"))
            await conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS observacao VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS rota_frequente VARCHAR(255)"))
            await conn.execute(text("UPDATE cargas SET ultima_visualizacao = data_captura WHERE ultima_visualizacao IS NULL"))
            # load_id pode se repetir entre fontes (a mesma carga migra do Carga Prioritária pro Pool de Cargas
            # quando não é aceita), então a unicidade precisa ser por (load_id, fonte), não global.
            await conn.execute(text("ALTER TABLE cargas DROP CONSTRAINT IF EXISTS cargas_load_id_key"))
            await conn.execute(text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_carga_load_id_fonte') THEN "
                "ALTER TABLE cargas ADD CONSTRAINT uq_carga_load_id_fonte UNIQUE (load_id, fonte); "
                "END IF; "
                "END $$;"
            ))
            await conn.run_sync(Base.metadata.create_all)
            # Aceites que já existiam antes da tabela carga_aceites: entram como "historico"
            # (horário aproximado pela última visualização, fora do gráfico por horário).
            await conn.execute(text(
                "INSERT INTO carga_aceites (id, carga_id, load_id, fonte, origem, destino, data_carregamento, "
                "tipo_carga, quantidade, valor, detectado_em, passe) "
                "SELECT gen_random_uuid(), c.id, c.load_id, c.fonte, c.origem, c.destino, c.data_carregamento, "
                "c.tipo_carga, COALESCE(c.quantidade, 1), c.valor, COALESCE(c.ultima_visualizacao, c.data_captura), 'historico' "
                "FROM cargas c WHERE c.fonte = 'Carga Prioritária' AND c.status_portal IN ('Aceita', 'Confirmada') "
                "AND NOT EXISTS (SELECT 1 FROM carga_aceites a WHERE a.carga_id = c.id)"
            ))
            
        async with AsyncSessionLocal() as db:
            # Criar operadores (nível usuário comum)
            operadores = [
                {"username": "operador1", "full_name": "Operador Exemplo", "senha": os.getenv("SEED_OPERATOR_PASSWORD", "change_me")},
            ]
            for op in operadores:
                result = await db.execute(select(User).where(User.username == op["username"]))
                existing_user = result.scalar_one_or_none()
                if not existing_user:
                    user = User(
                        username=op["username"],
                        email=f"{op['username']}@example.com",
                        hashed_password=hash_password(op["senha"]),
                        full_name=op["full_name"],
                        role="viewer",
                    )
                    db.add(user)
                else:
                    existing_user.hashed_password = hash_password(op["senha"])
                    existing_user.full_name = op["full_name"]
                    existing_user.role = "viewer"
                    
            # Criar novos administradores
            admins = [
                {"username": "admin2", "full_name": "Administrador Exemplo", "senha": os.getenv("SEED_ADMIN_PASSWORD", "change_me")},
            ]
            for adm in admins:
                result = await db.execute(select(User).where(User.username == adm["username"]))
                existing_user = result.scalar_one_or_none()
                if not existing_user:
                    user = User(
                        username=adm["username"],
                        email=f"{adm['username']}@example.com",
                        hashed_password=hash_password(adm["senha"]),
                        full_name=adm["full_name"],
                        role="admin",
                    )
                    db.add(user)
                else:
                    existing_user.hashed_password = hash_password(adm["senha"])
                    existing_user.full_name = adm["full_name"]
                    existing_user.role = "admin"
                    
            await db.commit()
            
        logger.info("✅ Verified DB tables and applied patches (incluindo criação de operadores)")
    except Exception as e:
        logger.error(f"Failed to run DB patch/creation: {e}")
