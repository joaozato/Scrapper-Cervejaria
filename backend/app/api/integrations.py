import secrets
import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.carga import Carga
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaItem, RelatorioCargaDiff
from app.rate_limit import limiter
from app.schemas.carga import CargaResponse
from app.schemas.relatorio_carga import (
    RelatorioCapturaListResponse,
    RelatorioCapturaResponse,
    RelatorioCapturaDetailResponse,
    RelatorioComparacaoResponse,
)
from app.services import relatorio_carga_service


class CargaListResponse(BaseModel):
    items: List[CargaResponse]
    total: int

router = APIRouter(
    prefix="/api/integrations",
    tags=["integrations"],
)


async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Autenticação por API key fixa (header X-API-Key), separada do login
    por cookie usado pelos operadores — pensada para consumo máquina-a-máquina
    (a IA interna da empresa), não para navegador. Sem INTEGRATION_API_KEY
    configurada no ambiente, o endpoint fica 404 em vez de aceitar qualquer
    chave ou nenhuma."""
    if not settings.INTEGRATION_API_KEY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.INTEGRATION_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@router.get("/cargas", response_model=CargaListResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
async def get_cargas_integration(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    desde: Optional[datetime] = Query(None, description="Só cargas com data_captura >= este instante (para sincronização incremental)"),
    db: AsyncSession = Depends(get_db),
):
    """Lista cargas capturadas, somente leitura, para consumo pela IA interna
    da empresa. Endpoint próprio (não reaproveita /api/cargas) para poder
    evoluir independente do que a UI de operadores precisa. Ordenado do mais
    antigo pro mais novo (junto com 'desde') para dar um cursor natural de
    sincronização incremental."""
    conditions = [Carga.data_captura >= desde] if desde is not None else []

    count_stmt = select(func.count()).select_from(Carga)
    stmt = select(Carga).order_by(Carga.data_captura.asc()).offset(skip).limit(limit)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt)
    cargas = result.scalars().all()

    return {"items": cargas, "total": total}


@router.get("/relatorios", response_model=RelatorioCapturaListResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
async def get_relatorios_integration(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    desde: Optional[datetime] = Query(None, description="Só capturas com capturado_em >= este instante (para sincronização incremental)"),
    data: Optional[date] = Query(None, description="Filtra pelo dia da captura (data_referencia)"),
    db: AsyncSession = Depends(get_db),
):
    """Lista as capturas do relatório de cargas (Portal), somente leitura,
    para a IA interna cruzar com motoristas/cargas. Cada captura cobre uma
    janela de hoje até +5 dias de carregamento (ver relatorio_carga_service);
    use GET /relatorios/{id} para os itens de uma captura específica."""
    conditions = []
    if desde is not None:
        conditions.append(RelatorioCaptura.capturado_em >= desde)
    if data is not None:
        conditions.append(RelatorioCaptura.data_referencia == data)

    count_stmt = select(func.count()).select_from(RelatorioCaptura)
    stmt = select(RelatorioCaptura).order_by(RelatorioCaptura.capturado_em.asc()).offset(skip).limit(limit)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = (await db.execute(count_stmt)).scalar_one()
    capturas = (await db.execute(stmt)).scalars().all()

    return RelatorioCapturaListResponse(
        items=[RelatorioCapturaResponse.model_validate(c) for c in capturas],
        total=total,
    )


@router.get("/relatorios/{relatorio_id}", response_model=RelatorioCapturaDetailResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
async def get_relatorio_detail_integration(
    request: Request,
    relatorio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Detalha uma captura do relatório de cargas, com todos os itens (Lata)
    lidos naquele CSV — inclui status_smartcargas, aceita/confirmado e a data
    de carregamento de cada pedido."""
    captura = await db.get(RelatorioCaptura, relatorio_id)
    if not captura:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    itens = (
        (await db.execute(
            select(RelatorioCargaItem).where(RelatorioCargaItem.relatorio_id == relatorio_id)
        )).scalars().all()
    )

    data = RelatorioCapturaResponse.model_validate(captura).model_dump()
    data["itens"] = itens
    return RelatorioCapturaDetailResponse.model_validate(data)


@router.get("/relatorios/{relatorio_id}/comparacao", response_model=RelatorioComparacaoResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
async def get_relatorio_comparacao_integration(
    request: Request,
    relatorio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Diff dessa captura contra a captura anterior do mesmo dia: pedidos
    novos, que sumiram do relatório, ou que mudaram de status_smartcargas.
    'elegivel_erp' sinaliza os pedidos de Lata já confirmados explicitamente."""
    captura = await db.get(RelatorioCaptura, relatorio_id)
    if not captura:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    # Mesma lógica de cache de GET /api/relatorios-carga/{id}/comparacao: os
    # diffs são calculados e persistidos uma vez (comparar_com_anterior faz
    # db.add + commit); em chamadas seguintes (a IA pode consultar o mesmo
    # relatório várias vezes) só reaproveita o que já existe, para não gerar
    # linhas duplicadas de diff a cada polling.
    diffs_existentes = (
        (await db.execute(
            select(RelatorioCargaDiff).where(RelatorioCargaDiff.relatorio_atual_id == relatorio_id)
        )).scalars().all()
    )

    if diffs_existentes:
        relatorio_anterior_id = diffs_existentes[0].relatorio_anterior_id
        novos = [d for d in diffs_existentes if d.tipo_mudanca == "novo"]
        sumidos = [d for d in diffs_existentes if d.tipo_mudanca == "sumiu"]
        status_alterado = [d for d in diffs_existentes if d.tipo_mudanca == "status_alterado"]
    else:
        comparacao = await relatorio_carga_service.comparar_com_anterior(db, captura)
        relatorio_anterior_id = comparacao["relatorio_anterior_id"]
        novos = comparacao["novos"]
        sumidos = comparacao["sumidos"]
        status_alterado = comparacao["status_alterado"]

    return RelatorioComparacaoResponse(
        relatorio_atual_id=relatorio_id,
        relatorio_anterior_id=relatorio_anterior_id,
        total_novos=len(novos),
        total_sumidos=len(sumidos),
        total_status_alterado=len(status_alterado),
        novos=novos,
        sumidos=sumidos,
        status_alterado=status_alterado,
    )
