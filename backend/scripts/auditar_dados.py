"""Auditoria SOMENTE LEITURA dos dados. Rode de backend/: ../venv/Scripts/python -m scripts.auditar_dados [horas]
(usa DATABASE_URL do ambiente). Em produção, prefira GET /api/estatisticas/auditoria."""
import asyncio
import sys

from app.database import AsyncSessionLocal
from app.services.auditoria_service import auditar


async def main(horas: int) -> None:
    async with AsyncSessionLocal() as db:
        achados = await auditar(db, horas)
    print("
".join(achados) if achados else "OK: nenhum problema encontrado")


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 24))
