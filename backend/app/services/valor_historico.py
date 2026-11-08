import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carga_valor_historico import CargaValorHistorico

logger = logging.getLogger("cargo.valor_historico")


async def registrar_valor(
    db: AsyncSession, load_id: Optional[str], fonte: str,
    origem: Optional[str], destino: Optional[str], valor: Optional[Decimal],
) -> None:
    """Grava uma linha de histórico se o valor da carga for novo ou tiver mudado
    desde o último registro. Só observa: nunca altera a carga e nunca levanta
    erro (o scraper não pode quebrar por causa do histórico)."""
    if not load_id or valor is None:
        return
    try:
        ultimo = (await db.execute(
            select(CargaValorHistorico)
            .where(CargaValorHistorico.load_id == load_id, CargaValorHistorico.fonte == fonte)
            .order_by(CargaValorHistorico.registrado_em.desc())
            .limit(1)
        )).scalar_one_or_none()
        if ultimo is None or Decimal(ultimo.valor) != Decimal(valor):
            db.add(CargaValorHistorico(
                load_id=load_id, fonte=fonte, origem=origem, destino=destino, valor=valor,
            ))
    except Exception as e:
        logger.error(f"Não consegui registrar histórico de valor do load {load_id}: {e}")
