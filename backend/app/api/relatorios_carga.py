import csv
import io
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.relatorio_carga import RelatorioCaptura, RelatorioCargaItem, RelatorioCargaDiff
from app.schemas.relatorio_carga import (
    RelatorioCapturaListResponse,
    RelatorioCapturaResponse,
    RelatorioCapturaDetailResponse,
    RelatorioComparacaoResponse,
)
from app.services.auth_service import get_current_user
from app.services import relatorio_carga_service
from app.models.user import User

router = APIRouter(
    prefix="/api/relatorios-carga",
    tags=["relatorios-carga"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=RelatorioCapturaListResponse)
async def listar_capturas(
    data: Optional[date] = Query(None, description="Filtra pela data de referência"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(RelatorioCaptura).order_by(RelatorioCaptura.capturado_em.desc())
    count_query = select(func.count()).select_from(RelatorioCaptura)
    if data:
        query = query.where(RelatorioCaptura.data_referencia == data)
        count_query = count_query.where(RelatorioCaptura.data_referencia == data)

    total = (await db.execute(count_query)).scalar_one()
    capturas = (await db.execute(query.limit(200))).scalars().all()

    return RelatorioCapturaListResponse(
        items=[RelatorioCapturaResponse.model_validate(c) for c in capturas],
        total=total,
    )


@router.get("/exportar")
async def exportar_capturas(
    ids: str = Query(..., description="IDs das capturas separados por vírgula"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """CSV com as linhas exatamente como vieram do Portal (dados_raw), com os
    cabeçalhos originais. Várias capturas são concatenadas."""
    try:
        id_list = [uuid.UUID(i) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs inválidos")
    if not id_list:
        raise HTTPException(status_code=400, detail="Nenhum relatório informado")

    capturas = (
        (await db.execute(
            select(RelatorioCaptura)
            .where(RelatorioCaptura.id.in_(id_list))
            .order_by(RelatorioCaptura.capturado_em.asc())
        )).scalars().all()
    )
    if not capturas:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    linhas: list[dict] = []
    colunas: list[str] = []
    for c in capturas:
        itens = (
            (await db.execute(
                select(RelatorioCargaItem).where(RelatorioCargaItem.relatorio_id == c.id)
            )).scalars().all()
        )
        for it in itens:
            raw = it.dados_raw or {}
            linhas.append(raw)
            for k in raw:
                if k not in colunas:
                    colunas.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=colunas, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(linhas)

    nome = (
        f"relatorio_{capturas[0].data_referencia}.csv"
        if len(capturas) == 1
        else f"relatorios_{len(capturas)}_capturas.csv"
    )
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/{relatorio_id}", response_model=RelatorioCapturaDetailResponse)
async def detalhar_captura(
    relatorio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
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


@router.get("/{relatorio_id}/comparacao", response_model=RelatorioComparacaoResponse)
async def comparar_captura(
    relatorio_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    captura = await db.get(RelatorioCaptura, relatorio_id)
    if not captura:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

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
